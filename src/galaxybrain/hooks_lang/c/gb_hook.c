/*
 * Galaxy Brain crash capture hook for C — shared library.
 *
 * Installs sigaction handlers for fatal signals (SIGSEGV, SIGABRT, SIGFPE,
 * SIGBUS, SIGILL) at load time via __attribute__((constructor)).
 *
 * IMPORTANT: The signal handler uses ONLY async-signal-safe functions
 * (write, _exit, open, close). No malloc, no printf, no fopen, no stdio.
 *
 * Build:
 *   gcc -shared -fPIC -o gb-hook.so gb_hook.c -rdynamic
 *
 * Install:
 *   LD_PRELOAD=/path/to/gb-hook.so ./your_program
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>   /* getenv — faltaba: no compilaba ni en Linux */
#include <string.h>
#include <sys/stat.h>  /* mkdir  — idem */
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

/* glibc extensions — best-effort backtrace */
#ifdef __GLIBC__
#include <execinfo.h>
#define GB_HAS_BACKTRACE 1
#else
#define GB_HAS_BACKTRACE 0
#endif

/* -----------------------------------------------------------------------
 * Pre-allocated static buffer (signal-safe — no heap)
 * ----------------------------------------------------------------------- */

#define GB_BUF_SIZE   8192
#define GB_PATH_SIZE  1024
#define GB_BT_DEPTH   64

static char  gb_buf[GB_BUF_SIZE];
static char  gb_path[GB_PATH_SIZE];
static int   gb_path_ready = 0;

/* -----------------------------------------------------------------------
 * Tiny async-signal-safe helpers
 * ----------------------------------------------------------------------- */

static int gb_strlen(const char *s) {
    int n = 0;
    while (s[n]) n++;
    return n;
}

static void gb_strcpy(char *dst, const char *src, int max) {
    int i = 0;
    while (src[i] && i < max - 1) { dst[i] = src[i]; i++; }
    dst[i] = '\0';
}

static void gb_strcat(char *dst, const char *src, int max) {
    int dlen = gb_strlen(dst);
    int i = 0;
    while (src[i] && dlen + i < max - 1) {
        dst[dlen + i] = src[i];
        i++;
    }
    dst[dlen + i] = '\0';
}

/* Append an integer as decimal string. */
static void gb_strcat_int(char *dst, long val, int max) {
    char tmp[24];
    int neg = 0;
    int i = 0;

    if (val < 0) { neg = 1; val = -val; }
    if (val == 0) { tmp[i++] = '0'; }
    while (val > 0 && i < 22) {
        tmp[i++] = '0' + (val % 10);
        val /= 10;
    }
    if (neg) tmp[i++] = '-';

    /* reverse into dst */
    int dlen = gb_strlen(dst);
    int j;
    for (j = i - 1; j >= 0 && dlen < max - 1; j--, dlen++) {
        dst[dlen] = tmp[j];
    }
    dst[dlen] = '\0';
}

/* Append a 2-digit zero-padded number. */
static void gb_strcat_2d(char *dst, int val, int max) {
    char tmp[3];
    tmp[0] = '0' + (val / 10) % 10;
    tmp[1] = '0' + val % 10;
    tmp[2] = '\0';
    gb_strcat(dst, tmp, max);
}

/* Append a 4-digit zero-padded number. */
static void gb_strcat_4d(char *dst, int val, int max) {
    char tmp[5];
    tmp[0] = '0' + (val / 1000) % 10;
    tmp[1] = '0' + (val / 100) % 10;
    tmp[2] = '0' + (val / 10) % 10;
    tmp[3] = '0' + val % 10;
    tmp[4] = '\0';
    gb_strcat(dst, tmp, max);
}

static const char *gb_signal_name(int sig) {
    switch (sig) {
        case SIGSEGV: return "SIGSEGV";
        case SIGABRT: return "SIGABRT";
        case SIGFPE:  return "SIGFPE";
#ifdef SIGBUS
        case SIGBUS:  return "SIGBUS";
#endif
        case SIGILL:  return "SIGILL";
        default:      return "UNKNOWN";
    }
}

/* JSON-escape a string into dst (caller must ensure enough space). */
static void gb_json_escape(char *dst, const char *src, int max) {
    int di = gb_strlen(dst);
    int si = 0;
    dst[di++] = '"';
    while (src[si] && di < max - 2) {
        char c = src[si++];
        if (c == '"' || c == '\\') {
            if (di < max - 3) { dst[di++] = '\\'; dst[di++] = c; }
        } else if (c == '\n') {
            if (di < max - 3) { dst[di++] = '\\'; dst[di++] = 'n'; }
        } else if (c == '\r') {
            if (di < max - 3) { dst[di++] = '\\'; dst[di++] = 'r'; }
        } else if (c == '\t') {
            if (di < max - 3) { dst[di++] = '\\'; dst[di++] = 't'; }
        } else {
            dst[di++] = c;
        }
    }
    dst[di++] = '"';
    dst[di] = '\0';
}

/* -----------------------------------------------------------------------
 * ISO-8601 timestamp (UTC, async-signal-safe via time()/gmtime_r())
 * ----------------------------------------------------------------------- */

static void gb_append_timestamp(char *dst, int max) {
    time_t now;
    struct tm tm_buf;

    now = time(NULL);
    if (gmtime_r(&now, &tm_buf) == NULL) {
        gb_strcat(dst, "\"1970-01-01T00:00:00Z\"", max);
        return;
    }

    gb_strcat(dst, "\"", max);
    gb_strcat_4d(dst, tm_buf.tm_year + 1900, max);
    gb_strcat(dst, "-", max);
    gb_strcat_2d(dst, tm_buf.tm_mon + 1, max);
    gb_strcat(dst, "-", max);
    gb_strcat_2d(dst, tm_buf.tm_mday, max);
    gb_strcat(dst, "T", max);
    gb_strcat_2d(dst, tm_buf.tm_hour, max);
    gb_strcat(dst, ":", max);
    gb_strcat_2d(dst, tm_buf.tm_min, max);
    gb_strcat(dst, ":", max);
    gb_strcat_2d(dst, tm_buf.tm_sec, max);
    gb_strcat(dst, "Z\"", max);
}

/* -----------------------------------------------------------------------
 * Signal handler — async-signal-safe only
 * ----------------------------------------------------------------------- */

/* Direccion en hex, sin stdio: el handler no puede llamar a snprintf. */
static void gb_strcat_hex(char *dst, unsigned long v, size_t cap) {
    static const char D[] = "0123456789abcdef";
    char tmp[2 + sizeof(unsigned long) * 2 + 1];
    int i = (int)sizeof(tmp) - 1;
    tmp[i--] = '\0';
    if (v == 0) tmp[i--] = '0';
    while (v && i >= 2) { tmp[i--] = D[v & 0xf]; v >>= 4; }
    tmp[i--] = 'x';
    tmp[i] = '0';
    gb_strcat(dst, &tmp[i], cap);
}

static void gb_signal_handler(int sig, siginfo_t *info, void *ucontext) {
    (void)info;
    (void)ucontext;

    if (!gb_path_ready) _exit(128 + sig);

    /* Build the JSON record in the pre-allocated buffer. */
    gb_buf[0] = '\0';
    gb_strcat(gb_buf, "{\"schema\":2,\"ts\":", GB_BUF_SIZE);
    gb_append_timestamp(gb_buf, GB_BUF_SIZE);
    gb_strcat(gb_buf, ",\"lang\":\"c\",\"origin\":\"signal\"", GB_BUF_SIZE);
    gb_strcat(gb_buf, ",\"error\":{\"type\":\"signal\",\"signal\":", GB_BUF_SIZE);
    gb_strcat_int(gb_buf, sig, GB_BUF_SIZE);
    gb_strcat(gb_buf, ",\"name\":", GB_BUF_SIZE);
    gb_json_escape(gb_buf, gb_signal_name(sig), GB_BUF_SIZE);
    gb_strcat(gb_buf, "}", GB_BUF_SIZE);  /* close error */

    /* Los frames van AL REGISTRO, no al stderr del programa observado. */
#if GB_HAS_BACKTRACE
    {
        void *bt_buf[GB_BT_DEPTH];
        int bt_count = backtrace(bt_buf, GB_BT_DEPTH);
        gb_strcat(gb_buf, ",\"frames\":[", GB_BUF_SIZE);
        for (int i = 0; i < bt_count; i++) {
            if (i) gb_strcat(gb_buf, ",", GB_BUF_SIZE);
            gb_strcat(gb_buf, "\"", GB_BUF_SIZE);
            gb_strcat_hex(gb_buf, (unsigned long)bt_buf[i], GB_BUF_SIZE);
            gb_strcat(gb_buf, "\"", GB_BUF_SIZE);
        }
        gb_strcat(gb_buf, "]", GB_BUF_SIZE);
    }
#endif

    /* PID for forensics */
    gb_strcat(gb_buf, ",\"pid\":", GB_BUF_SIZE);
    gb_strcat_int(gb_buf, (long)getpid(), GB_BUF_SIZE);

    gb_strcat(gb_buf, "}\n", GB_BUF_SIZE);

    /* Write the record. */
    int fd = open(gb_path, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd >= 0) {
        int saved_errno = errno;
        (void)write(fd, gb_buf, gb_strlen(gb_buf));
        close(fd);
        errno = saved_errno;
    }

    /* Re-raise with default handler so the process exits normally. */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = SIG_DFL;
    sigaction(sig, &sa, NULL);
    raise(sig);

    _exit(128 + sig); /* fallback */
}

/* -----------------------------------------------------------------------
 * Constructor — runs at library load time
 * ----------------------------------------------------------------------- */

__attribute__((constructor))
static void gb_hook_init(void) {
    /* Build the output path: ~/.galaxy-brain/crashes.jsonl */
    const char *home = getenv("HOME");
    if (!home) home = getenv("USERPROFILE");
    if (!home) return;  /* can't determine home — silently do nothing */

    gb_path[0] = '\0';
    gb_strcpy(gb_path, home, GB_PATH_SIZE);
    gb_strcat(gb_path, "/.galaxy-brain", GB_PATH_SIZE);

    /* Best-effort mkdir (not async-signal-safe, but we're in constructor). */
    mkdir(gb_path, 0755);

    gb_strcat(gb_path, "/crashes.jsonl", GB_PATH_SIZE);
    gb_path_ready = 1;

    /* Install signal handlers. */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = gb_signal_handler;
    sa.sa_flags = SA_SIGINFO | SA_RESETHAND;  /* one-shot to avoid loops */
    sigemptyset(&sa.sa_mask);

    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGABRT, &sa, NULL);
    sigaction(SIGFPE,  &sa, NULL);
    sigaction(SIGILL,  &sa, NULL);
#ifdef SIGBUS
    sigaction(SIGBUS,  &sa, NULL);
#endif
}
