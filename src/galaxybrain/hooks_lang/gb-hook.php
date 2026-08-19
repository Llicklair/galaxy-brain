<?php
/**
 * gb-hook.php ARREGLADO — OBSERVACION, no MANEJO.
 *
 * El original instalaba set_exception_handler + set_error_handler: los dos son
 * MANEJADORES. Instalarlos hace que PHP considere la excepcion atendida:
 * desaparece el "Fatal error: Uncaught ..." y el exit code 255 pasa a 0.
 *
 * Aqui solo se usa register_shutdown_function + error_get_last(): corre DESPUES
 * de que PHP ya haya reportado el fatal y salido por su camino normal. Observa.
 * No sustituye a nada, asi que ni el exit code ni la salida cambian.
 *
 * Install: php -d auto_prepend_file=/ruta/gb-hook.php  (o php.ini)
 */

(function () {
    $home = getenv('HOME') ?: getenv('USERPROFILE') ?: (
        getenv('HOMEDRIVE') && getenv('HOMEPATH')
            ? getenv('HOMEDRIVE') . getenv('HOMEPATH')
            : sys_get_temp_dir()
    );
    $crashesDir  = $home . DIRECTORY_SEPARATOR . '.galaxy-brain';
    $crashesFile = $crashesDir . DIRECTORY_SEPARATOR . 'crashes.jsonl';

    $NOMBRES = [
        E_ERROR => 'E_ERROR', E_WARNING => 'E_WARNING', E_PARSE => 'E_PARSE',
        E_NOTICE => 'E_NOTICE', E_CORE_ERROR => 'E_CORE_ERROR',
        E_CORE_WARNING => 'E_CORE_WARNING', E_COMPILE_ERROR => 'E_COMPILE_ERROR',
        E_COMPILE_WARNING => 'E_COMPILE_WARNING', E_USER_ERROR => 'E_USER_ERROR',
        E_RECOVERABLE_ERROR => 'E_RECOVERABLE_ERROR',
    ];

    $findProjectRoot = function (string $dir) {
        $cur = realpath($dir) ?: $dir;
        while (true) {
            if (file_exists($cur . DIRECTORY_SEPARATOR . '.git')) return $cur;
            $parent = dirname($cur);
            if ($parent === $cur) return null;
            $cur = $parent;
        }
    };

    $redactArgv = function (array $argv): array {
        $result = []; $count = count($argv);
        for ($i = 0; $i < $count; $i++) {
            $a = $argv[$i];
            if (preg_match('/^--?[a-zA-Z]/', $a)) {
                $eq = strpos($a, '=');
                if ($eq !== false) { $result[] = substr($a, 0, $eq + 1) . '<val>'; }
                else {
                    $result[] = $a;
                    if ($i + 1 < $count && !preg_match('/^--?[a-zA-Z]/', $argv[$i + 1])) {
                        $result[] = '<val>'; $i++;
                    }
                }
            } else { $result[] = $a; }
        }
        return $result;
    };

    register_shutdown_function(function () use (
        $crashesDir, $crashesFile, $NOMBRES, $findProjectRoot, $redactArgv
    ): void {
        try {
            $err = error_get_last();
            if ($err === null) return;

            $fatales = E_ERROR | E_PARSE | E_CORE_ERROR | E_COMPILE_ERROR
                     | E_USER_ERROR | E_RECOVERABLE_ERROR;
            if (!($err['type'] & $fatales)) return;

            $mensajeCrudo = $err['message'];
            $tipo    = $NOMBRES[$err['type']] ?? ('E_' . $err['type']);
            $mensaje = $mensajeCrudo;
            $origen  = 'shutdown';
            $frames  = [];

            // Excepcion no capturada: PHP la convierte en E_ERROR con el texto
            // "Uncaught <Clase>: <mensaje> in <fichero>:<linea>\nStack trace:\n..."
            if (preg_match('/^Uncaught\s+([\\\\A-Za-z_][\\\\A-Za-z0-9_]*)\s*:\s*(.*?)\s+in\s+(.+?):(\d+)\s*\nStack trace:\n(.*)$/s',
                           $mensajeCrudo, $m)) {
                $tipo    = $m[1];
                $mensaje = $m[2];
                $origen  = 'uncaught_exception';
                $ficheroLanza = $m[3];
                $lineaLanza   = (int) $m[4];
                $traza        = $m[5];

                $entradas = [];
                foreach (explode("\n", $traza) as $l) {
                    if (preg_match('/^#\d+\s+(.+)\((\d+)\):\s*(.+)$/', trim($l), $f)) {
                        $entradas[] = ['file' => $f[1], 'line' => (int) $f[2], 'function' => $f[3]];
                    } elseif (preg_match('/^#\d+\s+\{main\}$/', trim($l))) {
                        $entradas[] = ['file' => $ficheroLanza, 'line' => 0, 'function' => '{main}'];
                    }
                }
                // El punto exacto del lanzamiento: fichero:linea del mensaje, con
                // el nombre de la funcion que aparece en #0 (a quien se llamo).
                $frames[] = [
                    'file' => $ficheroLanza, 'line' => $lineaLanza, 'column' => 0,
                    'function' => $entradas[0]['function'] ?? '{main}',
                ];
                // La ultima entrada, "#N {main}", es el terminador de la traza de
                // PHP, no un frame: no se emite.
                $ultimo = count($entradas) - 1;
                for ($i = 0; $i < $ultimo; $i++) {
                    $e = $entradas[$i];
                    $frames[] = [
                        'file' => $e['file'], 'line' => $e['line'], 'column' => 0,
                        'function' => $entradas[$i + 1]['function'] ?? '{main}',
                    ];
                }
            }

            if (!$frames) {
                $frames[] = [
                    'file' => $err['file'] ?: '<unknown>', 'line' => (int) ($err['line'] ?? 0),
                    'column' => 0, 'function' => '<fatal>',
                ];
            }

            $cwd = getcwd() ?: '';
            $record = [
                'schema' => 2,
                'ts' => date('c'),
                'session_id' => getenv('GB_SESSION_ID') ?: 'unknown',
                'language' => 'php',
                'exception' => ['type' => $tipo, 'message' => $mensaje, 'origin' => $origen],
                'frames' => $frames,
                'process' => [
                    'cwd' => $cwd,
                    'project' => $findProjectRoot($cwd),
                    'argv_forma' => $redactArgv($_SERVER['argv'] ?? []),
                    'runtime' => 'php ' . PHP_VERSION,
                    'pid' => getmypid(),
                    'ppid' => function_exists('posix_getppid') ? posix_getppid() : null,
                ],
                'traceback' => $mensajeCrudo,
                'capture_method' => 'hook',
            ];

            if (!is_dir($crashesDir)) @mkdir($crashesDir, 0755, true);
            @file_put_contents(
                $crashesFile,
                json_encode($record, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n",
                FILE_APPEND | LOCK_EX
            );
        } catch (\Throwable $e) {
            // Silencio: si la captura falla, el programa sigue como si no existiera.
        }
    });
})();
