/*
 * gb-run (Windows) — captura de crashes nativos SIN tocar el programa observado.
 *
 * En Linux el hook de C se mete DENTRO del proceso (LD_PRELOAD + sigaction).
 * En Windows no existe LD_PRELOAD, y las tres alternativas de inyeccion piden
 * administrador, son globales para toda la maquina, o las marca el antivirus.
 *
 * Aqui se hace al reves: el programa se lanza como DEPURADO
 * (CreateProcess + DEBUG_ONLY_THIS_PROCESS) y este proceso escucha el bucle de
 * eventos. No se carga nada en el proceso observado, la excepcion llega
 * ESTRUCTURADA (codigo, direccion, hilo) en vez de como texto de stderr, y al
 * vivir fuera del proceso que muere no hay que programar async-signal-safe.
 *
 * Coste declarado: es un envolvente. Hay que invocar `gb-run programa.exe`.
 *
 * ---------------------------------------------------------------------------
 * DOS MODOS, porque Windows tiene una trampa medida el 18-ago-2026:
 *
 *   UnhandledExceptionFilter() de kernel32 comprueba si hay un depurador y, si
 *   lo hay, se SALTA el filtro de ultimo recurso que el programa instalo con
 *   SetUnhandledExceptionFilter. O sea: el simple hecho de mirar cambia lo que
 *   hace un programa que ya tiene su propio manejador de crashes (Sentry,
 *   Breakpad, Crashpad y cualquiera que registre uno).
 *
 *   --pegado  (por defecto): nos quedamos enganchados y registramos en la
 *             SEGUNDA vuelta. Ve todo, pero pisa el filtro del programa.
 *
 *   --soltar: en la primera vuelta de una excepcion mortal se anota lo visto,
 *             se SUELTA el depurador (DebugActiveProcessStop) y se deja que la
 *             excepcion siga su curso normal — con lo que el filtro del
 *             programa SI corre. Luego se decide por el RESULTADO: si el
 *             proceso murio con ese codigo, se escribe el registro; si salio
 *             limpio, no habia crash y no se escribe nada.
 *             Coste: tras soltar ya no se observa nada mas.
 *
 * Build:  gcc -O2 -Wall -Wextra -o gb-run.exe gb_run_win.c
 * Uso:    gb-run.exe [--soltar|--pegado] programa.exe [args...]
 */

#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static const char *nombre_excepcion(DWORD c) {
    switch (c) {
    case EXCEPTION_ACCESS_VIOLATION:      return "EXCEPTION_ACCESS_VIOLATION";
    case EXCEPTION_INT_DIVIDE_BY_ZERO:    return "EXCEPTION_INT_DIVIDE_BY_ZERO";
    case EXCEPTION_FLT_DIVIDE_BY_ZERO:    return "EXCEPTION_FLT_DIVIDE_BY_ZERO";
    case EXCEPTION_ILLEGAL_INSTRUCTION:   return "EXCEPTION_ILLEGAL_INSTRUCTION";
    case EXCEPTION_STACK_OVERFLOW:        return "EXCEPTION_STACK_OVERFLOW";
    case EXCEPTION_INT_OVERFLOW:          return "EXCEPTION_INT_OVERFLOW";
    case EXCEPTION_PRIV_INSTRUCTION:      return "EXCEPTION_PRIV_INSTRUCTION";
    case EXCEPTION_IN_PAGE_ERROR:         return "EXCEPTION_IN_PAGE_ERROR";
    case EXCEPTION_ARRAY_BOUNDS_EXCEEDED: return "EXCEPTION_ARRAY_BOUNDS_EXCEEDED";
    case EXCEPTION_DATATYPE_MISALIGNMENT: return "EXCEPTION_DATATYPE_MISALIGNMENT";
    case EXCEPTION_NONCONTINUABLE_EXCEPTION: return "EXCEPTION_NONCONTINUABLE_EXCEPTION";
    case 0xC0000409:                      return "STATUS_STACK_BUFFER_OVERRUN";  /* __fastfail / abort */
    case 0xE06D7363:                      return "CPP_EXCEPTION";                /* throw de C++ */
    default:                              return "UNKNOWN";
    }
}

/* Mortal = de las que matan si nadie las maneja. Un throw de C++ o un
   breakpoint NO lo son: soltar el depurador con uno de esos nos dejaria ciegos
   por una excepcion que el programa iba a manejar de todos modos. */
static int es_mortal(DWORD c) {
    switch (c) {
    case EXCEPTION_ACCESS_VIOLATION:
    case EXCEPTION_INT_DIVIDE_BY_ZERO:
    case EXCEPTION_FLT_DIVIDE_BY_ZERO:
    case EXCEPTION_ILLEGAL_INSTRUCTION:
    case EXCEPTION_STACK_OVERFLOW:
    case EXCEPTION_PRIV_INSTRUCTION:
    case EXCEPTION_IN_PAGE_ERROR:
    case EXCEPTION_ARRAY_BOUNDS_EXCEEDED:
    case EXCEPTION_NONCONTINUABLE_EXCEPTION:
    case 0xC0000409:
        return 1;
    default:
        return 0;
    }
}

/* Un exit code en el rango de error de NTSTATUS es una muerte del sistema,
   no un `exit(n)` del programa: 0xC0000005, 0xC0000409, etc. */
static int codigo_de_muerte(DWORD salida) {
    return (salida & 0xF0000000UL) == 0xC0000000UL;
}

/* El buzon: $HOME/.galaxy-brain/crashes.jsonl, con USERPROFILE de respaldo.
   Misma convencion que el hook de Linux, para que el almacen no note la via. */
static void ruta_buzon(char *out, size_t cap) {
    const char *home = getenv("HOME");
    if (!home || !*home) home = getenv("USERPROFILE");
    if (!home) home = ".";
    snprintf(out, cap, "%s\\.galaxy-brain", home);
    CreateDirectoryA(out, NULL);
    strncat(out, "\\crashes.jsonl", cap - strlen(out) - 1);
}

static void registra(DWORD codigo, const void *direccion, DWORD pid, DWORD tid,
                     DWORD tid_principal, const char *via) {
    char ruta[MAX_PATH * 2];
    ruta_buzon(ruta, sizeof(ruta));
    FILE *f = fopen(ruta, "ab");
    if (!f) return;

    time_t ahora = time(NULL);
    struct tm t;
    char ts[32] = "1970-01-01T00:00:00Z";
    if (gmtime_s(&t, &ahora) == 0)
        strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &t);

    /* Vive fuera del proceso que muere, asi que aqui SI se puede usar stdio. */
    /* `origin` dice DONDE afloro (enum del schema v2: main/thread/...), y
       `capture_method` COMO se capturo (hook/stderr/wrapper). Son dos campos
       distintos y meter aqui "debugger" era colar un metodo disfrazado de
       contexto: gb lo pintaba como un hilo llamado "debugger" que no existe. */
    fprintf(f,
            "{\"schema\":2,\"ts\":\"%s\",\"lang\":\"c\","
            "\"exception\":{\"origin\":\"%s\"},\"capture_method\":\"wrapper\","
            "\"via\":\"%s\","
            "\"error\":{\"type\":\"%s\",\"code\":\"0x%08lX\"",
            ts, (tid == tid_principal ? "main" : "thread"), via,
            nombre_excepcion(codigo), (unsigned long)codigo);
    if (direccion) fprintf(f, ",\"address\":\"0x%p\"", direccion);
    fprintf(f, "},\"pid\":%lu,\"tid\":%lu}\n",
            (unsigned long)pid, (unsigned long)tid);
    fclose(f);
}

int main(int argc, char **argv) {
    int soltar = 0;
    int i = 1;
    for (; i < argc; i++) {
        if (strcmp(argv[i], "--soltar") == 0)      soltar = 1;
        else if (strcmp(argv[i], "--pegado") == 0) soltar = 0;
        else break;
    }
    if (i >= argc) {
        fprintf(stderr, "uso: gb-run.exe [--soltar|--pegado] programa.exe [args...]\n");
        return 2;
    }

    /* Linea de comandos del hijo, con comillas si hay espacios. */
    char cmd[32768];
    cmd[0] = '\0';
    for (int j = i; j < argc; j++) {
        if (j > i) strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        int con_espacio = strchr(argv[j], ' ') != NULL;
        if (con_espacio) strncat(cmd, "\"", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, argv[j], sizeof(cmd) - strlen(cmd) - 1);
        if (con_espacio) strncat(cmd, "\"", sizeof(cmd) - strlen(cmd) - 1);
    }

    STARTUPINFOA si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));

    /* Handles heredados: el hijo escribe DIRECTO en nuestro stdout/stderr, sin
       tuberia intermedia. Un byte suyo es un byte nuestro, sin reescribir. */
    if (!CreateProcessA(NULL, cmd, NULL, NULL, TRUE,
                        DEBUG_ONLY_THIS_PROCESS, NULL, NULL, &si, &pi)) {
        fprintf(stderr, "gb-run: no se pudo lanzar (error %lu)\n", GetLastError());
        return 127;
    }

    DEBUG_EVENT ev;
    DWORD salida = 0;
    int primer_breakpoint = 1;
    /* El hilo del CREATE_PROCESS es el principal: con el se decide si la
       excepcion afloro en `main` o en un `thread`, que es lo que pide el enum. */
    DWORD tid_principal = 0;

    /* Lo visto en la primera vuelta, por si luego resulta que mato al proceso. */
    DWORD vi_codigo = 0, vi_pid = 0, vi_tid = 0;
    const void *vi_direccion = NULL;

    for (;;) {
        if (!WaitForDebugEvent(&ev, INFINITE)) break;
        DWORD continuar = DBG_CONTINUE;

        if (ev.dwDebugEventCode == EXCEPTION_DEBUG_EVENT) {
            const EXCEPTION_RECORD *er = &ev.u.Exception.ExceptionRecord;

            if (primer_breakpoint && er->ExceptionCode == EXCEPTION_BREAKPOINT) {
                /* El del cargador: es nuestro, no del programa. */
                primer_breakpoint = 0;
                continuar = DBG_CONTINUE;
            } else if (soltar && ev.u.Exception.dwFirstChance
                       && es_mortal(er->ExceptionCode)) {
                /* Anotar, soltar, y decidir por el resultado. Al soltar, el
                   filtro de ultimo recurso del programa vuelve a correr: para
                   el kernel ya no hay depurador enganchado. */
                vi_codigo = er->ExceptionCode;
                vi_direccion = er->ExceptionAddress;
                vi_pid = ev.dwProcessId;
                vi_tid = ev.dwThreadId;
                ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_EXCEPTION_NOT_HANDLED);
                DebugActiveProcessStop(ev.dwProcessId);

                WaitForSingleObject(pi.hProcess, INFINITE);
                GetExitCodeProcess(pi.hProcess, &salida);
                if (salida == vi_codigo) {
                    /* Murio por lo que vimos: registro completo, con direccion. */
                    registra(vi_codigo, vi_direccion, vi_pid, vi_tid, tid_principal, "debugger-soltado");
                } else if (codigo_de_muerte(salida)) {
                    /* Murio por otra cosa que ya no vimos: se registra lo que
                       el exit code demuestra, sin inventar la direccion. */
                    registra(salida, NULL, vi_pid, vi_tid, tid_principal, "exitcode");
                }
                /* Si salio limpio, el programa la manejo: no hubo crash. */
                break;
            } else if (ev.u.Exception.dwFirstChance) {
                /* Que la maneje el programa si tiene con que. Nosotros miramos. */
                continuar = DBG_EXCEPTION_NOT_HANDLED;
            } else {
                /* Segunda vuelta: nadie la manejo. Esto si es un crash. */
                registra(er->ExceptionCode, er->ExceptionAddress,
                         ev.dwProcessId, ev.dwThreadId, tid_principal, "debugger");
                continuar = DBG_EXCEPTION_NOT_HANDLED;
            }
        } else if (ev.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT) {
            if (!tid_principal) tid_principal = ev.dwThreadId;
        } else if (ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT) {
            salida = ev.u.ExitProcess.dwExitCode;
            ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE);
            break;
        }

        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, continuar);
    }

    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)salida;   /* el exit code del programa, repetido tal cual */
}
