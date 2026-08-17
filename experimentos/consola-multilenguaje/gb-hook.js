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

;(function gbHookInit() {
  // Wrap the entire hook so a bug here never masks the real error.
  try {
    var fs   = require('fs');
    var path = require('path');
    var os   = require('os');

    var CRASHES_DIR  = path.join(os.homedir(), '.galaxy-brain');
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
        language: detectLanguage(frames),
        exception: {
          type:    (err && err.constructor && err.constructor.name) || typeof err,
          message: (err && err.message) ? err.message : String(err),
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
        traceback:      rawStack,
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
      } catch (_) {
        // Silent fail — never mask the real crash.
      }
    }

    // ---------------------------------------------------------------
    // Install handlers
    // ---------------------------------------------------------------

    process.on('uncaughtException', function gbUncaughtException(err) {
      try {
        writeRecord(buildRecord(err, 'main'));
      } catch (_) { /* silent */ }
      // Set exit code and let Node die naturally.
      process.exitCode = 1;
      // Re-throw so the default handler prints the trace and exits.
      throw err;
    });

    process.on('unhandledRejection', function gbUnhandledRejection(reason) {
      try {
        var err = (reason instanceof Error) ? reason : new Error(String(reason));
        writeRecord(buildRecord(err, 'promise'));
      } catch (_) { /* silent */ }
      // Don't force exit — match Node.js default behavior:
      // Node >= 15 terminates on unhandled rejection by default;
      // Node < 15 only warns.  Either way, we let the runtime decide.
    });

  } catch (_) {
    // The hook itself failed to initialize — stay silent, don't break
    // the user's program.
  }
})();
