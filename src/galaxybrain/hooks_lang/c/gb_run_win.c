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
    /* El id de sesion que reparte `gb run`: sin el, el crash de C queda
       huerfano en un repo mixto — capturado, pero imposible de atar a la cadena
       de procesos que lo produjo, que es justo lo que hace util un buzon comun.
       Era el segundo hook al que le faltaba (experimento poliglota, 19-ago). */
    const char *sesion = getenv("GB_SESSION_ID");
    fprintf(f,
            "{\"schema\":2,\"ts\":\"%s\",\"lang\":\"c\","
            "\"exception\":{\"origin\":\"%s\"},\"capture_method\":\"wrapper\","
            "\"via\":\"%s\","
            "\"error\":{\"type\":\"%s\",\"code\":\"0x%08lX\"",
            ts, (tid == tid_principal ? "main" : "thread"), via,
            nombre_excepcion(codigo), (unsigned long)codigo);
    if (direccion) fprintf(f, ",\"address\":\"0x%p\"", direccion);
    /* Ojo con el orden: el `session_id` va FUERA del objeto `error`. Puesto
       dentro (que es donde cayo al primer intento) el registro sigue siendo
       JSON valido y el campo existe... pero en el sitio que nadie mira, asi que
       el crash seguia saliendo huerfano. Un dato en el sitio equivocado se lee
       igual que un dato que falta. */
    fprintf(f, "},\"pid\":%lu,\"tid\":%lu", (unsigned long)pid, (unsigned long)tid);
    if (sesion && *sesion) fprintf(f, ",\"session_id\":\"%s\"", sesion);
    /* El directorio, para que el buzon pueda deducir el proyecto. Sin el, la
       captura de C quedaba fuera de toda vista por proyecto: archivada, pero
       invisible en el mapa y en el `gb last` del repo. Las barras se escapan
       porque en Windows son `\` y esto es JSON. */
    char dir[MAX_PATH];
    if (GetCurrentDirectoryA(MAX_PATH, dir)) {
        fprintf(f, ",\"process\":{\"cwd\":\"");
        for (const char *c = dir; *c; c++) {
            if (*c == '\\') fputs("\\\\", f);
            else fputc(*c, f);
        }
        fprintf(f, "\"}");
    }
    fprintf(f, "}\n");
    fclose(f);
}

/* Los runtimes que YA traen su propio hook. En modo arbol el depurador ve las
   excepciones de TODOS los procesos, y una NullReferenceException de .NET llega
   al nivel nativo como un ACCESS_VIOLATION igual que el de un programa en C: sin
   este filtro, el crash de C# entraba DOS veces —por su hook y por aqui— y el
   segundo iba etiquetado como "c", que es sencillamente falso. Un registro mal
   atribuido es peor que uno que falta: manda a mirar el lenguaje que no es. */
static const char *RUNTIMES_CON_HOOK[] = {
    "dotnet.exe", "java.exe", "javaw.exe", "node.exe", "ruby.exe", "php.exe",
    "lua.exe", "python.exe", "pythonw.exe", "dart.exe", "scala.exe", "kotlin.exe",
    NULL,
};

#define GB_MAX_PROCESOS 64
static DWORD gb_pids[GB_MAX_PROCESOS];
static char gb_imagenes[GB_MAX_PROCESOS][MAX_PATH];
static int gb_n_procesos = 0;

static void recuerda_proceso(DWORD pid, HANDLE proceso) {
    if (gb_n_procesos >= GB_MAX_PROCESOS || !proceso) return;
    DWORD tam = MAX_PATH;
    char ruta[MAX_PATH] = "";
    if (!QueryFullProcessImageNameA(proceso, 0, ruta, &tam)) return;
    gb_pids[gb_n_procesos] = pid;
    strncpy(gb_imagenes[gb_n_procesos], ruta, MAX_PATH - 1);
    gb_imagenes[gb_n_procesos][MAX_PATH - 1] = '\0';
    gb_n_procesos++;
}

/* Las DLL que delatan a un runtime con hook propio. Es mejor discriminador que
   el nombre del ejecutable: un binario de .NET publicado se llama como quiera
   (`paso.exe`), pero SIEMPRE carga coreclr/hostfxr. Y un programa en C no carga
   ninguna de estas. */
static const char *DLLS_DE_RUNTIME[] = {
    "coreclr.dll", "hostfxr.dll", "hostpolicy.dll", "clrjit.dll",
    "jvm.dll", "libnode.dll", "node.exe", "dart.dll",
    NULL,
};

static DWORD gb_gestionados[GB_MAX_PROCESOS];
static int gb_n_gestionados = 0;

static void marca_gestionado(DWORD pid) {
    for (int i = 0; i < gb_n_gestionados; i++) if (gb_gestionados[i] == pid) return;
    if (gb_n_gestionados < GB_MAX_PROCESOS) gb_gestionados[gb_n_gestionados++] = pid;
}

static void mira_dll(DWORD pid, HANDLE fichero) {
    if (!fichero) return;
    char ruta[MAX_PATH] = "";
    if (!GetFinalPathNameByHandleA(fichero, ruta, MAX_PATH, 0)) return;
    const char *barra = strrchr(ruta, '\\');
    const char *nombre = barra ? barra + 1 : ruta;
    for (int j = 0; DLLS_DE_RUNTIME[j]; j++) {
        if (_stricmp(nombre, DLLS_DE_RUNTIME[j]) == 0) { marca_gestionado(pid); return; }
    }
}

static int lo_cubre_su_propio_hook(DWORD pid) {
    for (int i = 0; i < gb_n_gestionados; i++) if (gb_gestionados[i] == pid) return 1;
    for (int i = 0; i < gb_n_procesos; i++) {
        if (gb_pids[i] != pid) continue;
        const char *barra = strrchr(gb_imagenes[i], '\\');
        const char *nombre = barra ? barra + 1 : gb_imagenes[i];
        for (int j = 0; RUNTIMES_CON_HOOK[j]; j++) {
            if (_stricmp(nombre, RUNTIMES_CON_HOOK[j]) == 0) return 1;
        }
        return 0;
    }
    return 0;   /* desconocido: se registra, que es el lado seguro */
}


int main(int argc, char **argv) {
    int soltar = 0;
    /* --arbol: depurar tambien a los NIETOS (DEBUG_PROCESS en vez de
       DEBUG_ONLY_THIS_PROCESS). Es lo unico que cubre a un binario de C llamado
       por otro programa en un repo mixto: en Windows no hay nada que se herede
       solo, al reves que LD_PRELOAD en Linux. Va detras de una bandera y no por
       defecto porque tiene coste — engancha el depurador a TODO el arbol — y en
       este proyecto lo que cuesta se enciende midiendo, no suponiendo. */
    int arbol = 0;
    int i = 1;
    for (; i < argc; i++) {
        if (strcmp(argv[i], "--soltar") == 0)      soltar = 1;
        else if (strcmp(argv[i], "--pegado") == 0) soltar = 0;
        else if (strcmp(argv[i], "--arbol") == 0)  arbol = 1;
        else break;
    }
    /* En modo arbol manda `pegado`: `soltar` decide por el exit code del
       proceso que se solto, y con nietos el que revienta puede no ser el que se
       espera. Antes que dar un veredicto sobre el proceso equivocado, se observa
       y se registra en la segunda vuelta. */
    if (arbol) soltar = 0;

    if (i >= argc) {
        fprintf(stderr,
                "uso: gb-run.exe [--soltar|--pegado] [--arbol] programa.exe [args...]\n");
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
                        arbol ? DEBUG_PROCESS : DEBUG_ONLY_THIS_PROCESS,
                        NULL, NULL, &si, &pi)) {
        fprintf(stderr, "gb-run: no se pudo lanzar (error %lu)\n", GetLastError());
        return 127;
    }

    DEBUG_EVENT ev;
    DWORD salida = 0;
    int primer_breakpoint = 1;
    /* El hilo del CREATE_PROCESS es el principal: con el se decide si la
       excepcion afloro en `main` o en un `thread`, que es lo que pide el enum. */
    DWORD tid_principal = 0;
    /* La ultima excepcion registrada, para no contar dos veces la misma. */
    DWORD ultimo_pid = 0, ultimo_codigo = 0;
    const void *ultima_direccion = NULL;

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
            } else if (arbol && lo_cubre_su_propio_hook(ev.dwProcessId)) {
                /* Ese proceso ya tiene su hook dentro: lo suyo lo cuenta el, y
                   contarlo aqui ademas lo etiquetaria como "c". */
                continuar = DBG_EXCEPTION_NOT_HANDLED;
            } else if (ev.dwProcessId == ultimo_pid
                       && er->ExceptionCode == ultimo_codigo
                       && er->ExceptionAddress == ultima_direccion) {
                /* La MISMA excepcion, otra vez: en modo arbol el sistema la
                   reporta dos veces y el mismo crash entraba duplicado en el
                   buzon. Dos registros de un solo fallo no son mas informacion:
                   son una cuenta inflada, y este proyecto vive de que sus
                   numeros se puedan creer (19-ago-2026). */
                continuar = DBG_EXCEPTION_NOT_HANDLED;
            } else {
                /* Segunda vuelta: nadie la manejo. Esto si es un crash. */
                registra(er->ExceptionCode, er->ExceptionAddress,
                         ev.dwProcessId, ev.dwThreadId, tid_principal, "debugger");
                ultimo_pid = ev.dwProcessId;
                ultimo_codigo = er->ExceptionCode;
                ultima_direccion = er->ExceptionAddress;
                continuar = DBG_EXCEPTION_NOT_HANDLED;
            }
        } else if (ev.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT) {
            if (!tid_principal) tid_principal = ev.dwThreadId;
            /* En modo arbol llegan tambien los nietos: su handle de fichero se
               cierra en cuanto se recibe, o el proceso queda enganchado. */
            recuerda_proceso(ev.dwProcessId, ev.u.CreateProcessInfo.hProcess);
            if (ev.u.CreateProcessInfo.hFile) CloseHandle(ev.u.CreateProcessInfo.hFile);
        } else if (ev.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT) {
            mira_dll(ev.dwProcessId, ev.u.LoadDll.hFile);
            if (ev.u.LoadDll.hFile) CloseHandle(ev.u.LoadDll.hFile);
        } else if (ev.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT) {
            /* Solo manda la muerte del proceso RAIZ: en modo arbol mueren
               tambien los nietos, y salir con el primero dejaria la cadena a
               medias y devolveria el exit code de quien no era. */
            if (ev.dwProcessId == pi.dwProcessId) {
                salida = ev.u.ExitProcess.dwExitCode;
                ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, DBG_CONTINUE);
                break;
            }
        }

        ContinueDebugEvent(ev.dwProcessId, ev.dwThreadId, continuar);
    }

    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)salida;   /* el exit code del programa, repetido tal cual */
}
