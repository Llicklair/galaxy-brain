<?php
/**
 * gb-hook.php — PHP crash capture hook for galaxy-brain (schema v2)
 *
 * Install: php.ini → auto_prepend_file = /path/to/gb-hook.php
 *
 * Triple handler:
 *   1. set_exception_handler  — uncaught exceptions
 *   2. set_error_handler      — runtime errors (E_WARNING, E_NOTICE, etc.)
 *   3. register_shutdown_function + error_get_last() — fatal errors
 *
 * Zero external dependencies. Dormant until a crash occurs.
 * Appends a JSON record to ~/.galaxy-brain/crashes.jsonl.
 */

(function () {
    // Resolve home directory portably.
    $home = getenv('HOME') ?: getenv('USERPROFILE') ?: (
        getenv('HOMEDRIVE') && getenv('HOMEPATH')
            ? getenv('HOMEDRIVE') . getenv('HOMEPATH')
            : sys_get_temp_dir()
    );

    $crashesDir  = $home . DIRECTORY_SEPARATOR . '.galaxy-brain';
    $crashesFile = $crashesDir . DIRECTORY_SEPARATOR . 'crashes.jsonl';

    // ---------------------------------------------------------------
    // Helpers (closures to avoid polluting global namespace)
    // ---------------------------------------------------------------

    /**
     * Walk up from $dir looking for .git.
     */
    $findProjectRoot = function (string $dir): ?string {
        $cur = realpath($dir) ?: $dir;
        while (true) {
            if (file_exists($cur . DIRECTORY_SEPARATOR . '.git')) {
                return $cur;
            }
            $parent = dirname($cur);
            if ($parent === $cur) {
                return null;  // filesystem root
            }
            $cur = $parent;
        }
    };

    /**
     * Redact argv: keep flag names, replace values with <val>.
     */
    $redactArgv = function (array $argv): array {
        $result = [];
        $count  = count($argv);
        for ($i = 0; $i < $count; $i++) {
            $arg = $argv[$i];
            if (preg_match('/^--?[a-zA-Z]/', $arg)) {
                $eqPos = strpos($arg, '=');
                if ($eqPos !== false) {
                    $result[] = substr($arg, 0, $eqPos + 1) . '<val>';
                } else {
                    $result[] = $arg;
                    if ($i + 1 < $count && !preg_match('/^--?[a-zA-Z]/', $argv[$i + 1])) {
                        $result[] = '<val>';
                        $i++;
                    }
                }
            } else {
                $result[] = $arg;
            }
        }
        return $result;
    };

    /**
     * Parse a backtrace array (from debug_backtrace or Exception::getTrace)
     * into schema-v2 frames.
     */
    $parseTrace = function (array $trace): array {
        $frames = [];
        foreach ($trace as $frame) {
            $frames[] = [
                'file'     => $frame['file']     ?? '<internal>',
                'line'     => $frame['line']      ?? 0,
                'column'   => 0,  // PHP doesn't provide column info
                'function' => isset($frame['class'])
                    ? $frame['class'] . ($frame['type'] ?? '::') . ($frame['function'] ?? '')
                    : ($frame['function'] ?? '<unknown>'),
            ];
        }
        return $frames;
    };

    /**
     * Build a schema-v2 crash record.
     */
    $buildRecord = function (
        string $type,
        string $message,
        string $origin,
        array  $frames,
        string $rawTrace
    ) use ($findProjectRoot, $redactArgv): array {
        $cwd = getcwd() ?: '';
        $sessionId = getenv('GB_SESSION_ID') ?: 'unknown';
        // PHP doesn't have a built-in ppid function; use posix_getppid if available.
        $ppid = function_exists('posix_getppid') ? posix_getppid() : null;
        return [
            'schema'     => 2,
            'ts'         => date('c'),  // ISO 8601 with timezone
            'session_id' => $sessionId,
            'language'   => 'php',
            'exception'  => [
                'type'    => $type,
                'message' => $message,
                'origin'  => $origin,
            ],
            'frames'    => $frames,
            'process'   => [
                'cwd'        => $cwd,
                'project'    => $findProjectRoot($cwd),
                'argv_forma' => $redactArgv($_SERVER['argv'] ?? []),
                'runtime'    => 'php ' . PHP_VERSION,
                'pid'        => getmypid(),
                'ppid'       => $ppid,
            ],
            'traceback'      => $rawTrace,
            'capture_method' => 'hook',
        ];
    };

    /**
     * Append record to crashes.jsonl. Swallows all errors.
     */
    $writeRecord = function (array $record) use ($crashesDir, $crashesFile): void {
        try {
            if (!is_dir($crashesDir)) {
                @mkdir($crashesDir, 0755, true);
            }
            @file_put_contents(
                $crashesFile,
                json_encode($record, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n",
                FILE_APPEND | LOCK_EX
            );
        } catch (\Throwable $e) {
            // Silent fail.
        }
    };

    // Track whether we've already captured (avoid double-capture from
    // exception handler + shutdown function for the same error).
    $captured = false;

    // ---------------------------------------------------------------
    // 1. Uncaught exception handler
    // ---------------------------------------------------------------
    $previousExceptionHandler = set_exception_handler(
        function (\Throwable $ex) use (
            &$captured, $buildRecord, $parseTrace, $writeRecord,
            &$previousExceptionHandler
        ): void {
            if (!$captured) {
                $captured = true;
                try {
                    $frames   = $parseTrace($ex->getTrace());
                    $rawTrace = $ex->getTraceAsString();
                    $record   = $buildRecord(
                        get_class($ex),
                        $ex->getMessage(),
                        'exception',
                        $frames,
                        $rawTrace
                    );
                    $writeRecord($record);
                } catch (\Throwable $e) {
                    // Silent fail.
                }
            }

            // Chain to any previously installed handler.
            if (is_callable($previousExceptionHandler)) {
                ($previousExceptionHandler)($ex);
            }
        }
    );

    // ---------------------------------------------------------------
    // 2. Error handler (non-fatal errors: warnings, notices, etc.)
    //    Only capture errors that would be fatal or are severe.
    // ---------------------------------------------------------------
    $fatalErrorTypes = E_ERROR | E_PARSE | E_CORE_ERROR | E_COMPILE_ERROR | E_USER_ERROR;
    $previousErrorHandler = set_error_handler(
        function (
            int $errno,
            string $errstr,
            string $errfile = '',
            int $errline = 0
        ) use (
            &$captured, $fatalErrorTypes,
            $buildRecord, $parseTrace, $writeRecord,
            &$previousErrorHandler
        ): bool {
            // Only capture error types that are severe enough.
            if ($errno & $fatalErrorTypes) {
                if (!$captured) {
                    $captured = true;
                    try {
                        $frames   = $parseTrace(debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS));
                        $rawTrace = "Error [{$errno}] in {$errfile}:{$errline} — {$errstr}";
                        $record   = $buildRecord(
                            'E_' . $errno,
                            $errstr,
                            'error_handler',
                            $frames,
                            $rawTrace
                        );
                        $writeRecord($record);
                    } catch (\Throwable $e) {
                        // Silent fail.
                    }
                }
            }

            // Chain to previous handler or let PHP's default handle it.
            if (is_callable($previousErrorHandler)) {
                return ($previousErrorHandler)($errno, $errstr, $errfile, $errline);
            }
            return false;  // Let PHP's default error handler run.
        }
    );

    // ---------------------------------------------------------------
    // 3. Shutdown function — catches fatal errors that bypass the
    //    error handler (E_ERROR, E_PARSE, segfaults reported via
    //    error_get_last).
    // ---------------------------------------------------------------
    register_shutdown_function(
        function () use (
            &$captured, $fatalErrorTypes,
            $buildRecord, $writeRecord
        ): void {
            $error = error_get_last();
            if ($error === null) {
                return;
            }
            // Only capture fatal-class errors.
            if (!($error['type'] & $fatalErrorTypes)) {
                return;
            }
            if ($captured) {
                return;
            }
            $captured = true;
            try {
                $frames = [[
                    'file'     => $error['file'] ?? '<unknown>',
                    'line'     => $error['line'] ?? 0,
                    'column'   => 0,
                    'function' => '<fatal>',
                ]];
                $rawTrace = "Fatal [{$error['type']}] in {$error['file']}:{$error['line']} — {$error['message']}";
                $record   = $buildRecord(
                    'E_FATAL_' . $error['type'],
                    $error['message'],
                    'shutdown',
                    $frames,
                    $rawTrace
                );
                $writeRecord($record);
            } catch (\Throwable $e) {
                // Silent fail.
            }
        }
    );
})();
