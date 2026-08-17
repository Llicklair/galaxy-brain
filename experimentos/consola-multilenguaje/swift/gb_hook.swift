// Galaxy Brain crash capture hook for Swift.
//
// Installs both NSSetUncaughtExceptionHandler (for ObjC exceptions) and
// sigaction handlers (for Swift runtime traps: SIGTRAP, SIGILL, SIGABRT).
//
// Build:
//   swiftc -emit-library -o libgb_hook.dylib gb_hook.swift
//
// Usage (macOS, when SIP allows):
//   DYLD_INSERT_LIBRARIES=/path/to/libgb_hook.dylib ./your_app
//
// Or link directly:
//   swiftc -L. -lgb_hook your_app.swift -o your_app
//   // then in your_app.swift: GbHook.install()
//
// LIMITATIONS:
//   - On macOS with System Integrity Protection (SIP) enabled,
//     DYLD_INSERT_LIBRARIES is stripped for system binaries and any
//     binary in a SIP-protected path. The library injection approach
//     only works for your own unsigned/ad-hoc-signed binaries.
//   - Signal handlers are very limited — they can only call
//     async-signal-safe functions (write, _exit, etc.). The signal
//     handler here writes a minimal record; rich capture is only
//     available for NSException.

import Foundation
#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#endif

// MARK: - Public API

public enum GbHook {

    /// Installs crash capture handlers. Call as early as possible in main().
    ///
    /// ```swift
    /// @main struct MyApp {
    ///     static func main() {
    ///         GbHook.install()
    ///         // ... your application code ...
    ///     }
    /// }
    /// ```
    public static func install() {
        prepareOutputPath()
        installExceptionHandler()
        installSignalHandlers()
    }
}

// MARK: - Output path (computed once, stored for signal handler)

/// Pre-computed path — signal handlers cannot allocate.
private var crashesPath: String = ""
private var crashesCPath: [CChar] = []

private func prepareOutputPath() {
    let home = ProcessInfo.processInfo.environment["HOME"]
        ?? ProcessInfo.processInfo.environment["USERPROFILE"]
        ?? NSHomeDirectory()
    let dir = "\(home)/.galaxy-brain"

    // Best-effort mkdir
    mkdir(dir, 0o755)

    crashesPath = "\(dir)/crashes.jsonl"
    crashesCPath = Array(crashesPath.utf8CString)
}

// MARK: - Project root detection

private func detectProjectRoot() -> String? {
    var url = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    while true {
        let gitURL = url.appendingPathComponent(".git")
        var isDir: ObjCBool = false
        if FileManager.default.fileExists(atPath: gitURL.path, isDirectory: &isDir) {
            return url.path
        }
        let parent = url.deletingLastPathComponent()
        if parent.path == url.path { return nil }
        url = parent
    }
}

// MARK: - JSON helpers

private func jsonEscape(_ s: String) -> String {
    var out = ""
    out.reserveCapacity(s.count)
    for c in s {
        switch c {
        case "\"": out += "\\\""
        case "\\": out += "\\\\"
        case "\n": out += "\\n"
        case "\r": out += "\\r"
        case "\t": out += "\\t"
        default:
            if c.asciiValue != nil && c.asciiValue! < 0x20 {
                out += String(format: "\\u%04x", c.asciiValue!)
            } else {
                out.append(c)
            }
        }
    }
    return out
}

private func jsonString(_ s: String?) -> String {
    guard let s = s else { return "null" }
    return "\"\(jsonEscape(s))\""
}

private func jsonStringArray(_ arr: [String]) -> String {
    let items = arr.map { "\"\(jsonEscape($0))\"" }
    return "[\(items.joined(separator: ","))]"
}

// MARK: - ISO 8601 timestamp

private func iso8601Now() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter.string(from: Date())
}

// MARK: - Write crash record (Foundation — safe for exception handler)

private func writeCrashRecord(_ json: String) {
    let dir = (crashesPath as NSString).deletingLastPathComponent
    try? FileManager.default.createDirectory(
        atPath: dir, withIntermediateDirectories: true)

    if let handle = FileHandle(forWritingAtPath: crashesPath) {
        handle.seekToEndOfFile()
        if let data = (json + "\n").data(using: .utf8) {
            handle.write(data)
        }
        handle.closeFile()
    } else {
        // File doesn't exist yet — create it.
        FileManager.default.createFile(
            atPath: crashesPath,
            contents: (json + "\n").data(using: .utf8))
    }
}

// MARK: - NSException handler

private func installExceptionHandler() {
    NSSetUncaughtExceptionHandler { exception in
        let name = exception.name.rawValue
        let reason = exception.reason ?? "unknown"
        let symbols = exception.callStackSymbols
        let project = detectProjectRoot()

        let record = [
            "{\"schema\":2",
            "\"ts\":\"\(jsonEscape(iso8601Now()))\"",
            "\"lang\":\"swift\"",
            "\"origin\":\"NSException\"",
            "\"project\":\(jsonString(project))",
            "\"error\":{\"type\":\"\(jsonEscape(name))\",\"message\":\"\(jsonEscape(reason))\"}",
            "\"backtrace\":\(jsonStringArray(symbols))",
            "}"
        ].joined(separator: ",")

        writeCrashRecord(record)
    }
}

// MARK: - Signal handlers (async-signal-safe only inside the handler)

/// Pre-built static buffers for signal names (signal handler cannot allocate).
private let signalNames: [Int32: String] = [
    SIGTRAP: "SIGTRAP",
    SIGILL:  "SIGILL",
    SIGABRT: "SIGABRT",
]

private let handledSignals: [Int32] = [SIGTRAP, SIGILL, SIGABRT]

private func installSignalHandlers() {
    for sig in handledSignals {
        var action = sigaction()
        #if canImport(Darwin)
        action.__sigaction_u.__sa_sigaction = signalHandler
        #elseif canImport(Glibc)
        action.__sigaction_handler = unsafeBitCast(
            signalHandler as @convention(c) (Int32, UnsafeMutablePointer<siginfo_t>?, UnsafeMutableRawPointer?) -> Void,
            to: sigaction.__Unnamed_union___sigaction_handler.self)
        #endif
        action.sa_flags = Int32(SA_SIGINFO | SA_RESETHAND)
        sigemptyset(&action.sa_mask)
        sigaction(sig, &action, nil)
    }
}

/// Signal handler — ONLY async-signal-safe calls allowed here.
/// We write a minimal JSON record using POSIX write() and pre-built data.
private let signalHandler: @convention(c) (Int32, UnsafeMutablePointer<siginfo_t>?, UnsafeMutableRawPointer?) -> Void = { sig, _, _ in
    // Build a minimal record using only stack-allocated / pre-computed data.
    let sigName: StaticString
    switch sig {
    case SIGTRAP: sigName = "SIGTRAP"
    case SIGILL:  sigName = "SIGILL"
    case SIGABRT: sigName = "SIGABRT"
    default:      sigName = "UNKNOWN"
    }

    // We can't use String here — format the record as raw bytes.
    // Use a fixed-size buffer on the stack.
    var buf: [UInt8] = Array(repeating: 0, count: 512)
    var pos = 0

    func append(_ s: StaticString) {
        s.withUTF8Buffer { ptr in
            for i in 0..<ptr.count where pos < buf.count - 1 {
                buf[pos] = ptr[i]
                pos += 1
            }
        }
    }

    func appendInt(_ n: Int32) {
        var tmp: [UInt8] = []
        var v = n < 0 ? -Int(n) : Int(n)
        if n < 0 { buf[pos] = UInt8(ascii: "-"); pos += 1 }
        if v == 0 { buf[pos] = UInt8(ascii: "0"); pos += 1; return }
        while v > 0 { tmp.append(UInt8(ascii: "0") + UInt8(v % 10)); v /= 10 }
        for i in stride(from: tmp.count - 1, through: 0, by: -1) where pos < buf.count - 1 {
            buf[pos] = tmp[i]
            pos += 1
        }
    }

    append("{\"schema\":2,\"lang\":\"swift\",\"origin\":\"signal\",\"error\":{\"type\":\"signal\",\"signal\":")
    appendInt(sig)
    append(",\"name\":\"")
    append(sigName)
    append("\"},\"pid\":")
    appendInt(getpid())
    append("}\n")

    // Write to file using POSIX open/write/close (async-signal-safe).
    crashesCPath.withUnsafeBufferPointer { pathPtr in
        let fd = open(pathPtr.baseAddress!, O_WRONLY | O_CREAT | O_APPEND, 0o644)
        if fd >= 0 {
            buf.withUnsafeBufferPointer { bufPtr in
                _ = write(fd, bufPtr.baseAddress!, pos)
            }
            close(fd)
        }
    }

    // Re-raise with default handler.
    signal(sig, SIG_DFL)
    raise(sig)
}
