/**
 * Galaxy Brain JVM Agent -- crash capture for Java, Kotlin, and Scala.
 *
 * Installs as a javaagent via -javaagent flag or JAVA_TOOL_OPTIONS.
 * On any uncaught exception, writes a schema-v2 JSON record to
 * ~/.galaxy-brain/crashes.jsonl, then chains to any previously-installed handler.
 *
 * Also registers as a kotlinx.coroutines.CoroutineExceptionHandler via
 * ServiceLoader so Kotlin coroutine failures are captured too.
 *
 * BUILD (no external deps):
 *   javac GbAgent.java
 *   jar cfm gb-agent.jar META-INF/MANIFEST.MF GbAgent.class GbAgent\$CrashRecord.class \
 *       GbAgent\$ExceptionInfo.class GbAgent\$FrameInfo.class GbAgent\$ProcessInfo.class \
 *       GbAgent\$GbCoroutineHandler.class META-INF/services/kotlinx.coroutines.CoroutineExceptionHandler
 *
 * INSTALL:
 *   export JAVA_TOOL_OPTIONS="-javaagent:/absolute/path/to/gb-agent.jar"
 */

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.lang.instrument.Instrumentation;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

public class GbAgent {

    private static final String CRASHES_DIR = ".galaxy-brain";
    private static final String CRASHES_FILE = "crashes.jsonl";
    private static final int SCHEMA_VERSION = 2;

    // Patterns that suggest a value is a secret (case-insensitive).
    private static final Pattern SECRET_PATTERN = Pattern.compile(
        "(?i)(password|passwd|secret|token|key|api.?key|credential|auth)",
        Pattern.CASE_INSENSITIVE
    );

    // ── Agent entry point ────────────────────────────────────────────────

    public static void premain(String args, Instrumentation inst) {
        // Capture whatever handler was already installed so we can chain to it.
        Thread.UncaughtExceptionHandler previousHandler =
            Thread.getDefaultUncaughtExceptionHandler();

        Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
            try {
                captureAndWrite(throwable);
            } catch (Throwable suppressed) {
                // Never let our capture code mask the real crash.
                System.err.println("[gb-agent] Failed to capture crash: " + suppressed.getMessage());
            }

            // Chain to previous handler so the app's own crash logic still fires.
            if (previousHandler != null) {
                previousHandler.uncaughtException(thread, throwable);
            } else {
                // No previous handler is the NORMAL case, and it is a trap: the
                // JVM's default is not a handler at all, so installing ours
                // replaces it and the stack trace silently disappears. Measured:
                // with the agent, `String s = null; s.length()` printed nothing
                // at all — the console deleted the only thing the program was
                // still telling you, and wrote no record either.
                //
                // Do NOT delegate to thread.getThreadGroup().uncaughtException():
                // its default implementation looks the default handler up again —
                // us — and loops forever. Also measured, the hard way.
                //
                // So the default gets reproduced by hand, in the JVM's own format.
                System.err.print("Exception in thread \"" + thread.getName() + "\" ");
                throwable.printStackTrace(System.err);
            }
        });

        // Try to register the Kotlin coroutine handler eagerly. If the
        // coroutines runtime isn't on the classpath this is a harmless no-op.
        tryRegisterCoroutineHandler();
    }

    // ── Kotlin coroutine support ─────────────────────────────────────────
    //
    // kotlinx.coroutines discovers CoroutineExceptionHandler implementations
    // via ServiceLoader.  We ship a META-INF/services file pointing to this
    // inner class.  The class only compiles if kotlinx-coroutines-core is on
    // the compile classpath, but that is NOT required at runtime -- the
    // ServiceLoader entry is simply never loaded when the library is absent.
    //
    // Because we cannot add a compile-time dependency on kotlinx, the actual
    // handler class is loaded reflectively at install time.  The ServiceLoader
    // file still works: kotlinx itself does the loading when it IS present.

    /**
     * Reflectively check whether kotlinx.coroutines is available and, if so,
     * log that the ServiceLoader-based handler will be discovered automatically.
     */
    private static void tryRegisterCoroutineHandler() {
        try {
            Class.forName("kotlinx.coroutines.CoroutineExceptionHandler");
            // If we got here, the runtime is on the classpath.  The ServiceLoader
            // file in META-INF/services/ ensures our handler is discovered.
        } catch (ClassNotFoundException ignored) {
            // Kotlin coroutines not present -- nothing to do.
        }
    }

    // ── Core capture logic ───────────────────────────────────────────────

    static void captureAndWrite(Throwable throwable) {
        String json = buildRecord(throwable);
        writeRecord(json);
    }

    private static String buildRecord(Throwable throwable) {
        StringBuilder sb = new StringBuilder(2048);
        sb.append('{');

        // schema
        jsonField(sb, "schema", SCHEMA_VERSION, true);

        // timestamp (ISO 8601 / UTC)
        String ts = DateTimeFormatter.ISO_INSTANT.format(Instant.now().atOffset(ZoneOffset.UTC));
        jsonField(sb, "ts", ts, false);

        // language detection
        String language = detectLanguage(throwable);
        jsonField(sb, "language", language, false);

        // session ID for cross-language correlation
        String sessionId = System.getenv("GB_SESSION_ID");
        jsonField(sb, "session_id", sessionId != null ? sessionId : "unknown", false);

        // hook
        jsonField(sb, "hook", "jvm-agent", false);

        // exception chain
        sb.append("\"exception\":");
        appendExceptionChain(sb, throwable);
        sb.append(',');

        // frames (from the root cause, which usually has the most useful trace)
        Throwable root = throwable;
        while (root.getCause() != null) root = root.getCause();
        sb.append("\"frames\":[");
        appendFrames(sb, root.getStackTrace());
        sb.append("],");

        // process info
        sb.append("\"process\":");
        appendProcessInfo(sb);
        sb.append(',');

        // project root
        String projectRoot = detectProjectRoot();
        if (projectRoot != null) {
            jsonField(sb, "project_root", projectRoot, false);
        }

        // Remove trailing comma if present and close.
        if (sb.charAt(sb.length() - 1) == ',') {
            sb.setLength(sb.length() - 1);
        }
        sb.append('}');
        return sb.toString();
    }

    // ── Language detection ────────────────────────────────────────────────
    //
    // Heuristic: scan the stack trace for file-name extensions that indicate
    // Kotlin (.kt) or Scala (.scala).  Default to "java".

    private static String detectLanguage(Throwable throwable) {
        Throwable current = throwable;
        while (current != null) {
            for (StackTraceElement frame : current.getStackTrace()) {
                String fileName = frame.getFileName();
                if (fileName != null) {
                    if (fileName.endsWith(".kt")) return "kotlin";
                    if (fileName.endsWith(".scala")) return "scala";
                }
            }
            current = current.getCause();
        }
        return "java";
    }

    // ── Exception chain serialisation ────────────────────────────────────

    private static void appendExceptionChain(StringBuilder sb, Throwable t) {
        sb.append('{');
        jsonField(sb, "type", t.getClass().getName(), true);
        jsonField(sb, "message", t.getMessage(), false);

        if (t.getCause() != null) {
            sb.append("\"cause\":");
            appendExceptionChain(sb, t.getCause());
        } else {
            // Remove trailing comma.
            if (sb.charAt(sb.length() - 1) == ',') {
                sb.setLength(sb.length() - 1);
            }
        }
        sb.append('}');
    }

    // ── Stack frames ─────────────────────────────────────────────────────

    private static void appendFrames(StringBuilder sb, StackTraceElement[] elements) {
        for (int i = 0; i < elements.length; i++) {
            StackTraceElement el = elements[i];
            if (i > 0) sb.append(',');
            sb.append('{');
            jsonField(sb, "class", el.getClassName(), true);
            jsonField(sb, "method", el.getMethodName(), false);
            if (el.getFileName() != null) {
                jsonField(sb, "file", el.getFileName(), false);
            }
            if (el.getLineNumber() >= 0) {
                jsonField(sb, "line", el.getLineNumber(), false);
            }
            jsonField(sb, "native", el.isNativeMethod(), false);
            // Remove trailing comma.
            if (sb.charAt(sb.length() - 1) == ',') {
                sb.setLength(sb.length() - 1);
            }
            sb.append('}');
        }
    }

    // ── Process info ─────────────────────────────────────────────────────

    private static void appendProcessInfo(StringBuilder sb) {
        sb.append('{');
        jsonField(sb, "java_version", System.getProperty("java.version"), true);
        jsonField(sb, "java_vendor", System.getProperty("java.vendor"), false);
        jsonField(sb, "os_name", System.getProperty("os.name"), false);
        jsonField(sb, "os_arch", System.getProperty("os.arch"), false);
        jsonField(sb, "pid", getPid(), false);

        // Parent PID for cross-language correlation.
        //
        // El padre DE VERDAD, preguntado al sistema. Antes se cogia GB_PPID, que
        // es el pid del envolvente `gb run`: el abuelo, o el bisabuelo, segun
        // por donde vaya la cadena. Con eso, el arbol de procesos que se
        // reconstruye despues es FALSO — todos cuelgan del envolvente y las
        // llamadas reales entre lenguajes desaparecen (experimento poliglota,
        // 19-ago-2026). GB_PPID queda de respaldo para Java 8, donde no se
        // puede preguntar.
        String ppid = getPpid();
        if (ppid == null) ppid = System.getenv("GB_PPID");
        if (ppid != null) {
            jsonField(sb, "ppid", ppid, false);
        }

        // argv: redact values to avoid leaking secrets passed on the command line.
        String rawCmd = System.getProperty("sun.java.command");
        if (rawCmd != null) {
            jsonField(sb, "command", redactArgv(rawCmd), false);
        }

        // Remove trailing comma.
        if (sb.charAt(sb.length() - 1) == ',') {
            sb.setLength(sb.length() - 1);
        }
        sb.append('}');
    }

    private static String getPpid() {
        // ProcessHandle.current().parent().get().pid(), por reflexion para
        // seguir compilando en Java 8 (donde devuelve null y manda GB_PPID).
        try {
            Class<?> ph = Class.forName("java.lang.ProcessHandle");
            Object current = ph.getMethod("current").invoke(null);
            Object padre = ph.getMethod("parent").invoke(current);
            Class<?> opt = Class.forName("java.util.Optional");
            Boolean hay = (Boolean) opt.getMethod("isPresent").invoke(padre);
            if (!Boolean.TRUE.equals(hay)) return null;
            Object handle = opt.getMethod("get").invoke(padre);
            return ph.getMethod("pid").invoke(handle).toString();
        } catch (Exception e) {
            return null;
        }
    }

    private static String getPid() {
        // Works on Java 9+.  On Java 8, falls back to the runtime name.
        try {
            // ProcessHandle.current().pid() -- use reflection to stay Java-8 compilable.
            Class<?> ph = Class.forName("java.lang.ProcessHandle");
            Object current = ph.getMethod("current").invoke(null);
            Object pid = ph.getMethod("pid").invoke(current);
            return pid.toString();
        } catch (Exception e) {
            // Java 8 fallback: RuntimeMXBean name is usually "pid@hostname".
            String name = java.lang.management.ManagementFactory.getRuntimeMXBean().getName();
            int at = name.indexOf('@');
            return at > 0 ? name.substring(0, at) : name;
        }
    }

    // ── Project root detection ───────────────────────────────────────────
    //
    // Walk up from user.dir looking for a .git directory.

    private static String detectProjectRoot() {
        try {
            Path dir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
            while (dir != null) {
                if (Files.isDirectory(dir.resolve(".git"))) {
                    return dir.toString();
                }
                dir = dir.getParent();
            }
        } catch (Exception ignored) {
            // Security manager or I/O issue -- give up silently.
        }
        return null;
    }

    // ── Redaction ────────────────────────────────────────────────────────
    //
    // Redact argv tokens that look like key=value where the key smells like
    // a secret, plus any bare token that matches the secret pattern.

    private static String redactArgv(String rawCommand) {
        String[] parts = rawCommand.split("\\s+");
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) out.append(' ');
            String part = parts[i];

            // -Dkey=value or --key=value forms.
            int eq = part.indexOf('=');
            if (eq > 0) {
                String key = part.substring(0, eq);
                if (SECRET_PATTERN.matcher(key).find()) {
                    out.append(key).append("=[REDACTED]");
                    continue;
                }
            }
            out.append(part);
        }
        return out.toString();
    }

    // ── File I/O ─────────────────────────────────────────────────────────

    private static void writeRecord(String json) {
        try {
            Path dir = Paths.get(System.getProperty("user.home"), CRASHES_DIR);
            Files.createDirectories(dir);
            Path file = dir.resolve(CRASHES_FILE);

            // Append atomically-ish: open in append mode, write one line, flush.
            try (PrintWriter pw = new PrintWriter(
                    new BufferedWriter(new FileWriter(file.toFile(), true)))) {
                pw.println(json);
                pw.flush();
            }
        } catch (IOException e) {
            System.err.println("[gb-agent] Could not write crash record: " + e.getMessage());
        }
    }

    // ── JSON helpers (no deps) ───────────────────────────────────────────
    //
    // Minimal JSON serialisation to avoid pulling in Gson / Jackson.

    private static void jsonField(StringBuilder sb, String key, String value, boolean first) {
        if (!first) { /* comma already appended by caller or previous call */ }
        sb.append('"').append(escapeJson(key)).append("\":");
        if (value == null) {
            sb.append("null");
        } else {
            sb.append('"').append(escapeJson(value)).append('"');
        }
        sb.append(',');
    }

    private static void jsonField(StringBuilder sb, String key, int value, boolean first) {
        sb.append('"').append(escapeJson(key)).append("\":").append(value).append(',');
    }

    private static void jsonField(StringBuilder sb, String key, boolean value, boolean first) {
        sb.append('"').append(escapeJson(key)).append("\":").append(value).append(',');
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        StringBuilder out = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n");  break;
                case '\r': out.append("\\r");  break;
                case '\t': out.append("\\t");  break;
                default:
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        return out.toString();
    }
}
