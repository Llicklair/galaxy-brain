# gb-hook.rb — Ruby crash capture hook for galaxy-brain (schema v2)
#
# Install: RUBYOPT="-r /path/to/gb-hook.rb"
#
# Zero external dependencies (json is Ruby stdlib).
# Dormant until the process exits with an unhandled exception ($!).
# Appends a JSON record to ~/.galaxy-brain/crashes.jsonl, then lets
# the process die normally (the original error message is preserved).

require 'json'
require 'securerandom'
require 'fileutils'

# W3C Trace Context por variable de entorno (spec de OpenTelemetry para cruzar
# procesos sin red): se lee el TRACEPARENT de quien nos llamo, su span queda
# como PADRE, se genera el propio y se re-exporta para los hijos. No depende de
# pids, que es donde varios runtimes no llegan.
GB_TRACE = begin
  previo = (ENV['TRACEPARENT'] || '').split('-')
  traza = (previo.length == 4 && previo[1].length == 32) ? previo[1] : SecureRandom.hex(16)
  padre = (previo.length == 4 && previo[2].length == 16) ? previo[2] : nil
  propio = SecureRandom.hex(8)
  ENV['TRACEPARENT'] = "00-#{traza}-#{propio}-01"
  { trace_id: traza, span_id: propio, parent_span: padre }
rescue StandardError
  { trace_id: nil, span_id: nil, parent_span: nil }
end
require 'socket'       # for hostname (stdlib)
require 'time'         # for Time#iso8601 (stdlib)

module GBHook
  # GB_HOME manda, como en el resto de gb.
  CRASHES_DIR  = ENV['GB_HOME'] || File.join(Dir.home, '.galaxy-brain')
  CRASHES_FILE = File.join(CRASHES_DIR, 'crashes.jsonl')

  # La MISMA lista que config.REDACT_PATTERNS de Python (la sonda de la suite
  # caza la deriva). Por NOMBRE, no por contenido: coste asimetrico.
  REDACT = %w[passwd password secret token api_key apikey auth credential
              private_key session cookie].freeze
  REDACTADO = '<redactado>'

  # El binding del PRIMER raise de la excepcion que acabe matando el proceso.
  # `at_exit` llega con la pila desenrollada (backtrace = strings, sin estado);
  # TracePoint(:raise) dispara EN el raise con el frame vivo. Ruby no sabe ahi
  # si sera capturada, asi que se aparca la REFERENCIA (coste ~0 por raise) y
  # los locals se extraen solo al morir, si la que muere es la aparcada.
  ULTIMO_RAISE = { exc: nil, binding: nil }

  class << self

    # Walk up from dir looking for .git
    def find_project_root(dir)
      cur = File.expand_path(dir)
      loop do
        return cur if File.exist?(File.join(cur, '.git'))
        parent = File.dirname(cur)
        return nil if parent == cur   # reached filesystem root
        cur = parent
      end
    rescue
      nil
    end

    # Redact argv: keep flag names, replace values with <val>.
    def redact_argv(argv)
      result = []
      skip_next = false
      argv.each_with_index do |arg, i|
        if skip_next
          skip_next = false
          next
        end

        if arg.match?(/\A--?[a-zA-Z]/)
          eq_idx = arg.index('=')
          if eq_idx
            result << "#{arg[0..eq_idx]}<val>"
          else
            result << arg
            # If next arg exists and is not a flag, it's this flag's value.
            nxt = argv[i + 1]
            if nxt && !nxt.match?(/\A--?[a-zA-Z]/)
              result << '<val>'
              skip_next = true
            end
          end
        else
          result << arg
        end
      end
      result
    end

    # Parse a Ruby backtrace array into structured frames.
    # Ruby format: "/path/to/file.rb:42:in `method_name'"
    #           or "/path/to/file.rb:42"
    def parse_backtrace(bt)
      return [] unless bt
      bt.map do |line|
        if (m = line.match(/\A(.+):(\d+):in `(.+)'\z/))
          { 'file' => m[1], 'line' => m[2].to_i, 'column' => 0, 'function' => m[3] }
        elsif (m = line.match(/\A(.+):(\d+)\z/))
          { 'file' => m[1], 'line' => m[2].to_i, 'column' => 0, 'function' => '<toplevel>' }
        else
          { 'file' => line, 'line' => 0, 'column' => 0, 'function' => '<unknown>' }
        end
      end
    end

    def sensible?(nombre)
      bajo = nombre.to_s.downcase
      REDACT.any? { |patron| bajo.include?(patron) }
    end

    def repr_local(nombre, valor)
      return REDACTADO if sensible?(nombre)
      texto = begin; valor.inspect; rescue StandardError; '<inspect fallo>'; end
      texto.length > 200 ? texto[0, 200] + '...' : texto
    end

    # Los locals del binding aparcado, redactados y acotados. Solo el frame que
    # lanza — una pila de bindings cobraria en CADA raise, y el coste ~0 del
    # aparcado es lo que hace defendible tener esto encendido por defecto.
    def locals_de(binding_, tope)
      nombres = binding_.local_variables
      fuera = {}
      nombres.first(tope).each do |nombre|
        valor = binding_.local_variable_get(nombre)
        fuera[nombre.to_s] = repr_local(nombre, valor)
      end
      fuera['...'] = '(mas variables, recortadas por GB_MAX_LOCALS)' if nombres.length > tope
      fuera
    rescue StandardError
      nil
    end

    # Build the schema-v2 crash record.
    def build_record(exception)
      cwd = Dir.pwd
      frames = parse_backtrace(exception.backtrace)
      # Paridad con Python (6-sep-2026): el estado del frame que lanzo, si el
      # que muere es el que TracePoint aparco. frames[0] es el sitio del raise
      # en el backtrace de Ruby — el mismo frame que el binding.
      if !frames.empty? && ULTIMO_RAISE[:exc].equal?(exception) && ULTIMO_RAISE[:binding]
        tope = ENV['GB_MAX_LOCALS'].to_i
        tope = 20 if tope <= 0
        locales = locals_de(ULTIMO_RAISE[:binding], tope)
        frames[0]['locals'] = locales if locales && !locales.empty?
      end
      session_id = ENV['GB_SESSION_ID'] || 'unknown'
      ppid = begin; Process.ppid; rescue; nil; end
      {
        schema:  2,
        ts:      Time.now.iso8601,
        session_id: session_id,
        trace_id: GB_TRACE[:trace_id],
        span_id: GB_TRACE[:span_id],
        parent_span: GB_TRACE[:parent_span],
        language: 'ruby',
        exception: {
          type:    exception.class.name,
          message: exception.message,
          origin:  'main'
        },
        frames:   frames,
        process: {
          cwd:        cwd,
          project:    find_project_root(cwd),
          argv_forma: redact_argv(ARGV),
          runtime:    "ruby #{RUBY_VERSION}",
          pid:        Process.pid,
          ppid:       ppid
        },
        traceback:      exception.backtrace ? exception.backtrace.join("\n") : '',
        capture_method: 'hook'
      }
    end

    # Append record to crashes.jsonl. Swallows all errors silently.
    def write_record(record)
      FileUtils.mkdir_p(CRASHES_DIR)
      File.open(CRASHES_FILE, 'a') { |f| f.puts(record.to_json) }
    rescue
      # Silent fail — never mask the real crash.
    end

    # Main entry: capture the crash if $! is set and it's a real
    # exception (not SystemExit from a normal exit).
    def report_crash(exception)
      return unless exception
      return if exception.is_a?(SystemExit) && exception.success?
      write_record(build_record(exception))
    rescue
      # Silent fail.
    end

  end
end

# El aparcador: cada raise NUEVO guarda su binding; un re-raise de la misma
# excepcion no lo pisa (el re-raise ocurre en el rescue, y sus locals no son
# los que explican el fallo). Apagable: GB_NO_RUBY_LOCALS=1.
unless %w[1 true yes on].include?(ENV['GB_NO_RUBY_LOCALS'].to_s.downcase)
  begin
    TracePoint.new(:raise) do |tp|
      unless GBHook::ULTIMO_RAISE[:exc].equal?(tp.raised_exception)
        GBHook::ULTIMO_RAISE[:exc] = tp.raised_exception
        GBHook::ULTIMO_RAISE[:binding] = tp.binding
      end
    end.enable
  rescue StandardError
    # Sin TracePoint (embebido raro): hook sin estado, como antes.
  end
end

at_exit do
  # `$!` trae la ultima excepcion, y en Ruby `exit 3` TAMBIEN es una
  # excepcion: SystemExit. Sin excluirla, un programa que termina como
  # quiso —un CLI que sale con 3, un script que hace `exit 1` tras
  # informar— deja una captura de un fallo que no existio. Medido:
  # `puts 'me voy'; exit 3` escribia un registro tipo SystemExit.
  #
  # Ensuciar el historico con salidas normales no es un detalle: el
  # embudo de `gb list` deja de significar nada, y lo que no significa
  # nada se deja de mirar.
  GBHook.report_crash($!) if $! && !$!.is_a?(SystemExit)
end
