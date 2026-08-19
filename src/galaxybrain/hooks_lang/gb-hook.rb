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
  CRASHES_DIR  = File.join(Dir.home, '.galaxy-brain')
  CRASHES_FILE = File.join(CRASHES_DIR, 'crashes.jsonl')

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

    # Build the schema-v2 crash record.
    def build_record(exception)
      cwd = Dir.pwd
      frames = parse_backtrace(exception.backtrace)
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
