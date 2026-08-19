// ──────────────────────────────────────────────────────────────────────────────
// Galaxy Brain .NET Startup Hook -- crash capture for C# / .NET 6+.
//
// Implements the .NET startup-hook convention: a static Initialize() method
// in a class named StartupHook (no namespace).  The runtime calls it before
// the app's Main().
//
// BUILD:
//   dotnet new classlib -n GbHook --no-restore
//   cp gb-hook.cs GbHook/StartupHook.cs   # replace the generated Class1.cs
//   cd GbHook && dotnet build -c Release
//   # Output: GbHook/bin/Release/net6.0/GbHook.dll  (adjust TFM as needed)
//
// INSTALL:
//   export DOTNET_STARTUP_HOOKS=/absolute/path/to/GbHook.dll
//
// Multiple hooks can be chained with the platform path separator (: or ;).
//
// No external NuGet dependencies -- only System.* APIs.
// ──────────────────────────────────────────────────────────────────────────────

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

/// <summary>
/// .NET startup hook entry point.  Must be a top-level (no namespace) class
/// named exactly "StartupHook" with a static void Initialize() method.
/// </summary>
internal class StartupHook
{
    private const int SchemaVersion = 2;
    private const string CrashesDir = ".galaxy-brain";
    private const string CrashesFile = "crashes.jsonl";

    // Patterns that suggest an environment variable or argument value is a secret.
    private static readonly Regex SecretPattern = new Regex(
        @"(?i)(password|passwd|secret|token|key|api.?key|credential|auth)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    /// <summary>
    /// Called by the .NET runtime before the application's Main() method.
    /// </summary>
    internal static void Initialize()
    {
        // ── Unhandled exceptions (sync) ──────────────────────────────────
        AppDomain.CurrentDomain.UnhandledException += (sender, args) =>
        {
            if (args.ExceptionObject is Exception ex)
            {
                try { CaptureAndWrite(ex); }
                catch
                {
                    // Swallow -- never let capture code mask the real crash.
                }
            }
        };

        // ── Unobserved Task exceptions (async / fire-and-forget) ─────────
        TaskScheduler.UnobservedTaskException += (sender, args) =>
        {
            if (args.Exception != null)
            {
                try
                {
                    // AggregateException may wrap multiple; capture each.
                    foreach (Exception inner in args.Exception.Flatten().InnerExceptions)
                    {
                        CaptureAndWrite(inner);
                    }
                }
                catch
                {
                    // Swallow.
                }
            }
        };
    }

    // ── Core capture ─────────────────────────────────────────────────────

    private static void CaptureAndWrite(Exception ex)
    {
        string json = BuildRecord(ex);
        WriteRecord(json);
    }

    private static string BuildRecord(Exception ex)
    {
        var sb = new StringBuilder(2048);
        sb.Append('{');

        JsonField(sb, "schema", SchemaVersion);
        JsonField(sb, "ts", DateTime.UtcNow.ToString("o")); // ISO 8601
        JsonField(sb, "language", "csharp");
        JsonField(sb, "hook", "dotnet-startup-hook");

        // Exception chain.
        sb.Append("\"exception\":");
        AppendExceptionChain(sb, ex);
        sb.Append(',');

        // Frames from the innermost exception (most useful trace).
        Exception root = ex;
        while (root.InnerException != null) root = root.InnerException;
        sb.Append("\"frames\":[");
        AppendFrames(sb, root);
        sb.Append("],");

        // Process info.
        sb.Append("\"process\":");
        AppendProcessInfo(sb);
        sb.Append(',');

        // Project root.
        string projectRoot = DetectProjectRoot();
        if (projectRoot != null)
        {
            JsonField(sb, "project_root", projectRoot);
        }

        // Remove trailing comma, close.
        if (sb[sb.Length - 1] == ',') sb.Length--;
        sb.Append('}');
        return sb.ToString();
    }

    // ── Exception chain ──────────────────────────────────────────────────

    private static void AppendExceptionChain(StringBuilder sb, Exception ex)
    {
        sb.Append('{');
        JsonField(sb, "type", ex.GetType().FullName ?? ex.GetType().Name);
        JsonField(sb, "message", ex.Message);

        if (ex.InnerException != null)
        {
            sb.Append("\"cause\":");
            AppendExceptionChain(sb, ex.InnerException);
        }
        else
        {
            if (sb[sb.Length - 1] == ',') sb.Length--;
        }
        sb.Append('}');
    }

    // ── Stack frames ─────────────────────────────────────────────────────
    //
    // Exception.StackTrace is a pre-formatted string.  We parse it into
    // structured frames.  The format is locale-dependent but the "at " /
    // "   at " prefix and " in <file>:line <n>" suffix are consistent
    // enough for practical use.

    private static readonly Regex FrameRegex = new Regex(
        @"^\s*at\s+(?<method>.+?)(?:\s+in\s+(?<file>.+?):line\s+(?<line>\d+))?\s*$",
        RegexOptions.Compiled | RegexOptions.Multiline);

    // Alternate format: " in <file>:line <n>" may also appear as
    // " en <file>:linea <n>" (Spanish) etc.  Fall back to the raw line.
    private static readonly Regex FrameRegexAlt = new Regex(
        @"^\s*at\s+(?<method>.+?)(?:\s+\w+\s+(?<file>[^:]+):.*?(?<line>\d+))?\s*$",
        RegexOptions.Compiled | RegexOptions.Multiline);

    private static void AppendFrames(StringBuilder sb, Exception ex)
    {
        string trace = ex.StackTrace;
        if (string.IsNullOrEmpty(trace)) return;

        bool first = true;
        foreach (Match m in FrameRegex.Matches(trace))
        {
            if (!first) sb.Append(',');
            first = false;

            sb.Append('{');
            JsonField(sb, "method", m.Groups["method"].Value);
            if (m.Groups["file"].Success)
                JsonField(sb, "file", m.Groups["file"].Value);
            if (m.Groups["line"].Success)
                JsonField(sb, "line", int.Parse(m.Groups["line"].Value));

            if (sb[sb.Length - 1] == ',') sb.Length--;
            sb.Append('}');
        }

        // Fallback: if regex matched nothing, try alternate pattern.
        if (first)
        {
            foreach (Match m in FrameRegexAlt.Matches(trace))
            {
                if (!first) sb.Append(',');
                first = false;

                sb.Append('{');
                JsonField(sb, "method", m.Groups["method"].Value);
                if (m.Groups["file"].Success)
                    JsonField(sb, "file", m.Groups["file"].Value);
                if (m.Groups["line"].Success)
                    JsonField(sb, "line", int.Parse(m.Groups["line"].Value));

                if (sb[sb.Length - 1] == ',') sb.Length--;
                sb.Append('}');
            }
        }
    }

    // ── Process info ─────────────────────────────────────────────────────

    private static void AppendProcessInfo(StringBuilder sb)
    {
        sb.Append('{');
        JsonField(sb, "dotnet_version", Environment.Version.ToString());
        JsonField(sb, "os", RuntimeInformation.OSDescription);
        JsonField(sb, "arch", RuntimeInformation.OSArchitecture.ToString());
        JsonField(sb, "pid", Environment.ProcessId);

        // Command line, redacted.
        string[] args = Environment.GetCommandLineArgs();
        if (args != null && args.Length > 0)
        {
            JsonField(sb, "command", RedactArgv(args));
        }

        if (sb[sb.Length - 1] == ',') sb.Length--;
        sb.Append('}');
    }

    // ── Project root detection ───────────────────────────────────────────

    private static string DetectProjectRoot()
    {
        try
        {
            string dir = Directory.GetCurrentDirectory();
            while (!string.IsNullOrEmpty(dir))
            {
                if (Directory.Exists(Path.Combine(dir, ".git")))
                    return dir;
                string parent = Path.GetDirectoryName(dir);
                if (parent == dir) break; // filesystem root
                dir = parent;
            }
        }
        catch
        {
            // Permission or I/O issue -- give up silently.
        }
        return null;
    }

    // ── Redaction ────────────────────────────────────────────────────────

    private static string RedactArgv(string[] args)
    {
        var sb = new StringBuilder();
        for (int i = 0; i < args.Length; i++)
        {
            if (i > 0) sb.Append(' ');
            string arg = args[i];

            // Check for key=value patterns where key looks secret.
            int eq = arg.IndexOf('=');
            if (eq > 0)
            {
                string key = arg.Substring(0, eq);
                if (SecretPattern.IsMatch(key))
                {
                    sb.Append(key).Append("=[REDACTED]");
                    continue;
                }
            }
            // Check for --secret <value> pattern (next arg is the value).
            if (SecretPattern.IsMatch(arg) && i + 1 < args.Length && !args[i + 1].StartsWith("-"))
            {
                sb.Append(arg).Append(" [REDACTED]");
                i++; // skip the value
                continue;
            }
            sb.Append(arg);
        }
        return sb.ToString();
    }

    // ── File I/O ─────────────────────────────────────────────────────────

    private static readonly object WriteLock = new object();

    private static void WriteRecord(string json)
    {
        try
        {
            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            string dir = Path.Combine(home, CrashesDir);
            Directory.CreateDirectory(dir);
            string file = Path.Combine(dir, CrashesFile);

            // Lock to avoid interleaved writes from concurrent threads.
            lock (WriteLock)
            {
                File.AppendAllText(file, json + Environment.NewLine, Encoding.UTF8);
            }
        }
        catch
        {
            // Swallow -- never crash the app because of our hook.
        }
    }

    // ── JSON helpers (no deps) ───────────────────────────────────────────

    private static void JsonField(StringBuilder sb, string key, string value)
    {
        sb.Append('"').Append(EscapeJson(key)).Append("\":");
        if (value == null)
            sb.Append("null");
        else
            sb.Append('"').Append(EscapeJson(value)).Append('"');
        sb.Append(',');
    }

    private static void JsonField(StringBuilder sb, string key, int value)
    {
        sb.Append('"').Append(EscapeJson(key)).Append("\":").Append(value).Append(',');
    }

    private static string EscapeJson(string s)
    {
        if (s == null) return "";
        var sb = new StringBuilder(s.Length);
        foreach (char c in s)
        {
            switch (c)
            {
                case '"':  sb.Append("\\\""); break;
                case '\\': sb.Append("\\\\"); break;
                case '\n': sb.Append("\\n");  break;
                case '\r': sb.Append("\\r");  break;
                case '\t': sb.Append("\\t");  break;
                default:
                    if (c < 0x20)
                        sb.AppendFormat("\\u{0:x4}", (int)c);
                    else
                        sb.Append(c);
                    break;
            }
        }
        return sb.ToString();
    }
}
