"""El mapa, en imagen. Un solo fichero HTML autocontenido.

§10 nivel 3 pide *"un mapa, no una lectura"*, y `gb graph` ya lo da en texto. Esto es
el mismo hecho pintado: no hay dato nuevo, hay otra forma de mirarlo.

Dos decisiones que no son estéticas:

**DETERMINISTA aunque se mueva.** Dos capturas del mismo proyecto tienen que poder
compararse. En la nube, Python calcula las semillas (jerarquía + jitter por hash) y
el sim converge EN VIVO en el navegador — el "Layout optimizing…" de GitNexus: la
convergencia animada es el efecto. Sigue siendo determinista porque nada usa
`random()`: mismas semillas, mismas iteraciones, mismo estado final en cada carga.
La respiración y el pulso posteriores viven en espacio de *dibujo*, no de física —
la estructura no deriva. `force_layout` queda como gemela de referencia del sim en
JS (mismo algoritmo y constantes), y es donde se testea la física con pytest.

Aviso sobre una afirmación anterior de este mismo fichero, que era **falsa**: se dijo
que un layout de fuerzas renuncia al determinismo. No es cierto — solo baila si lo
arrancas al azar.

Dos vistas, dos preguntas distintas: la de **capas** responde *"¿qué depende de qué?"*
y la de **nube** responde *"¿qué forma tiene esto?"*. Ninguna sustituye a la otra.

**Cero dependencias, un fichero.** Nada de CDN, ni npm, ni build. El SVG se calcula
aquí y el HTML se escribe entero; se abre con doble clic o desde VS Code. Esto no es
purismo: la regla de cero dependencias existe para que `gb` se pueda instalar en el
venv de cualquier proyecto sin arrastrar nada, y un visor no es motivo para romperla.

Los ciclos van marcados, porque son el único hecho de este mapa que exige una decisión.
Con `--since`, lo NUEVO va marcado aparte: ver crecer un proyecto es, sobre todo, ver
qué apareció desde la última vez.
"""

import html as _html
import math


def _jitter(nombre, amplitud):
    """Desplazamiento pseudoaleatorio pero DETERMINISTA, derivado del nombre.

    Donde una implementacion tipica pone `Math.random()` —y con el la
    irreproducibilidad— aqui va un hash: mismo nombre, mismo jitter, siempre.
    """
    import hashlib

    h = hashlib.md5(nombre.encode("utf-8", "replace")).digest()
    x = (int.from_bytes(h[0:4], "big") / 0xFFFFFFFF - 0.5) * 2 * amplitud
    y = (int.from_bytes(h[4:8], "big") / 0xFFFFFFFF - 0.5) * 2 * amplitud
    return x, y


def force_layout(nodes, edges, iteraciones=300, lado=1000.0, mass=None, seeds=None):
    """Layout de fuerzas **determinista**, portado de la arquitectura de GitNexus
    (gitnexus-web/src/lib/graph-adapter.ts, leido — no supuesto).

    Las tres decisiones que hacen que su nube tenga forma y la primera version de
    esta no la tuviera:

    - **Siembra jerarquica, no circulo.** Lo estructural se coloca primero en
      espiral de angulo aureo; cada hijo nace JUNTO a su padre con un jitter
      determinista. El comentario de su codigo lo dice tal cual: *"used only for
      initial spatial seeding before FA2 runs"*. Se pasa via `seeds`.
    - **Masa por tipo** (`mass`): un modulo pesa 20, una funcion 2. Lo pesado
      repele fuerte y arrastra a sus hijos — de ahi los clusters.
    - **Gravedad, no caja.** La version anterior acotaba con un clamp a los
      bordes, y el resultado fue un rectangulo de nodos pegados a las paredes
      (visto en captura real). La gravedad hacia el centro hace el mismo trabajo
      sin ese artefacto.

    Determinista de punta a punta: siembra por hash, iteraciones fijas, desempate
    de superpuestos por indice. Mismo grafo, mismo dibujo, byte a byte.
    """
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: (lado / 2, lado / 2)}

    indice = {nodo: i for i, nodo in enumerate(nodes)}
    centro = lado / 2
    crudas = [max(0.5, (mass or {}).get(nodo, 1.0)) for nodo in nodes]
    # Normalizadas a media 1 y combinadas con RAIZ del producto, no el producto
    # crudo: con masas 20x20 la repulsion vencia a la gravedad y el layout
    # explotaba (comprobado: nodos en x=-6969 sobre un lienzo de 1000).
    media = sum(crudas) / len(crudas)
    masas = [m / media for m in crudas]

    lista = []
    for i, nodo in enumerate(nodes):
        if seeds and nodo in seeds:
            lista.append([seeds[nodo][0], seeds[nodo][1]])
        else:
            angulo = 2 * math.pi * i / n
            radio = lado / 2.5
            lista.append([centro + radio * math.cos(angulo), centro + radio * math.sin(angulo)])

    pares = [
        (indice[a], indice[b])
        for a, b in edges
        if a in indice and b in indice and a != b
    ]
    k = math.sqrt((lado * lado) / n)
    gravedad = 0.06
    temperatura = lado / 10.0
    enfriamiento = temperatura / (iteraciones + 1)

    for _ in range(iteraciones):
        desplazamiento = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            xi, yi = lista[i]
            for j in range(i + 1, n):
                dx = xi - lista[j][0]
                dy = yi - lista[j][1]
                dist2 = dx * dx + dy * dy
                if dist2 < 0.01:
                    dx, dy, dist2 = 0.01 * (i + 1), 0.01 * (j + 1), 0.0002
                dist = math.sqrt(dist2)
                # Repulsion escalada por la raiz del producto de masas: lo
                # estructural se abre paso y lo ligero orbita alrededor.
                fuerza = (k * k) / dist * math.sqrt(masas[i] * masas[j])
                ux, uy = dx / dist * fuerza, dy / dist * fuerza
                desplazamiento[i][0] += ux
                desplazamiento[i][1] += uy
                desplazamiento[j][0] -= ux
                desplazamiento[j][1] -= uy
        for a, b in pares:
            dx = lista[a][0] - lista[b][0]
            dy = lista[a][1] - lista[b][1]
            dist = math.sqrt(dx * dx + dy * dy) or 0.01
            fuerza = (dist * dist) / k
            ux, uy = dx / dist * fuerza, dy / dist * fuerza
            desplazamiento[a][0] -= ux
            desplazamiento[a][1] -= uy
            desplazamiento[b][0] += ux
            desplazamiento[b][1] += uy
        for i in range(n):
            # Gravedad lineal hacia el centro, en vez del clamp que fabricaba el
            # rectangulo: los nodos sueltos derivan hacia dentro, no hacia el borde.
            desplazamiento[i][0] += (centro - lista[i][0]) * gravedad
            desplazamiento[i][1] += (centro - lista[i][1]) * gravedad
            dx, dy = desplazamiento[i]
            largo = math.sqrt(dx * dx + dy * dy) or 1.0
            paso = min(largo, temperatura)
            lista[i][0] += dx / largo * paso
            lista[i][1] += dy / largo * paso
        temperatura -= enfriamiento

    # Renormalizar al lienzo al final, conservando la forma (escala uniforme).
    # La dinamica puede acabar donde quiera; lo que el navegador espera es un
    # dibujo dentro de lado x lado, y esto lo garantiza pase lo que pase.
    xs = [p[0] for p in lista]
    ys = [p[1] for p in lista]
    margen = lado * 0.05
    rango = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    escala = (lado - 2 * margen) / rango
    cx0 = (max(xs) + min(xs)) / 2
    cy0 = (max(ys) + min(ys)) / 2
    return {
        nodo: (
            round(centro + (lista[i][0] - cx0) * escala, 2),
            round(centro + (lista[i][1] - cy0) * escala, 2),
        )
        for nodo, i in indice.items()
    }


def _layers(nodes, edges, cycles):
    """Capa de cada módulo: cuánto se puede bajar desde él siguiendo dependencias.

    Los módulos de un mismo ciclo comparten capa a la fuerza (si no, no habría orden
    posible entre ellos: eso es lo que significa un ciclo). Con eso el grafo se
    condensa a un DAG y la profundidad ya está bien definida.
    """
    grupo = {}
    for i, ciclo in enumerate(cycles):
        for mod in ciclo:
            grupo[mod] = "ciclo-%d" % i
    clave = {mod: grupo.get(mod, mod) for mod in nodes}

    condensado = {}
    for mod in nodes:
        origen = clave[mod]
        destinos = condensado.setdefault(origen, set())
        for dep in edges.get(mod, ()):
            if dep in clave and clave[dep] != origen:
                destinos.add(clave[dep])

    profundidad = {}

    def calcula(nodo, visitando):
        if nodo in profundidad:
            return profundidad[nodo]
        if nodo in visitando:  # cinturón: el condensado no deberia tener ciclos
            return 0
        visitando.add(nodo)
        hijos = condensado.get(nodo, ())
        valor = 1 + max((calcula(h, visitando) for h in hijos), default=-1)
        visitando.discard(nodo)
        profundidad[nodo] = valor
        return valor

    for nodo in sorted(condensado):
        calcula(nodo, set())
    return {mod: profundidad.get(clave[mod], 0) for mod in nodes}


def _posiciones(nodes, capas, ancho_nodo=190, alto_fila=92, margen=40):
    por_capa = {}
    for mod in sorted(nodes):
        por_capa.setdefault(capas[mod], []).append(mod)

    posiciones = {}
    ancho_max = 0
    # Capa alta = más profundo. Se pinta arriba lo que NO depende de nadie (las
    # entradas) y abajo los cimientos, que es como se lee un sistema.
    for fila, capa in enumerate(sorted(por_capa, reverse=True)):
        modulos = por_capa[capa]
        for columna, mod in enumerate(modulos):
            posiciones[mod] = (
                margen + columna * ancho_nodo,
                margen + fila * alto_fila,
            )
        ancho_max = max(ancho_max, len(modulos) * ancho_nodo)
    alto = margen * 2 + len(por_capa) * alto_fila
    return posiciones, ancho_max + margen * 2, alto


def _corto(nombre, limite=26):
    if len(nombre) <= limite:
        return nombre
    partes = nombre.split(".")
    corto = partes[-1]
    return ("…" + corto) if len(corto) < limite else ("…" + corto[-(limite - 1):])


#: Color y tamanio POR TIPO, no por modulo — portados tal cual de la paleta de
#: GitNexus (gitnexus-web/src/lib/constants.ts): la jerarquia se lee por tamanio
#: (un modulo ES mas grande que una funcion) y el tipo por color. Con color-por-
#: modulo, dos funciones del mismo fichero eran indistinguibles de su clase.
_KIND_COLOR = {
    "module": "#7c3aed",    # violeta — contenedor
    "class": "#f59e0b",     # ambar — destaca
    "function": "#10b981",  # esmeralda
    "method": "#14b8a6",    # teal
}
_KIND_SIZE = {"module": 13.0, "class": 8.0, "function": 4.0, "method": 3.0}

#: La arista de import. Rosa a proposito: tiene que ser un color que NO esté en
#: _KIND_COLOR. En la primera version reusé el ámbar de las clases y en la
#: pantalla dos clases sueltas parecían parte de la capa de imports — un color
#: repetido es una mentira visual, y esta capa existe justo para separar el
#: hecho exacto de la inferencia.
_COLOR_IMPORT = "#fb7185"

#: Fallback para agrupaciones sin tipo (vista de modulos): paleta ciclica.
_COLORES = [
    "#7c5cff", "#22d3ee", "#f472b6", "#fb923c", "#4ade80",
    "#60a5fa", "#c084fc", "#facc15", "#2dd4bf", "#f87171",
    "#a3e635", "#e879f9",
]


def render_graph_cloud(report, title="galaxy-brain — grafo", modo="simbolos", graph_report=None):
    """La nube: nodos repartidos por fuerzas, coloreados por módulo, navegable.

    Mismo dato que el informe, otro modo de mirarlo — este responde *"¿qué forma
    tiene esto?"* y el de capas responde *"¿qué depende de qué?"*. Las posiciones se
    calculan aquí (deterministas), así que el navegador solo dibuja: ni layout en
    JS, ni librería, ni WebGL.

    Con `graph_report` la página deja de ser el grafo de símbolos y pasa a ser **el**
    grafo: los imports entre módulos entran como una cuarta clase de arista sobre
    nodos que YA estaban ahí (los módulos siempre fueron nodos de esta nube). Así
    hay un solo artefacto en vez de dos que había que juntar de cabeza.

    Lo que NO se funde son los hechos: el import es exacto y es lo único que puede
    gatear; la llamada es inferencia con 93% de recall. Se dibujan distinto y la
    leyenda lo dice, porque mezclarlos en un número acabaría gateando sobre un
    proxy (regla 11).
    """
    lado = 1000.0
    nuevos_n = set(report.get("new_nodes") or [])
    nuevas_c = {tuple(e) for e in (report.get("new_calls") or [])}
    importaciones = []
    if modo == "simbolos":
        kinds = {n["qual"]: n["kind"] for n in report.get("nodes", [])}
        grupo_de = {n["qual"]: n.get("module", "") for n in report.get("nodes", [])}
        # TODOS los simbolos, no solo los que aparecen en llamadas: en la primera
        # version los sueltos ni salian, y "no llamado desde ninguna parte" es
        # precisamente algo que se quiere VER.
        implicados = sorted(kinds)
        llamadas = [(a, b) for a, b, t in report.get("edges", []) if t == "CALLS"]
        # La jerarquia entra al layout como MUELLE y al dibujo como linea tenue:
        # es lo que mantiene cada funcion pegada a su modulo. Sin esto, la mitad
        # de los nodos no tenia nada que los sujetara y la repulsion los lanzaba
        # al borde (el rectangulo de la captura del owner).
        jerarquia = [(a, b) for a, b, t in report.get("edges", []) if t != "CALLS"]
        # Los imports unen modulo con modulo, y los modulos ya son nodos de esta
        # nube. Por eso unificar no exige inventar nada: es una clase de arista
        # mas sobre el mismo lienzo. Que los nombres casen entre los dos
        # analizadores lo garantiza la relacion "graph y symbols ven lo mismo".
        if graph_report:
            importaciones = [tuple(e) for e in (graph_report.get("edge_list") or [])]

        # Siembra jerarquica de GitNexus: modulos en espiral de angulo aureo,
        # cada simbolo junto a su modulo con jitter determinista.
        modulos = sorted({n for n in implicados if kinds.get(n) == "module"})
        aureo = math.pi * (3 - math.sqrt(5))
        centros = {}
        for i, mod in enumerate(modulos):
            radio = (lado / 3.2) * math.sqrt((i + 1) / max(len(modulos), 1))
            centros[mod] = (lado / 2 + radio * math.cos(i * aureo),
                            lado / 2 + radio * math.sin(i * aureo))
        seeds = {}
        for n in implicados:
            if n in centros:
                seeds[n] = centros[n]
            else:
                cx, cy = centros.get(grupo_de.get(n, ""), (lado / 2, lado / 2))
                jx, jy = _jitter(n, lado / 12)
                seeds[n] = (cx + jx, cy + jy)
        masa = {n: {"module": 20.0, "class": 5.0}.get(kinds.get(n), 2.0) for n in implicados}

        # Se emiten las SEMILLAS, no el layout final: el sim corre en el navegador
        # (mismo algoritmo y constantes que force_layout, que queda como gemela de
        # referencia testeable). Es el "Layout optimizing..." de GitNexus — la
        # convergencia animada ES el efecto — y con el sim vivo, arrastrar un nodo
        # y que sus vecinos respondan sale casi gratis. Determinista igual: mismas
        # semillas por hash, mismas iteraciones, cero Math.random().
        pos = seeds
        total = report.get("calls_candidates") or 0
        pct = round(100 * report.get("calls_resolved", 0) / total) if total else 0
        resumen = "%d simbolos · %d llamadas resueltas de %d (%d%%)" % (
            len(implicados), report.get("calls_resolved", 0), total, pct)
        if report.get("baseline_ok"):
            resumen += " · +%d simbolos, +%d llamadas, -%d vs %s" % (
                len(report["new_nodes"]), len(report["new_calls"]),
                report["gone_nodes"], report["since"])
        pie = "sin resolver: " + ", ".join(
            "%s %d" % (k, v) for k, v in sorted((report.get("unresolved") or {}).items())
        )
        color_nodo = lambda n: _KIND_COLOR.get(kinds.get(n), "#64748b")  # noqa: E731
        base_nodo = lambda n: _KIND_SIZE.get(kinds.get(n), 3.0)  # noqa: E731
        leyenda = "".join(
            '<span><i style="background:%s"></i>%s</span>' % (_KIND_COLOR[k], k)
            for k in ("module", "class", "function", "method")
        )
        if importaciones:
            # Se dice de donde sale cada arista: el import es un hecho exacto y la
            # llamada es inferencia. Un grafo que no distingue las dos invita a
            # gatear sobre la mitad que no se puede gatear.
            #
            # El color NO puede repetir ninguno de _KIND_COLOR: en la primera
            # version puse el mismo ambar que ya usaban las clases, y dos clases
            # sueltas se leian como si fueran parte de la capa de imports.
            #
            # Y aqui NO va el porcentaje. El 19% es COBERTURA —cuantas candidatas
            # se resolvieron— y en la leyenda se leia como fiabilidad, o sea justo
            # al reves: las aristas dibujadas son las que SI se resolvieron. El
            # numero exacto ya va en la cabecera, con su denominador.
            leyenda += (
                '<span><i style="background:%s"></i>import (exacto)</span>'
                '<span><i style="background:#94a3b8"></i>llamada (inferida)</span>'
            ) % _COLOR_IMPORT
    else:
        llamadas = [(a, b) for a, b in (report.get("edge_list") or [])]
        jerarquia = []
        implicados = sorted(report.get("fan_in", {}))
        kinds = {m: "module" for m in implicados}
        grupo_de = {m: m.split(".")[0] for m in implicados}
        grupos = sorted({grupo_de.get(n, "") for n in implicados})
        color_grupo = {g: _COLORES[i % len(_COLORES)] for i, g in enumerate(grupos)}
        aureo = math.pi * (3 - math.sqrt(5))
        masa = {n: 1.0 for n in implicados}
        pos = {
            n: (500 + (1000 / 3.2) * math.sqrt((i + 1) / len(implicados)) * math.cos(i * aureo),
                500 + (1000 / 3.2) * math.sqrt((i + 1) / len(implicados)) * math.sin(i * aureo))
            for i, n in enumerate(implicados)
        }
        resumen = "%d modulos · %d aristas · %d ciclo(s)" % (
            report.get("modules", 0), report.get("edges", 0), len(report.get("cycles") or []))
        pie = str(report.get("root", ""))
        color_nodo = lambda n: color_grupo.get(grupo_de.get(n, ""), _COLORES[0])  # noqa: E731
        base_nodo = lambda n: 6.0  # noqa: E731
        leyenda = "".join(
            '<span><i style="background:%s"></i>%s</span>'
            % (color_grupo[g], _html.escape(g.split(".")[-1] or "—"))
            for g in grupos[:12]
        )

    grados = {}
    for a, b in llamadas:
        grados[a] = grados.get(a, 0) + 1
        grados[b] = grados.get(b, 0) + 1

    datos = [
        {
            "id": n,
            "x": pos[n][0],
            "y": pos[n][1],
            "r": round(base_nodo(n) + 0.9 * math.sqrt(grados.get(n, 0)), 2),
            "c": color_nodo(n),
            "g": grupo_de.get(n, ""),
            "k": kinds.get(n, ""),
            "l": n.split(".")[-1],
            "m": masa.get(n, 1.0),
            "nu": 1 if n in nuevos_n else 0,
        }
        for n in implicados
    ]
    import json as _json

    indice = {n: i for i, n in enumerate(implicados)}
    # Cada arista lleva su clase: 1 = llamada (se pinta), 0 = jerarquia (tenue).
    lista_aristas = [
        [indice[a], indice[b], 2 if (a, b) in nuevas_c else 1]
        for a, b in llamadas if a in indice and b in indice
    ] + [
        [indice[a], indice[b], 0] for a, b in jerarquia if a in indice and b in indice
    ] + [
        # Clase 3: import entre modulos. Hecho exacto, no inferencia.
        [indice[a], indice[b], 3] for a, b in importaciones if a in indice and b in indice
    ]

    return _NUBE % {
        "title": _html.escape(title),
        "resumen": _html.escape(resumen),
        "pie": _html.escape(pie),
        "nodos": _json.dumps(datos, ensure_ascii=False),
        "aristas": _json.dumps(lista_aristas),
        "leyenda": leyenda,
        "color_import": _COLOR_IMPORT,
    }


def render_symbols_html(report, title="galaxy-brain — simbolos"):
    """El grafo de símbolos, con su cobertura escrita en la cabecera.

    La cobertura va EN LA IMAGEN a propósito: un grafo parcial que no dice que es
    parcial se lee como completo, y entonces la parte que falta parece que no existe
    en vez de parecer que no se pudo resolver.
    """
    llamadas = [(a, b) for a, b, tipo in report.get("edges", []) if tipo == "CALLS"]
    implicados = {x for par in llamadas for x in par}
    kinds = {n["qual"]: n["kind"] for n in report.get("nodes", [])}
    nodes = sorted(implicados)
    edges = {}
    for a, b in llamadas:
        edges.setdefault(a, []).append(b)

    capas = _layers(nodes, edges, [])
    pos, ancho, alto = _posiciones(nodes, capas, ancho_nodo=210)

    entrantes = {}
    for _a, b in llamadas:
        entrantes[b] = entrantes.get(b, 0) + 1

    lineas = [
        '<path class="arista" data-a="%s" data-b="%s" d="M%d %d C%d %d %d %d %d %d"/>'
        % (_html.escape(a), _html.escape(b),
           pos[a][0] + 80, pos[a][1] + 26, pos[a][0] + 80, pos[a][1] + 60,
           pos[b][0] + 80, pos[b][1] - 20, pos[b][0], pos[b][1])
        for a, b in llamadas if a in pos and b in pos
    ]
    cajas = [
        '<g class="nodo %s" data-mod="%s" transform="translate(%d,%d)">'
        '<rect width="180" height="26" rx="4"/><text x="8" y="17">%s</text>'
        '<text class="peso" x="172" y="17" text-anchor="end">%s</text></g>'
        % (kinds.get(mod, ""), _html.escape(mod), pos[mod][0], pos[mod][1],
           _html.escape(_corto(mod, 30)), entrantes.get(mod, "") or "")
        for mod in nodes
    ]

    total = report.get("calls_candidates") or 0
    pct = round(100 * report.get("calls_resolved", 0) / total) if total else 0
    resumen = "%d simbolos · %d llamadas resueltas de %d candidatas (%d%%)" % (
        len(nodes), report.get("calls_resolved", 0), total, pct,
    )
    return _PAGINA % {
        "title": _html.escape(title),
        "resumen": _html.escape(resumen),
        "raiz": _html.escape(
            "sin resolver: " + ", ".join(
                "%s %d" % (k, v) for k, v in sorted((report.get("unresolved") or {}).items())
            )
        ),
        "ancho": ancho,
        "alto": alto,
        "aristas": "\n".join(lineas),
        "nodos": "\n".join(cajas),
    }


def render_html(report, title="galaxy-brain — mapa"):
    """El informe de `graph.analyze` a un HTML autocontenido."""
    nodes = sorted(report.get("fan_in", {}))
    edges = {}
    for origen, destino in report.get("edge_list") or []:
        edges.setdefault(origen, []).append(destino)
    cycles = report.get("cycles") or []

    en_ciclo = {mod for ciclo in cycles for mod in ciclo}
    nuevos_pares = {frozenset(p) for p in (report.get("new_pairs") or [])}
    violaciones = {
        (v["importer"], v["imported"]) for v in (report.get("violations") or [])
    }

    capas = _layers(nodes, edges, cycles)
    pos, ancho, alto = _posiciones(nodes, capas)

    fan_in = report.get("fan_in", {})
    lineas = []
    for origen in sorted(edges):
        for destino in edges[origen]:
            if origen not in pos or destino not in pos:
                continue
            x1, y1 = pos[origen]
            x2, y2 = pos[destino]
            clase = "arista"
            if (origen, destino) in violaciones:
                clase = "arista prohibida"
            elif frozenset((origen, destino)) in nuevos_pares:
                clase = "arista nueva"
            elif origen in en_ciclo and destino in en_ciclo:
                clase = "arista ciclica"
            lineas.append(
                '<path class="%s" data-a="%s" data-b="%s" d="M%d %d C%d %d %d %d %d %d"/>'
                % (clase, _html.escape(origen), _html.escape(destino),
                   x1 + 80, y1 + 26, x1 + 80, y1 + 60, x2 + 80, y2 - 20, x2 + 80, y2)
            )

    cajas = []
    for mod in nodes:
        x, y = pos[mod]
        clase = "nodo ciclo" if mod in en_ciclo else "nodo"
        peso = fan_in.get(mod, 0)
        cajas.append(
            '<g class="%s" data-mod="%s" transform="translate(%d,%d)">'
            '<rect width="160" height="26" rx="4"/>'
            '<text x="8" y="17">%s</text>'
            '<text class="peso" x="152" y="17" text-anchor="end">%s</text></g>'
            % (clase, _html.escape(mod), x, y, _html.escape(_corto(mod)),
               peso if peso else "")
        )

    resumen = "%d modulos · %d aristas · %d ciclo(s)" % (
        report.get("modules", 0), report.get("edges", 0), len(cycles),
    )
    if report.get("since"):
        resumen += " · nuevo vs %s" % _html.escape(str(report["since"]))

    return _PAGINA % {
        "title": _html.escape(title),
        "resumen": _html.escape(resumen),
        "raiz": _html.escape(str(report.get("root", ""))),
        "ancho": ancho,
        "alto": alto,
        "aristas": "\n".join(lineas),
        "nodos": "\n".join(cajas),
    }


_PAGINA = """<!doctype html>
<meta charset="utf-8">
<title>%(title)s</title>
<style>
  :root{--fondo:#eef1f4;--tinta:#131c24;--suave:#5b6b78;--linea:#c3cdd6;
        --caja:#fff;--borde:#b9c5cf;--ciclo:#a8480f;--nueva:#1f6068;--mala:#96262b}
  @media (prefers-color-scheme:dark){
    :root{--fondo:#0e151b;--tinta:#e4eaef;--suave:#93a4b2;--linea:#2c3c49;
          --caja:#16202a;--borde:#31434f;--ciclo:#e0a05a;--nueva:#59b2b8;--mala:#e0736f}}
  body{margin:0;background:var(--fondo);color:var(--tinta);
       font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
  header{padding:14px 18px;border-bottom:1px solid var(--linea);
         display:flex;gap:18px;align-items:baseline;flex-wrap:wrap}
  h1{font:600 15px/1.2 ui-monospace,Consolas,monospace;margin:0;letter-spacing:-.02em}
  .meta{font:12px/1.4 ui-monospace,Consolas,monospace;color:var(--suave)}
  .leyenda{margin-left:auto;display:flex;gap:14px;font:11px ui-monospace,Consolas,monospace}
  .leyenda span{display:flex;align-items:center;gap:5px;color:var(--suave)}
  .muestra{width:16px;height:2px;display:inline-block}
  svg{display:block;width:100%%;height:calc(100vh - 58px);cursor:grab}
  svg.arrastrando{cursor:grabbing}
  .arista{fill:none;stroke:var(--linea);stroke-width:1.2}
  .arista.ciclica{stroke:var(--ciclo);stroke-width:1.8}
  .arista.nueva{stroke:var(--nueva);stroke-width:2.2}
  .arista.prohibida{stroke:var(--mala);stroke-width:2.2;stroke-dasharray:4 3}
  .nodo rect{fill:var(--caja);stroke:var(--borde)}
  .nodo.ciclo rect{stroke:var(--ciclo);stroke-width:1.6}
  .nodo text{font:12px ui-monospace,Consolas,monospace;fill:var(--tinta)}
  .nodo .peso{fill:var(--suave);font-size:10px}
  .nodo{cursor:default}
  .apagado{opacity:.13}
  .resaltado rect{stroke-width:2}
</style>
<header>
  <h1>%(title)s</h1>
  <span class="meta">%(resumen)s</span>
  <span class="meta">%(raiz)s</span>
  <span class="leyenda">
    <span><i class="muestra" style="background:var(--ciclo)"></i>ciclo</span>
    <span><i class="muestra" style="background:var(--nueva)"></i>nuevo</span>
    <span><i class="muestra" style="background:var(--mala)"></i>frontera</span>
  </span>
</header>
<svg id="lienzo" viewBox="0 0 %(ancho)d %(alto)d">
  <g id="camara">
%(aristas)s
%(nodos)s
  </g>
</svg>
<script>
// Pasar el raton por un modulo apaga lo que no le toca. Es lo unico interactivo:
// la pregunta que se hace uno mirando un mapa es "de que depende ESTE".
const svg = document.getElementById('lienzo'), camara = document.getElementById('camara');
const nodos = [...document.querySelectorAll('.nodo')], aristas = [...document.querySelectorAll('.arista')];
function limpia(){ [...nodos,...aristas].forEach(e=>e.classList.remove('apagado','resaltado')); }
nodos.forEach(n=>{
  const mod = n.dataset.mod;
  n.addEventListener('mouseenter', ()=>{
    const tocados = new Set([mod]);
    aristas.forEach(a=>{ if(a.dataset.a===mod||a.dataset.b===mod){tocados.add(a.dataset.a);tocados.add(a.dataset.b);} });
    nodos.forEach(o=>o.classList.toggle('apagado', !tocados.has(o.dataset.mod)));
    nodos.forEach(o=>o.classList.toggle('resaltado', tocados.has(o.dataset.mod)));
    aristas.forEach(a=>a.classList.toggle('apagado', a.dataset.a!==mod && a.dataset.b!==mod));
  });
  n.addEventListener('mouseleave', limpia);
});
// Pan y zoom sobre el viewBox: sin libreria, y el fichero sigue siendo uno.
let vb = svg.viewBox.baseVal, arrastrando = false, ox = 0, oy = 0;
svg.addEventListener('mousedown', e=>{ arrastrando = true; ox = e.clientX; oy = e.clientY; svg.classList.add('arrastrando'); });
addEventListener('mouseup', ()=>{ arrastrando = false; svg.classList.remove('arrastrando'); });
addEventListener('mousemove', e=>{
  if(!arrastrando) return;
  const k = vb.width / svg.clientWidth;
  vb.x -= (e.clientX - ox) * k; vb.y -= (e.clientY - oy) * k;
  ox = e.clientX; oy = e.clientY;
});
svg.addEventListener('wheel', e=>{
  e.preventDefault();
  const k = e.deltaY > 0 ? 1.1 : 0.9;
  vb.x += vb.width * (1 - k) / 2; vb.y += vb.height * (1 - k) / 2;
  vb.width *= k; vb.height *= k;
}, {passive:false});
</script>
"""


_NUBE = """<!doctype html>
<meta charset="utf-8">
<title>%(title)s</title>
<style>
  /* Oscuro siempre, a proposito: la paleta neon esta diseniada para negro y en
     claro se lava (comprobado en captura real). Compromiso visual, no descuido. */
  :root{--fondo:#0a0d14;--tinta:#e8edf3;--suave:#7d8b9c;--linea:#1e2836;--panel:#111722}
  *{box-sizing:border-box}
  body{margin:0;background:var(--fondo);color:var(--tinta);overflow:hidden;
       font:13px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
  header{position:fixed;top:0;left:0;right:0;z-index:5;padding:10px 14px;
         background:var(--panel);border-bottom:1px solid var(--linea);
         display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  h1{font:600 14px ui-monospace,Consolas,monospace;margin:0;letter-spacing:-.02em}
  .meta{font:11px ui-monospace,Consolas,monospace;color:var(--suave)}
  #estado{font:11px ui-monospace,Consolas,monospace;color:#4ade80;transition:opacity .8s}
  input{background:var(--fondo);border:1px solid var(--linea);color:var(--tinta);
        border-radius:4px;padding:5px 9px;font:12px ui-monospace,Consolas,monospace;width:210px}
  input:focus{outline:2px solid #7c5cff;outline-offset:1px}
  button{background:var(--fondo);border:1px solid var(--linea);color:var(--suave);
         border-radius:4px;padding:4px 9px;font:12px ui-monospace,Consolas,monospace;cursor:pointer}
  button:hover{color:var(--tinta);border-color:var(--suave)}
  .leyenda{display:flex;gap:10px;flex-wrap:wrap;margin-left:auto;
           font:10px ui-monospace,Consolas,monospace;color:var(--suave)}
  .leyenda span{display:flex;align-items:center;gap:4px}
  .leyenda i{width:8px;height:8px;border-radius:50%%;display:inline-block}
  canvas{display:block;cursor:grab}
  canvas.arrastrando{cursor:grabbing}
  #ficha{position:fixed;bottom:12px;left:12px;z-index:5;background:var(--panel);
         border:1px solid var(--linea);border-radius:5px;padding:9px 12px;max-width:460px;
         font:12px ui-monospace,Consolas,monospace;display:none}
  #ficha b{color:var(--tinta)} #ficha span{color:var(--suave)}
  #pie{position:fixed;bottom:12px;right:12px;z-index:5;
       font:10px ui-monospace,Consolas,monospace;color:var(--suave);max-width:40vw;text-align:right}
</style>
<header>
  <h1>%(title)s</h1>
  <span class="meta">%(resumen)s</span>
  <span id="estado">layout optimizando&hellip;</span>
  <input id="buscar" placeholder="buscar simbolo..." autocomplete="off">
  <button id="btnPausa" title="pausar/reanudar la fisica">&#9208;</button>
  <button id="btnEncaja" title="reencuadrar">&#8862;</button>
  <span class="leyenda">%(leyenda)s</span>
</header>
<canvas id="lienzo"></canvas>
<div id="ficha"></div>
<div id="pie">%(pie)s</div>
<script>
// ================= datos =================
const NODOS = %(nodos)s, ARISTAS = %(aristas)s, LADO = 1000;
const IMPORT_COLOR = '%(color_import)s';
const N = NODOS.length;

// ================= simulacion =================
// El mismo algoritmo que force_layout en Python (que queda como gemela de
// referencia con tests); aqui corre EN VIVO, que es el "Layout optimizing..."
// de GitNexus — la convergencia animada ES el efecto. Determinista: semillas
// por hash desde Python, iteraciones fijas, cero Math.random().
const X = NODOS.map(n=>n.x), Y = NODOS.map(n=>n.y);
const M = NODOS.map(n=>Math.max(0.5, n.m||1));
const mediaM = M.reduce((a,b)=>a+b,0)/Math.max(N,1);
for(let i=0;i<N;i++) M[i] /= mediaM;
const K = Math.sqrt(LADO*LADO/Math.max(N,1));
const MAXIT = 300, GRAV = 0.06;
let temp = LADO/10, iter = 0, corriendo = true;
let agarrado = null, cola = 0;   // nodo en arrastre + enfriamiento tras soltar

function paso(){
  const dx = new Float64Array(N), dy = new Float64Array(N);
  for(let i=0;i<N;i++){
    for(let j=i+1;j<N;j++){
      let ax = X[i]-X[j], ay = Y[i]-Y[j];
      let d2 = ax*ax+ay*ay;
      if(d2<0.01){ ax=0.01*(i+1); ay=0.01*(j+1); d2=0.0002; }
      const d = Math.sqrt(d2);
      const f = K*K/d*Math.sqrt(M[i]*M[j]);
      const ux=ax/d*f, uy=ay/d*f;
      dx[i]+=ux; dy[i]+=uy; dx[j]-=ux; dy[j]-=uy;
    }
  }
  for(const par of ARISTAS){
    const a=par[0], b=par[1];
    if(a===b) continue;
    let ax=X[a]-X[b], ay=Y[a]-Y[b];
    const d=Math.sqrt(ax*ax+ay*ay)||0.01;
    const f=d*d/K, ux=ax/d*f, uy=ay/d*f;
    dx[a]-=ux; dy[a]-=uy; dx[b]+=ux; dy[b]+=uy;
  }
  const c = LADO/2;
  for(let i=0;i<N;i++){
    dx[i]+=(c-X[i])*GRAV; dy[i]+=(c-Y[i])*GRAV;
    if(i===agarrado) continue;   // al agarrado lo mueve el raton, no la fisica
    const l=Math.sqrt(dx[i]*dx[i]+dy[i]*dy[i])||1;
    const p=Math.min(l,Math.max(temp,0));
    X[i]+=dx[i]/l*p; Y[i]+=dy[i]/l*p;
  }
  if(iter<MAXIT){ temp -= (LADO/10)/(MAXIT+1); iter++; }
}

// ================= camara =================
const cv = document.getElementById('lienzo'), cx = cv.getContext('2d');
let esc=1, ox=0, oy=0, camaraLibre=false;
function encaje(){
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  for(let i=0;i<N;i++){ x0=Math.min(x0,X[i]); y0=Math.min(y0,Y[i]); x1=Math.max(x1,X[i]); y1=Math.max(y1,Y[i]); }
  const pad=70, w=Math.max(x1-x0,1), h=Math.max(y1-y0,1);
  const e = Math.min((cv.width-2*pad)/w, (cv.height-60-2*pad)/h);
  return [e, pad+(cv.width-2*pad-w*e)/2 - x0*e, 60+pad+(cv.height-60-2*pad-h*e)/2 - y0*e];
}
function medir(){ cv.width=innerWidth; cv.height=innerHeight;
  const r=encaje(); esc=r[0]; ox=r[1]; oy=r[2]; }

// ================= atenuado con tinte =================
// El dimColor de GitNexus: mezclar hacia el color del FONDO conservando el
// matiz, en vez de bajar alfa y dejarlo gris.
function mezcla(hex, f){
  const n=parseInt(hex.slice(1),16), r=(n>>16)&255, g=(n>>8)&255, b=n&255;
  return 'rgb('+Math.round(10+(r-10)*f)+','+Math.round(13+(g-13)*f)+','+Math.round(20+(b-20)*f)+')';
}
NODOS.forEach(n=>{ n.cd = mezcla(n.c, 0.28); });

// ================= vecindario / interaccion =================
const vecinos = NODOS.map(()=>new Set());
ARISTAS.forEach(par=>{ vecinos[par[0]].add(par[1]); vecinos[par[1]].add(par[0]); });
const ficha = document.getElementById('ficha'), buscar = document.getElementById('buscar');
const estado = document.getElementById('estado');
let activo=null, fijado=null, filtro='';

function muestraFicha(i){
  if(i===null){ ficha.style.display='none'; return; }
  const n=NODOS[i];
  ficha.innerHTML='<b>'+n.id+'</b><br><span>'+(n.k||'')+' &middot; '+vecinos[i].size+
    ' conexiones &middot; '+(n.g||'')+'</span>';
  ficha.style.display='block';
}

// ================= dibujo =================
function pinta(t){
  cx.clearRect(0,0,cv.width,cv.height);
  const foco = fijado!==null ? fijado : activo;
  const cerca = foco!==null ? vecinos[foco] : null;
  // Respiracion en espacio de DIBUJO, no de fisica: la estructura queda quieta
  // y el grafo respira. Fase por indice: determinista.
  const WX=new Float64Array(N), WY=new Float64Array(N);
  const vivo = iter>=MAXIT ? 1 : 0;
  for(let i=0;i<N;i++){
    WX[i]=X[i]*esc+ox + vivo*2.2*Math.sin(t/1100+i*2.1);
    WY[i]=Y[i]*esc+oy + vivo*2.2*Math.cos(t/1300+i*1.3);
  }
  cx.lineWidth=1;
  // Orden de pintado = orden de lectura. Jerarquia (0) casi invisible debajo,
  // solo sujeta; imports entre modulos (3) como esqueleto ambar, que es el hecho
  // exacto; llamadas (1) encima; lo nuevo (2) en cian, que es lo que se mira.
  for(const capa of [0,3,1,2]) for(const par of ARISTAS){
    const a=par[0], b=par[1], tp=par[2]|0;
    if(tp!==capa) continue;
    const tocada = foco!==null && (a===foco || b===foco);
    if(foco!==null && !tocada){ cx.globalAlpha=0.02; }
    else { cx.globalAlpha = tocada ? 0.9 : (capa===0 ? 0.09 : capa===3 ? 0.5 : (capa===2 ? 0.7 : 0.3)); }
    cx.strokeStyle = capa===2 ? '#22d3ee' : capa===3 ? IMPORT_COLOR : NODOS[a].c;
    cx.lineWidth = capa===3 ? 1.8 : 1;
    cx.beginPath(); cx.moveTo(WX[a],WY[a]); cx.lineTo(WX[b],WY[b]); cx.stroke();
  }
  cx.lineWidth=1;
  cx.globalAlpha=1;
  const fase=(Math.sin(t/180)+1)/2;   // pulso de busqueda: formula de GitNexus
  for(let i=0;i<N;i++){
    const n=NODOS[i];
    const coincide = filtro && n.id.toLowerCase().includes(filtro);
    const relacionado = foco===null || i===foco || cerca.has(i);
    let rr = n.r*Math.min(Math.max(esc,0.55),1.6);
    rr *= 1 + vivo*0.05*Math.sin(t/900+i*2.4);          // respiracion
    let color = n.c;
    if(filtro && !coincide){ color=n.cd; }
    else if(foco!==null && !relacionado){ color=n.cd; }
    if(coincide){ rr *= 1.2+fase*0.5; if(fase>0.5) color='#06b6d4'; }
    if(i===foco){ rr *= 1+0.12*Math.sin(t/250); }
    cx.beginPath(); cx.arc(WX[i],WY[i],rr,0,6.284);
    cx.fillStyle=color; cx.fill();
    if(n.nu){ cx.strokeStyle='#22d3ee'; cx.lineWidth=1.2; cx.stroke(); cx.lineWidth=1; }
    if(i===foco || coincide){
      cx.strokeStyle='#fff'; cx.lineWidth=1.5; cx.stroke(); cx.lineWidth=1;
      cx.fillStyle='#e8edf3'; cx.font='11px ui-monospace,Consolas,monospace';
      cx.fillText(n.l, WX[i]+rr+4, WY[i]+3);
    }
  }
}

// ================= bucle =================
function bucle(t){
  if(N>1){
    if(corriendo && iter<MAXIT){
      for(let s=0;s<3 && iter<MAXIT;s++) paso();
      if(!camaraLibre){ const r=encaje(); esc+=(r[0]-esc)*0.08; ox+=(r[1]-ox)*0.08; oy+=(r[2]-oy)*0.08; }
      if(iter>=MAXIT) estado.style.opacity=0;
    } else if(agarrado!==null || cola>0){
      // Fisica local al arrastrar: los vecinos responden; al soltar, se enfria.
      temp=Math.max(temp,10); paso();
      if(agarrado===null) cola--;
    }
  } else { estado.style.opacity=0; }
  pinta(t);
  requestAnimationFrame(bucle);
}

// ================= raton =================
function nodoEn(mx,my){
  let mejor=null, dmin=16;
  for(let i=0;i<N;i++){
    const d=Math.hypot(X[i]*esc+ox-mx, Y[i]*esc+oy-my);
    if(d<dmin){ dmin=d; mejor=i; }
  }
  return mejor;
}
let panning=false, lx=0, ly=0, movido=false;
cv.addEventListener('mousedown', e=>{
  movido=false; lx=e.clientX; ly=e.clientY;
  const i=nodoEn(e.clientX,e.clientY);
  if(i!==null){ agarrado=i; camaraLibre=true; }
  else { panning=true; cv.classList.add('arrastrando'); }
});
addEventListener('mousemove', e=>{
  if(Math.hypot(e.clientX-lx,e.clientY-ly)>3) movido=true;
  if(agarrado!==null){
    X[agarrado]=(e.clientX-ox)/esc; Y[agarrado]=(e.clientY-oy)/esc;
    return;
  }
  if(panning){ ox+=e.clientX-lx; oy+=e.clientY-ly; lx=e.clientX; ly=e.clientY; camaraLibre=true; return; }
  const i=nodoEn(e.clientX,e.clientY);
  if(i!==activo){ activo=i; if(fijado===null) muestraFicha(i); }
});
addEventListener('mouseup', e=>{
  if(agarrado!==null){
    if(!movido){ fijado = (fijado===agarrado) ? null : agarrado; muestraFicha(fijado); }
    else cola=90;
    agarrado=null;
  } else if(panning && !movido){ fijado=null; muestraFicha(null); }
  panning=false; cv.classList.remove('arrastrando');
});
cv.addEventListener('wheel', e=>{
  e.preventDefault(); camaraLibre=true;
  const k = e.deltaY>0 ? 0.9 : 1.1;
  ox = e.clientX-(e.clientX-ox)*k; oy = e.clientY-(e.clientY-oy)*k; esc*=k;
}, {passive:false});
buscar.addEventListener('input', e=>{ filtro=e.target.value.trim().toLowerCase(); });
document.getElementById('btnPausa').addEventListener('click', ev=>{
  corriendo=!corriendo; ev.target.innerHTML = corriendo ? '&#9208;' : '&#9654;';
});
document.getElementById('btnEncaja').addEventListener('click', ()=>{
  const r=encaje(); esc=r[0]; ox=r[1]; oy=r[2];
});
addEventListener('resize', ()=>{ if(!camaraLibre) medir(); else { cv.width=innerWidth; cv.height=innerHeight; } });
medir(); requestAnimationFrame(bucle);
</script>
"""
