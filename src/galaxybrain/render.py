"""Mostrar un registro. La unica parte del proyecto que es cuestion de gusto.

Criterio: que el frame donde de verdad fallo se lea sin buscarlo, y que el
estado quepa en una pantalla. Un volcado completo es lo mismo que no tener
nada — obliga a leer, y leer es el trabajo que esto viene a quitar.
"""

import datetime
import os
import sys

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"

#: La consola de Windows sigue siendo cp1252 en muchas maquinas — incluida la de
#: quien escribe esto. Un adorno tipografico que revienta la salida no es un
#: detalle estetico: es la herramienta inservible en su plataforma principal.
GLYPHS_UNICODE = {"arrow": "→", "dot": "·", "more": "…"}
GLYPHS_ASCII = {"arrow": ">", "dot": "-", "more": "..."}


def terminal_supports_unicode(stream=None):
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        "".join(GLYPHS_UNICODE.values()).encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


class Style:
    """Color solo si hay terminal, y glifos solo si la terminal sabe pintarlos.

    En un fichero de log los codigos ANSI son basura que hay que quitar despues;
    en una consola cp1252 una flecha unicode es una excepcion.
    """

    def __init__(self, enabled, unicode_ok=None):
        self.enabled = enabled
        self.unicode = terminal_supports_unicode() if unicode_ok is None else unicode_ok
        self.glyph = GLYPHS_UNICODE if self.unicode else GLYPHS_ASCII

    def __call__(self, text, *codes):
        if not self.enabled or not codes:
            return text
        return "".join(codes) + text + RESET


def relative_time(ts):
    if not ts:
        return "?"
    try:
        moment = datetime.datetime.fromisoformat(ts)
    except ValueError:
        return ts
    now = datetime.datetime.now(moment.tzinfo)
    seconds = int((now - moment).total_seconds())
    if seconds < 0:
        return "ahora"
    if seconds < 60:
        return "hace %ds" % seconds
    if seconds < 3600:
        return "hace %dmin" % (seconds // 60)
    if seconds < 86400:
        return "hace %dh" % (seconds // 3600)
    return "hace %dd" % (seconds // 86400)


def short_path(path, project=None):
    """Rutas relativas al proyecto: la parte comun no aporta y ocupa pantalla."""
    if not path:
        return "?"
    try:
        if project and os.path.commonpath([os.path.abspath(path), project]) == project:
            return os.path.relpath(path, project).replace("\\", "/")
    except (ValueError, OSError):
        pass
    return path.replace("\\", "/")


def _headline_index(frames):
    """El frame mas interno que sea codigo tuyo: donde miras primero."""
    for index in range(len(frames) - 1, -1, -1):
        if not frames[index].get("is_library"):
            return index
    return len(frames) - 1 if frames else -1


def render_record(record, style, full=False):
    lines = []
    exc = record.get("exception", {})
    process = record.get("process", {})
    project = process.get("project")
    frames = record.get("frames") or []

    header = "%s: %s" % (exc.get("type", "?"), exc.get("message", ""))
    lines.append(style(header, BOLD, RED))

    dot = " %s " % style.glyph["dot"]
    where = ""
    index = _headline_index(frames)
    if index >= 0:
        where = "%s%s:%s" % (
            dot,
            short_path(frames[index].get("file"), project),
            frames[index].get("line"),
        )
    meta = "%s%s" % (relative_time(record.get("ts")), where)
    if project:
        meta += "%s%s" % (dot, os.path.basename(project))
    if record.get("thread") and record.get("thread") != "MainThread":
        meta += "%shilo %s" % (dot, record["thread"])
    lines.append(style(meta, DIM))
    lines.append("")

    for chain in exc.get("chain", []):
        label = "causada por" if chain["kind"] == "cause" else "durante el manejo de"
        lines.append(style("  %s %s: %s" % (label, chain["type"], chain["message"]), DIM))
    if exc.get("chain"):
        lines.append("")

    shown = frames if full else ([frames[index]] if index >= 0 else [])
    skipped = len(frames) - len(shown)

    for frame in shown:
        lines.extend(_render_frame(frame, style, project))
        lines.append("")

    if skipped > 0:
        lines.append(
            style("  (%d frames mas: gb show %s --full)" % (skipped, record.get("id")), DIM)
        )
    if record.get("frames_trimmed"):
        lines.append(
            style("  (%d frames externos recortados por GB_MAX_FRAMES)" % record["frames_trimmed"], DIM)
        )
    return "\n".join(lines)


def _render_frame(frame, style, project):
    lines = []
    location = "  %s:%s" % (short_path(frame.get("file"), project), frame.get("line"))
    suffix = "  in %s" % frame.get("function", "?")
    if frame.get("is_library"):
        suffix += style("  [libreria]", DIM)
    lines.append(style(location, BOLD) + suffix)

    for entry in frame.get("source") or []:
        marker = style(" " + style.glyph["arrow"], YELLOW) if entry.get("is_fail") else "  "
        number = style("%5d" % entry["n"], DIM)
        lines.append("  %s %s | %s" % (marker, number, entry.get("text", "")))

    local_values = frame.get("locals")
    if local_values:
        lines.append("")
        width = max(len(name) for name in local_values)
        for name, value in local_values.items():
            lines.append("      %s = %s" % (style(name.ljust(width), BOLD), value))
    elif local_values is None and frame.get("is_library"):
        lines.append(style("      (locales no capturadas: frame de libreria — GB_ALL_FRAMES=1)", DIM))
    return lines


MARKS = {"ok": "+", "parcial": "~", "falta": "!", "no-detectable": "?", "esqueleto": "o"}


def render_floor(report, style):
    """El suelo: que hay, que falta, y que no puede mirar esto.

    Lo delegado y lo no cubierto van al final CON el mismo peso: un informe que solo
    enumera lo que comprobo se lee como si eso fuera todo lo que hay que comprobar.
    """
    lines = []
    if report.get("root_error"):
        return style("ERROR: %s" % report["root_error"], RED)

    levels = report.get("levels") or []
    faltan = [l for l in levels if l["status"] == "falta"]
    lines.append(
        style(
            "El suelo de %s — %d nivel(es) sin cubrir de %d"
            % (report["root"], len(faltan), len(levels)),
            BOLD,
        )
    )
    lines.append("")

    for level in levels:
        mark = MARKS.get(level["status"], "?")
        color = {
            "ok": None, "parcial": YELLOW, "falta": RED,
            "no-detectable": DIM, "esqueleto": YELLOW,
        }.get(level["status"])
        head = "  %s %s" % (style(mark, color) if color else mark, level["title"])
        lines.append(head)
        lines.append("      %s" % style(level["detail"], DIM))
    lines.append("")

    if report.get("pending"):
        lines.append(style("Documentos puestos pero SIN RELLENAR:", BOLD))
        for path in report["pending"]:
            lines.append("  %s %s" % (style("o", YELLOW), path))
        lines.append(
            style(
                "      Un documento que existe y no dice nada pasa la lista sin aportar nada. "
                "Esto no cuenta como suelo hasta que se rellene.",
                DIM,
            )
        )
        lines.append("")

    if report.get("delegated"):
        lines.append(style("Delegado a herramientas que ya lo hacen:", BOLD))
        for item in report["delegated"]:
            lines.append("  %s %s" % (style("->", DIM), style(item, DIM)))
        lines.append("")

    if report.get("not_covered"):
        lines.append(style("Lo que esto NO ha mirado:", BOLD))
        for item in report["not_covered"]:
            lines.append("  %s %s" % (style("-", DIM), style(item, DIM)))

    return "\n".join(lines)


def render_changes(report, style, brief=False):
    """Qué le hizo el cambio a la evidencia. Informe, no veredicto.

    Lo que NO se ha mirado va SIEMPRE al final y con el mismo peso visual: un
    informe que solo enumera lo que revisó se lee como si lo hubiera revisado todo.

    `brief` es para los hooks: sin señales, una línea. Un informe largo en CADA
    commit deja de leerse a la tercera vez, y entonces no protege de nada — el
    mismo motivo por el que el aviso de captura es una sola línea.
    """
    lines = []
    if report.get("range_error"):
        lines.append(style("ERROR: %s" % report["range_error"], RED))
        return "\n".join(lines)

    flags = report.get("flags") or []

    if brief and not flags:
        return style(
            "[gb check] %s: %d fichero(s) de test tocado(s), sin senales "
            "(detalle: gb check%s)"
            % (
                report["range"],
                report["test_files_changed"],
                " --staged" if report.get("staged") else "",
            ),
            DIM,
        )
    lines.append(
        style(
            "%s — %d fichero(s) de test tocado(s), %d senal(es)"
            % (report["range"], report["test_files_changed"], len(flags)),
            BOLD,
        )
    )
    lines.append("")

    if flags:
        lines.append(style("SENALES sobre los tests (proxies: justifica cada una, no bloquean):", BOLD))
        for flag in flags:
            lines.append(
                "  %s [%s] %s" % (style("!", YELLOW), flag["signal"], flag["file"])
            )
            lines.append("      %s" % style(flag["detail"], DIM))
            for sample in flag["evidence"][:1]:
                if sample:
                    lines.append("      %s" % style("p.ej. `%s`" % sample[:100], DIM))
    else:
        lines.append(style("Sin senales de ablandamiento en los tests.", DIM))
    lines.append("")

    coupling = report.get("coupling")
    if coupling:
        if coupling["new_pairs"] or coupling["new_violations"]:
            lines.append(style("ACOPLAMIENTO nuevo vs %s:" % coupling["base"], BOLD))
            for pair in coupling["new_pairs"]:
                lines.append("  %s %s" % (style("+", YELLOW), "  <->  ".join(pair)))
            for violation in coupling["new_violations"]:
                lines.append(
                    "  %s %s  ->  %s   [%s]"
                    % (
                        style("!", YELLOW),
                        violation["importer"],
                        violation["imported"],
                        violation["rule"],
                    )
                )
        else:
            lines.append(
                style("Sin acoplamiento nuevo vs %s (%d modulos)." % (coupling["base"], coupling["modules"]), DIM)
            )
        lines.append("")

    if report.get("not_covered"):
        lines.append(style("Lo que esto NO ha mirado:", BOLD))
        for item in report["not_covered"]:
            lines.append("  %s %s" % (style("-", DIM), style(item, DIM)))

    return "\n".join(lines)


def render_graph(report, style):
    """El mapa de acoplamiento: resumen, ciclos (el hecho que importa) y hotspots."""
    lines = []
    if report.get("root_error"):
        lines.append(style("ERROR: %s" % report["root_error"], RED))
        lines.append("")
    lines.append(
        style(
            "%d modulos, %d aristas internas, %d ciclo(s)"
            % (report["modules"], report["edges"], len(report["cycles"])),
            BOLD,
        )
    )
    if report.get("errors"):
        lines.append(style("  %d fichero(s) no parsearon (ver --json)" % len(report["errors"]), DIM))
    # Decir SIEMPRE lo que se dejo fuera: reducir cobertura en silencio convierte
    # un "sin ciclos" en una mentira comoda.
    skipped = report.get("skipped_nested") or []
    if skipped:
        lines.append(
            style(
                "  %d subproyecto(s) anidado(s) omitido(s) (--include-nested para verlos):"
                % len(skipped),
                DIM,
            )
        )
        for path in skipped[:5]:
            lines.append(style("    %s" % path, DIM))
        if len(skipped) > 5:
            lines.append(style("    ... y %d mas" % (len(skipped) - 5), DIM))
    if not report["modules"] and not report.get("root_error"):
        lines.append(style("  AVISO: ni un modulo analizado — esto no comprueba nada.", YELLOW))
    lines.append("")

    if report["cycles"]:
        lines.append(style("CICLOS de imports (acoplamiento circular — un hecho, no una opinion):", BOLD))
        for cyc in report["cycles"]:
            lines.append("  %s %s" % (style("*", YELLOW), "  <->  ".join(cyc)))
    else:
        lines.append(style("Sin ciclos de imports.", DIM))
    lines.append("")

    if report.get("since") is not None:
        ref = report["since"]
        if report.get("baseline_ok") is False:
            lines.append(style("No pude comparar con '%s' (repo git? ref valida?)." % ref, DIM))
        elif report.get("new_cycles"):
            lines.append(style("NUEVO acoplamiento ciclico vs %s:" % ref, BOLD))
            for cyc in report["new_cycles"]:
                lines.append("  %s %s" % (style("+", YELLOW), "  <->  ".join(cyc)))
        else:
            lines.append(style("Sin acoplamiento ciclico nuevo vs %s." % ref, DIM))
        lines.append("")

    # El estado de las fronteras se dice SIEMPRE, y sobre todo cuando hay CERO
    # reglas. Antes esa rama era la unica muda: con reglas se leia "Sin cruces
    # (33 regla(s))" y sin reglas no salia nada, asi que un verde sin comprobar
    # nada era indistinguible de un verde limpio. Es el peor modo de fallo de un
    # gate y se encontro usando la herramienta de verdad (2026-07-31).
    if not report.get("root_error"):
        if report.get("boundaries_error"):
            lines.append(style("ERROR de fronteras: %s" % report["boundaries_error"], RED))
        if report["violations"]:
            extra = ""
            if report.get("since") is not None and report.get("baseline_ok"):
                extra = " (%d nuevo(s) vs %s)" % (len(report["new_violations"]), report["since"])
            lines.append(style("CRUCES de frontera prohibidos%s:" % extra, BOLD))
            for v in report["violations"]:
                lines.append(
                    "  %s %s  ->  %s   [%s]"
                    % (style("!", YELLOW), v["importer"], v["imported"], v["rule"])
                )
        elif report.get("boundaries"):
            lines.append(style("Sin cruces de frontera prohibidos (%d regla(s))." % report["boundaries"], DIM))
        elif not report.get("boundaries_error"):
            otro = report.get("boundaries_elsewhere")
            lines.append(style("SIN FRONTERAS COMPROBADAS: 0 reglas cargadas.", YELLOW))
            lines.append(style("  busque en %s" % report.get("boundaries_path", "?"), DIM))
            if otro:
                lines.append(
                    style(
                        "  pero SI existe %s — ese fichero no se esta aplicando; "
                        "apunta el analisis a su carpeta o mueve el fichero" % otro,
                        YELLOW,
                    )
                )
        for m in report.get("malformed_boundaries", []):
            lines.append(style("  AVISO: linea de regla no valida (ignorada): `%s`" % m, YELLOW))
        for u in report.get("unmatched_rules", []):
            lines.append(
                style("  AVISO: la regla `%s` no casa con ningun modulo (typo o raiz equivocada)." % u["rule"], YELLOW)
            )
        lines.append("")

    if report.get("smells"):
        if report.get("abstractions"):
            lines.append(
                style("Sobreingenieria (ADVISORY, no bloquea) — abstracciones con <=1 implementacion:", BOLD)
            )
            for a in report["abstractions"]:
                cuenta = "sin implementacion" if a["impls"] == 0 else "1 implementacion"
                lines.append("  %s %s.%s  (%s)" % (style("?", DIM), a["module"], a["class"], cuenta))
        else:
            lines.append(style("Sin abstracciones sospechosas.", DIM))
        lines.append("")

    def _top(counts):
        return [(m, n) for m, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5] if n]

    fan_in = _top(report["fan_in"])
    fan_out = _top(report["fan_out"])
    if fan_in:
        lines.append(style("Mas importados (fan-in):", BOLD))
        for mod, n in fan_in:
            lines.append("  %3d  %s" % (n, mod))
        lines.append("")
    if fan_out:
        lines.append(style("Mas dependientes (fan-out):", BOLD))
        for mod, n in fan_out:
            lines.append("  %3d  %s" % (n, mod))
    return "\n".join(lines).rstrip()


def render_graph_context(report):
    """El mapa comprimido a payload de sesión: la forma del proyecto de una pasada.

    Sin color y sin adornos porque no lo lee un humano en una terminal: lo lee un
    agente al arrancar. Y **cadena vacía cuando no hay nada que decir** — un payload
    que anuncia "0 módulos" es ruido inyectado en cada sesión, y la regla 2 dice
    devolver algo o callarse. El techo es la decena de líneas: si esto engorda,
    compite con el contexto que `gb memory` se esfuerza en mantener magro (H6).
    """
    if report.get("root_error") or not report.get("modules"):
        return ""
    raiz = report.get("root") or ""
    nombre = os.path.basename(raiz.rstrip("\\/")) or raiz
    padre = os.path.basename(os.path.dirname(raiz.rstrip("\\/")))
    etiqueta = (padre + "/" + nombre) if padre and nombre in ("src", "lib", "app") else nombre

    ciclos = report.get("cycles") or []
    violaciones = report.get("violations") or []
    lines = [
        "# mapa de %s — %d modulos, %d aristas, %d ciclo(s) [gb graph]"
        % (etiqueta, report["modules"], report["edges"], len(ciclos)),
        # El alcance va SIEMPRE: este payload sale de la raiz del repo (incluye
        # tests) y `gb graph src` mira solo el paquete, asi que los dos numeros son
        # distintos y correctos. Sin decir sobre que se ha contado, parecen
        # contradecirse y uno de los dos se toma por erroneo. Reportado en uso real.
        "  alcance: %s — otra raiz da otros numeros" % raiz.replace("\\", "/"),
    ]

    # Los dos hechos que bloquean van arriba y enteros: son la unica salida de
    # `graph` que detiene un commit (regla 11), asi que no se resumen.
    for ciclo in ciclos[:5]:
        lines.append("  CICLO: " + " -> ".join(ciclo))
    for v in violaciones[:5]:
        lines.append("  CRUCE DE FRONTERA: %s -> %s" % (v.get("importer", "?"), v.get("imported", "?")))

    def _top(counts, n=4):
        return [(m, c) for m, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n] if c]

    entrantes = _top(report.get("fan_in") or {})
    salientes = _top(report.get("fan_out") or {})
    if entrantes:
        lines.append("  nucleo (mas importado): " + " · ".join("%s<-%d" % (m, c) for m, c in entrantes))
    if salientes:
        lines.append("  cabeza (mas depende): " + " · ".join("%s->%d" % (m, c) for m, c in salientes))
    return "\n".join(lines)


def render_groups(groups, style):
    """La vista de libreta: qué se rompe y cuántas veces, lo más frecuente arriba."""
    if not groups:
        return "(sin capturas todavia)"
    lines = []
    width = max(len("%dx" % g["count"]) for g in groups)
    for g in groups:
        count = style(("%dx" % g["count"]).rjust(width), BOLD)
        kind = (g.get("type") or "?")[:22].ljust(22)
        when = ("ult. " + relative_time(g.get("last_ts"))).ljust(16)
        where = short_path(g.get("where") or "", g.get("project"))
        lines.append("%s  %s  %s  %s" % (count, style(kind, BOLD), style(when, DIM), where))
    return "\n".join(lines)


def render_index(entries, style):
    if not entries:
        return "(sin capturas todavia)"
    lines = []
    for entry in entries:
        when = relative_time(entry.get("ts")).ljust(10)
        kind = (entry.get("type") or "?")[:22].ljust(22)
        where = short_path(entry.get("where") or "", entry.get("project"))
        lines.append(
            "%s  %s  %s  %s"
            % (
                style(entry.get("id", "?")[:22].ljust(22), DIM),
                style(when, DIM),
                style(kind, BOLD),
                where,
            )
        )
    return "\n".join(lines)
