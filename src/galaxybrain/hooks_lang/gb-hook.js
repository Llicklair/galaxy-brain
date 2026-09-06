/**
 * gb-hook.js — Node.js crash capture hook for galaxy-brain (schema v2)
 *
 * Install: NODE_OPTIONS="--require /path/to/gb-hook.js"
 *
 * Zero dependencies. Dormant until a crash occurs.
 * Appends a JSON record to ~/.galaxy-brain/crashes.jsonl on uncaught
 * exception or unhandled promise rejection, then preserves original
 * crash behavior.
 */

'use strict';

// ── W3C Trace Context por variable de entorno ──────────────────────────────
// El estandar que OpenTelemetry define para cruzar procesos cuando no hay red.
// Se lee el TRACEPARENT que dejo quien nos llamo, se anota su span como PADRE,
// se genera uno propio y se re-exporta: cualquier hijo que lancemos lo hereda
// sin que nadie tenga que cooperar. Es lo que los pids no podian dar — hay
// runtimes que no saben decir quien es su padre.
var gbTrace = (function () {
  function hex(n) {
    var s = '';
    for (var i = 0; i < n; i++) s += Math.floor(Math.random() * 16).toString(16);
    return s;
  }
  var previo = process.env.TRACEPARENT || '';
  var partes = previo.split('-');
  var traceId = (partes.length === 4 && partes[1].length === 32) ? partes[1] : hex(32);
  var parentSpan = (partes.length === 4 && partes[2].length === 16) ? partes[2] : null;
  var spanId = hex(16);
  try { process.env.TRACEPARENT = '00-' + traceId + '-' + spanId + '-01'; } catch (_) {}
  return { traceId: traceId, spanId: spanId, parentSpan: parentSpan };
})();

;(function gbHookInit() {
  // Wrap the entire hook so a bug here never masks the real error.
  try {
    var fs   = require('fs');
    var path = require('path');
    var os   = require('os');

    /* GB_HOME manda, como en el resto de gb: sin leerlo, un GB_HOME apuntado a
     * otro sitio dejaba estas capturas en el ~ real — escritas y perdidas. */
    var CRASHES_DIR  = process.env.GB_HOME || path.join(os.homedir(), '.galaxy-brain');
    var CRASHES_FILE = path.join(CRASHES_DIR, 'crashes.jsonl');

    // ---------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------

    /**
     * Walk up from `dir` looking for a directory that contains `.git`.
     * Returns the project root or null.
     */
    function findProjectRoot(dir) {
      try {
        var prev = null;
        var cur  = path.resolve(dir);
        while (cur !== prev) {
          try {
            var stat = fs.statSync(path.join(cur, '.git'));
            if (stat.isDirectory() || stat.isFile()) return cur;
          } catch (_) { /* not here, keep walking */ }
          prev = cur;
          cur  = path.dirname(cur);
        }
      } catch (_) { /* fall through */ }
      return null;
    }

    /**
     * Redact argv: keep flag names, replace their values with <val>.
     * "node app.js --token SECRET -p 8080" → ["node","app.js","--token","<val>","-p","<val>"]
     */
    function redactArgv(argv) {
      var result = [];
      for (var i = 0; i < argv.length; i++) {
        var arg = argv[i];
        if (/^--?[a-zA-Z]/.test(arg)) {
          // Flag — check if value is part of it (--flag=value) or next arg.
          var eqIdx = arg.indexOf('=');
          if (eqIdx !== -1) {
            result.push(arg.substring(0, eqIdx + 1) + '<val>');
          } else {
            result.push(arg);
            // If next arg exists and is NOT a flag, it's this flag's value.
            if (i + 1 < argv.length && !/^--?[a-zA-Z]/.test(argv[i + 1])) {
              result.push('<val>');
              i++;
            }
          }
        } else {
          result.push(arg);
        }
      }
      return result;
    }

    /**
     * Parse an Error.stack string into structured frames.
     */
    function parseStack(stack) {
      if (!stack) return [];
      var frames = [];
      var lines = stack.split('\n');
      // Typical V8 format: "    at funcName (file:line:col)"
      //                  or "    at file:line:col"
      var re = /^\s*at\s+(?:(.+?)\s+\()?(.+?):(\d+):(\d+)\)?$/;
      for (var i = 0; i < lines.length; i++) {
        var m = re.exec(lines[i]);
        if (m) {
          frames.push({
            'function': m[1] || '<anonymous>',
            file:   m[2],
            line:   parseInt(m[3], 10),
            column: parseInt(m[4], 10)
          });
        }
      }
      return frames;
    }

    /**
     * Detect language: "ts" if any frame points to a .ts file, else "js".
     */
    function detectLanguage(frames) {
      for (var i = 0; i < frames.length; i++) {
        if (/\.tsx?$/.test(frames[i].file)) return 'ts';
      }
      return 'js';
    }

    /**
     * Build the schema-v2 crash record.
     */
    function buildRecord(err, origin) {
      var rawStack  = (err && err.stack) ? err.stack : String(err);
      var frames    = parseStack(rawStack);
      var cwd       = process.cwd();
      var sessionId = process.env.GB_SESSION_ID || 'unknown';
      var ppid;
      try { ppid = process.ppid; } catch (_) { ppid = null; }

      return {
        schema:  2,
        ts:      new Date().toISOString(),
        session_id: sessionId,
        // W3C Trace Context: quien me llamo, sin depender de pids. Ver
        // gbTrace() abajo.
        trace_id: gbTrace.traceId,
        span_id: gbTrace.spanId,
        parent_span: gbTrace.parentSpan,
        language: detectLanguage(frames),
        exception: {
          type:    (err && err.constructor && err.constructor.name) || typeof err,
          // El mensaje puede llevar un secreto clave=valor (el S2 de Python).
          message: redactarTexto((err && err.message) ? err.message : String(err)),
          origin:  origin
        },
        frames:   frames,
        process: {
          cwd:        cwd,
          project:    findProjectRoot(cwd),
          argv_forma: redactArgv(process.argv),
          runtime:    'node ' + process.version,
          pid:        process.pid,
          ppid:       ppid
        },
        traceback:      redactarTexto(rawStack),
        capture_method: 'hook'
      };
    }

    /**
     * Append record to crashes.jsonl. Swallows all errors silently.
     */
    function writeRecord(record) {
      try {
        if (!fs.existsSync(CRASHES_DIR)) {
          fs.mkdirSync(CRASHES_DIR, { recursive: true });
        }
        fs.appendFileSync(CRASHES_FILE, JSON.stringify(record) + '\n');
        // El aviso, como en Python: quien solo lee stderr tiene que saber que
        // hay captura. SIN id — el id se acuna al ingerir el buzon, no aqui, y
        // fabricar uno paralelo seria mentir. `gb last` es la puerta honesta.
        var quiet = String(process.env.GB_QUIET || '').toLowerCase();
        if (quiet === '' || quiet === '0' || quiet === 'false' ||
            quiet === 'no' || quiet === 'off') {
          var aviso = (process.env.GB_LANG === 'en')
            ? '[galaxy-brain] state captured -> gb last'
            : '[galaxy-brain] estado capturado -> gb last';
          process.stderr.write(aviso + '\n');
        }
      } catch (_) {
        // Silent fail — never mask the real crash.
      }
    }

    // ---------------------------------------------------------------
    // Locals por inspector — paridad con Python (medido 6-sep-2026)
    // ---------------------------------------------------------------
    // `uncaughtExceptionMonitor` llega con la pila YA desenrollada: ahi no hay
    // locals que leer. El protocolo inspector si los da: V8 pausa en la
    // excepcion que predice no-capturada (frames vivos), se leen los scopes y
    // se aparcan; el monitor los fusiona en el registro un instante despues.
    //
    // Coste medido en esta maquina (spike 6-sep-2026, 3 tiradas): computo puro
    // +0 ms; cada throw CAPTURADO paga ~2x (~18 µs extra). En un programa
    // normal no se nota; en codigo que usa excepciones como control de flujo,
    // si — por eso hay salida: GB_NO_JS_LOCALS=1 vuelve al hook sin estado.
    // Sin resume a proposito: medido que el proceso muere igual (exit 1, traza
    // intacta) y anadirlo seria codigo sin evidencia.

    // La MISMA lista que config.REDACT_PATTERNS de Python — una sonda en la
    // suite caza la deriva. Redaccion por NOMBRE, no por contenido: el mismo
    // coste asimetrico (un valor perdido < un token en disco).
    var REDACT = ['passwd', 'password', 'secret', 'token', 'api_key', 'apikey',
                  'auth', 'credential', 'private_key', 'session', 'cookie'];
    var REDACTADO = '<redactado>';

    function esSensible(nombre) {
      var bajo = String(nombre).toLowerCase();
      for (var i = 0; i < REDACT.length; i++) {
        if (bajo.indexOf(REDACT[i]) !== -1) return true;
      }
      return false;
    }

    // El S5/S2 de Python, replicado: un identificador sensible seguido de = o :
    // y su valor, en TEXTO libre. Hace falta porque String(function) en JS
    // vuelca el codigo fuente entero — un `var password = 'x'` dentro de una
    // funcion aparcada como local viajaba en claro (cazado por el test e2e).
    var RE_ASIGNACION = new RegExp(
      "(\\b\\w*(?:" + REDACT.join('|') + ")\\w*\\b)(['\"]?\\s*[:=]\\s*)" +
      "(\"[^\"]*\"|'[^']*'|[^\\s,)\\]}]+)", 'gi');

    function redactarTexto(texto) {
      try {
        return String(texto).replace(RE_ASIGNACION, function (_m, a, b) {
          return a + b + REDACTADO;
        });
      } catch (_) { return texto; }
    }

    function reprLocal(nombre, valor) {
      if (esSensible(nombre)) return REDACTADO;
      var texto = (valor === undefined) ? 'undefined' : String(valor);
      if (texto.length > 200) {
        texto = texto.slice(0, 200) + '...(+' + (texto.length - 200) + ' chars)';
      }
      return redactarTexto(texto);
    }

    var localsPendientes = null;   // frames del ultimo pause, del mas interno afuera

    (function armarLocals() {
      var quitar = String(process.env.GB_NO_JS_LOCALS || '').toLowerCase();
      if (quitar === '1' || quitar === 'true' || quitar === 'yes' || quitar === 'on') return;
      try {
        var inspector = require('inspector');
        var session = new inspector.Session();
        session.connect();

        // El inspector corre en el MISMO hilo: el callback de post llega antes
        // de devolver el control (comprobado en el spike; si un dia no llega,
        // res queda null y ese frame sale sin locals — degradacion, no fallo).
        function postSync(method, params) {
          var res = null;
          session.post(method, params || {}, function (e, r) { res = r; });
          return res;
        }

        // Lo que el frame de modulo CommonJS trae SIEMPRE y no dice nada del
        // fallo — el equivalente del filtro de dunders de Python.
        var RUIDO_MODULO = { exports: 1, require: 1, module: 1,
                             __filename: 1, __dirname: 1 };
        var maxLocals = parseInt(process.env.GB_MAX_LOCALS || '20', 10) || 20;

        session.on('Debugger.paused', function (msg) {
          try {
            var fuera = [];
            var callFrames = (msg.params && msg.params.callFrames) || [];
            for (var i = 0; i < callFrames.length && i < 20; i++) {
              var cf = callFrames[i];
              // La misma regla que Python (capture_all or not is_library): los
              // frames del runtime no llevan estado — sus locals son ruido de
              // Module._compile, no del fallo del usuario.
              if (cf.url && cf.url.indexOf('node:') === 0) {
                fuera.push({ 'function': cf.functionName || '<anonymous>',
                             line: cf.location ? cf.location.lineNumber + 1 : null,
                             locals: null });
                continue;
              }
              var scope = null;
              for (var j = 0; j < (cf.scopeChain || []).length; j++) {
                if (cf.scopeChain[j].type === 'local') { scope = cf.scopeChain[j]; break; }
              }
              var locals = null;
              if (scope && scope.object && scope.object.objectId) {
                var props = postSync('Runtime.getProperties',
                  { objectId: scope.object.objectId, ownProperties: true });
                if (props && props.result) {
                  locals = {};
                  var vistos = 0;
                  for (var k = 0; k < props.result.length; k++) {
                    var p = props.result[k];
                    if (RUIDO_MODULO[p.name]) continue;
                    if (vistos >= maxLocals) {
                      locals['...'] = '(mas variables, recortadas por GB_MAX_LOCALS)';
                      break;
                    }
                    var v = p.value;
                    locals[p.name] = reprLocal(p.name,
                      v ? (v.value !== undefined ? v.value : v.description) : undefined);
                    vistos++;
                  }
                  if (vistos === 0 && !locals['...']) locals = null;
                }
              }
              fuera.push({
                // lineNumber del inspector es 0-based; Error.stack es 1-based.
                'function': cf.functionName || '<anonymous>',
                line: cf.location ? cf.location.lineNumber + 1 : null,
                locals: locals
              });
            }
            localsPendientes = fuera;
          } catch (_) { /* sin locals; el registro sale igual */ }
        });

        postSync('Debugger.enable');
        postSync('Debugger.setPauseOnExceptions', { state: 'uncaught' });
      } catch (_) {
        // Sin inspector (embebido, o alguien lo tiene tomado): hook sin estado,
        // como antes del 6-sep. Nunca romper el programa observado.
      }
    })();

    /**
     * Fusiona los locals aparcados por el pause en los frames del registro.
     * Ambas pilas van del frame mas interno hacia afuera; se casa por posicion
     * verificando la linea (o el nombre) para no pegar estado al frame que no es.
     */
    function fusionarLocals(record) {
      var pendientes = localsPendientes;
      localsPendientes = null;   // un pause alimenta UN registro, nunca dos
      if (!pendientes) return;
      for (var i = 0; i < record.frames.length && i < pendientes.length; i++) {
        var f = record.frames[i];
        var p = pendientes[i];
        if (!p.locals) continue;
        if (f.line === p.line || f['function'] === p['function']) {
          f.locals = p.locals;
        }
      }
    }

    // ---------------------------------------------------------------
    // Install handlers
    // ---------------------------------------------------------------

    // `uncaughtExceptionMonitor`, NOT `uncaughtException`. Subscribing to the
    // monitor does NOT count as handling the exception, so Node proceeds with
    // its default behaviour: it prints the trace and exits 1, exactly as it
    // would with no hook installed.
    //
    // With `uncaughtException` you must re-throw for the trace to appear at all,
    // and that costs both things the observer must not change: the process exits
    // 7 instead of 1, and the hook's own frames land in the trace. A crash
    // console that alters how the program dies is not observing it.
    //
    // Measured 3/3 across sync, thrown and async crashes — see
    // docs/CONSOLA-MULTILENGUAJE.md.
    // TAMBIEN para las promesas, y no un listener de `unhandledRejection`:
    // TENER ese listener hace que Node de la promesa por manejada y el proceso
    // salga 0 en vez de 1 — medido el 6-sep-2026 (a pelo exit 1, con el
    // listener exit 0). El mismo error del ADR 0012, "engancharse donde se
    // maneja", que este hook ya pago una vez con uncaughtException. En modo
    // por defecto (>= Node 15) la promesa sin catch pasa por el monitor con
    // el origen en el SEGUNDO argumento, que es todo lo que se necesitaba.
    // Limite declarado: con --unhandled-rejections=warn no hay muerte y no hay
    // captura — se captura lo que mata al proceso.
    process.on('uncaughtExceptionMonitor', function gbUncaughtException(err, origen) {
      try {
        var record = buildRecord(
          err, origen === 'unhandledRejection' ? 'promise' : 'main');
        fusionarLocals(record);
        writeRecord(record);
      } catch (_) { /* silent */ }
    });

  } catch (_) {
    // The hook itself failed to initialize — stay silent, don't break
    // the user's program.
  }
})();
