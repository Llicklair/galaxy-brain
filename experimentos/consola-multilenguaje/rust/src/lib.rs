//! Galaxy Brain crash capture hook for Rust.
//!
//! Installs a panic hook that writes a JSON crash record (schema v2)
//! to `~/.galaxy-brain/crashes.jsonl`. Chains with any previously
//! installed hook so existing behaviour is preserved.
//!
//! # Usage
//! ```rust
//! fn main() {
//!     gb_hook::install();
//!     // ... your application code ...
//! }
//! ```
//!
//! No external crate dependencies — std only.

use std::backtrace::Backtrace;
use std::env;
use std::fs;
use std::io::Write;
use std::panic::{self, PanicHookInfo};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

/// Installs the Galaxy Brain panic hook.
///
/// The hook captures panic information, writes it as a JSON record to
/// `~/.galaxy-brain/crashes.jsonl`, and then forwards the panic to
/// whichever hook was previously installed (the default or a custom one).
pub fn install() {
    let previous_hook = panic::take_hook();

    panic::set_hook(Box::new(move |info: &PanicHookInfo<'_>| {
        // Best-effort crash capture — never let the hook itself panic.
        let _ = capture_crash(info);

        // Chain to the previous hook.
        previous_hook(info);
    }));
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

fn capture_crash(info: &PanicHookInfo<'_>) -> Result<(), Box<dyn std::error::Error>> {
    let message = extract_message(info);
    let (file, line, column) = extract_location(info);
    let backtrace = Backtrace::force_capture().to_string();
    let timestamp = iso8601_now();
    let project_root = detect_project_root().unwrap_or_default();

    let record = format!(
        concat!(
            "{{",
            "\"schema\":2,",
            "\"ts\":\"{ts}\",",
            "\"lang\":\"rust\",",
            "\"origin\":\"panic\",",
            "\"project\":\"{project}\",",
            "\"error\":{{\"type\":\"panic\",\"message\":{msg}}},",
            "\"location\":{{\"file\":{file},\"line\":{line},\"column\":{col}}},",
            "\"backtrace\":{bt}",
            "}}"
        ),
        ts = timestamp,
        project = escape_json_string(&project_root),
        msg = json_string_or_null(&message),
        file = json_string_or_null(&file),
        line = line.map_or("null".to_string(), |l| l.to_string()),
        col = column.map_or("null".to_string(), |c| c.to_string()),
        bt = to_json_string(&backtrace),
    );

    let crashes_path = crashes_file_path()?;
    if let Some(parent) = crashes_path.parent() {
        fs::create_dir_all(parent)?;
    }

    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(crashes_path)?;
    writeln!(file, "{}", record)?;

    Ok(())
}

fn extract_message(info: &PanicHookInfo<'_>) -> Option<String> {
    let payload = info.payload();
    if let Some(s) = payload.downcast_ref::<&str>() {
        Some((*s).to_string())
    } else if let Some(s) = payload.downcast_ref::<String>() {
        Some(s.clone())
    } else {
        None
    }
}

fn extract_location(info: &PanicHookInfo<'_>) -> (Option<String>, Option<u32>, Option<u32>) {
    match info.location() {
        Some(loc) => (
            Some(loc.file().to_string()),
            Some(loc.line()),
            Some(loc.column()),
        ),
        None => (None, None, None),
    }
}

fn detect_project_root() -> Option<String> {
    let mut dir = env::current_dir().ok()?;
    loop {
        if dir.join(".git").exists() {
            return Some(dir.to_string_lossy().into_owned());
        }
        if !dir.pop() {
            return None;
        }
    }
}

fn crashes_file_path() -> Result<PathBuf, Box<dyn std::error::Error>> {
    let home = home_dir().ok_or("could not determine home directory")?;
    Ok(home.join(".galaxy-brain").join("crashes.jsonl"))
}

fn home_dir() -> Option<PathBuf> {
    env::var_os("HOME")
        .or_else(|| env::var_os("USERPROFILE"))
        .map(PathBuf::from)
}

fn iso8601_now() -> String {
    let dur = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = dur.as_secs();

    // Compute UTC date-time components (no chrono needed).
    let days = secs / 86400;
    let time_of_day = secs % 86400;
    let hours = time_of_day / 3600;
    let minutes = (time_of_day % 3600) / 60;
    let seconds = time_of_day % 60;

    // Days since 1970-01-01 to Y-M-D (simplified Rata Die).
    let (year, month, day) = civil_from_days(days as i64);

    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        year, month, day, hours, minutes, seconds
    )
}

/// Convert days since 1970-01-01 to (year, month, day).
/// Algorithm from Howard Hinnant's `civil_from_days`.
fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = (z - era * 146097) as u32;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

fn escape_json_string(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out
}

fn to_json_string(s: &str) -> String {
    format!("\"{}\"", escape_json_string(s))
}

fn json_string_or_null(opt: &Option<String>) -> String {
    match opt {
        Some(s) => to_json_string(s),
        None => "null".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_escape_json_string() {
        assert_eq!(escape_json_string("hello"), "hello");
        assert_eq!(escape_json_string("he\"llo"), "he\\\"llo");
        assert_eq!(escape_json_string("line\nnew"), "line\\nnew");
    }

    #[test]
    fn test_iso8601_now_format() {
        let ts = iso8601_now();
        assert!(ts.ends_with('Z'));
        assert_eq!(ts.len(), 20); // YYYY-MM-DDTHH:MM:SSZ
    }

    #[test]
    fn test_civil_from_days_epoch() {
        let (y, m, d) = civil_from_days(0);
        assert_eq!((y, m, d), (1970, 1, 1));
    }
}
