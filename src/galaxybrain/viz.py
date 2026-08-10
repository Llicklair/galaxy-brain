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

**UN solo grafo, y una sola página.** Había tres renderizadores para el mismo sujeto
—módulos en SVG, símbolos en lienzo, capas en SVG— con su CSS y su JS cada uno, y había
que juntarlos de cabeza. Quedó uno.

Los módulos siempre fueron nodos de esta nube, así que los imports entraron como una
clase de arista más sobre lo que ya se dibujaba. Y `--capas` dejó de ser otra página para
ser otra **siembra** de este mismo lienzo: las posiciones salen de la profundidad de
dependencias en vez de la espiral áurea, y el sim no corre —la física desharía justo el
orden que esa vista existe para enseñar—. Misma plantilla, mismas interacciones, misma
pregunta respondida.

Lo que NO se funde son los hechos. El import sale de una declaración: es exacto y es lo
único que puede gatear. La llamada sale de inferencia, con su porcentaje de resolución
dicho en la cabecera. Se pintan distinto y la leyenda lo separa, porque un número que
mezclara ambos acabaría gateando sobre un proxy (regla 11).

Los ciclos van marcados por encima de su capa: son el único hecho de este mapa que
detiene un commit. Con `--since`, lo NUEVO va aparte — ver crecer un proyecto es, sobre
todo, ver qué apareció desde la última vez.

**Cero dependencias, un fichero.** Ni CDN, ni npm, ni build: el HTML se escribe entero y
se abre con doble clic. No es purismo — la regla de cero dependencias existe para que
`gb` entre en el venv de cualquier proyecto sin arrastrar nada, y un visor no es motivo
para romperla.
"""

import hashlib as _hashlib
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


_KIND_COLOR = {
    "module": "#7c3aed",    # violeta — contenedor
    "class": "#f59e0b",     # ambar — destaca
    "function": "#10b981",  # esmeralda
    # Azul, no teal. El teal (#14b8a6) estaba a ΔE 5,4 del esmeralda en vision
    # NORMAL — el suelo son 15 — y function+method son la inmensa mayoria de los
    # nodos, o sea que la nube entera era una mancha verde indistinguible. Medido
    # el 5-ago-2026 con el validador de paleta; con azul el par sube a ΔE 21,1
    # (8,9 en protanopia, sobre el suelo de 8).
    "method": "#60a5fa",    # azul
}
_KIND_SIZE = {"module": 13.0, "class": 8.0, "function": 4.0, "method": 3.0}


def _en_script(json_texto):
    """JSON apto para vivir DENTRO de un <script>: '<' viaja como \\u003c.

    Un nombre de worktree o un docstring que contenga '</script>' cerraria la
    etiqueta y ejecutaria lo que venga detras como HTML. Cazado el 5-ago-2026
    por el test de inyeccion de la leyenda de agentes; el payload de nodos tenia
    la MISMA exposicion desde antes (los docstrings viajan en el campo 'd').
    El reemplazo es JSON valido — \\u003c es el mismo caracter, solo que inerte.
    """
    return json_texto.replace("<", "\\u003c")


def _rgba(hexa, alfa):
    """'#e879f9' -> 'rgba(232,121,249,.3)'. Para que la leyenda pueda dibujar el
    halo con la MISMA transparencia con la que lo pinta el lienzo."""
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "rgba(%d,%d,%d,%s)" % (r, g, b, ("%.2f" % alfa).rstrip("0").rstrip("."))

#: La arista de import. Rosa a proposito: tiene que ser un color que NO esté en
#: _KIND_COLOR. En la primera version reusé el ámbar de las clases y en la
#: pantalla dos clases sueltas parecían parte de la capa de imports — un color
#: repetido es una mentira visual, y esta capa existe justo para separar el
#: hecho exacto de la inferencia.
_COLOR_IMPORT = "#fb7185"

#: El ciclo. Rojo, y por encima de la capa a la que pertenezca la arista: es el
#: unico hecho de este grafo que detiene un commit, asi que no puede competir de
#: igual a igual con el resto de colores.
_COLOR_CICLO = "#ef4444"

#: El ciclo del error sobre un nodo (borde discontinuo, no relleno: el color del
#: nodo sigue diciendo su tipo). El rojo queda reservado al ciclo de imports —
#: lo unico que bloquea—; esto INFORMA (regla 11) con su propia escala. Y el
#: ultimo eslabon se llama "en-silencio", no otra cosa: gb no re-ejecuta nada,
#: asi que la ausencia de ocurrencias es solo eso, ausencia con ventana.
_CICLO_ERROR_COLOR = {
    "capturada": "#f97316",    # naranja — capturada y sin leer, pendiente
    "leida": "#facc15",        # amarillo — leida, aun sin commit posterior
    "intervenida": "#38bdf8",  # azul — tocado despues del fallo
    "en-silencio": "#4ade80",  # verde — sin reaparecer desde la intervencion
}

#: La capa de cambio: el nodo cuyo fichero esta TOCADO respecto a HEAD (trabajo
#: en curso sin commitear). Es un HALO RELLENO translucido bajo el nodo, no otro
#: anillo: todo lo demas son strokes (rojo del ciclo de imports, cian de lo
#: nuevo, discontinuos del ciclo del error) y un cuarto trazo compitiendo en el
#: mismo borde seria ilegible — se distingue por FORMA ademas de por color.
#: Fucsia: no esta en _KIND_COLOR, ni es el rosa del import, ni pisa la escala
#: naranja/amarillo/azul/verde del ciclo del error. "Tocado" es un hecho de git,
#: nunca un veredicto (regla 9): informa, no bloquea.
_COLOR_OBRA = "#e879f9"

#: Un color POR AGENTE. "En obra" (fucsia) es un estado del arbol —tocado sin
#: commitear— y "un agente trabajando aqui" es otra cosa: pintarlas igual daba el
#: protagonismo a la señal equivocada. Validados a todos los pares el 5-ago-2026:
#: ΔE 20,6 en vision normal y 8,6 en deuteranopia (suelos 15 y 8).
_COLOR_AGENTE = ["#ff4d9d", "#a3e635", "#22d3ee", "#fb923c"]
#: A partir del quinto no se generan tonos nuevos: se comparte uno neutro y la
#: consola sigue diciendo el nombre. Inventar el color 9 es como se fabrica una
#: paleta que ya no distingue nada.
_COLOR_AGENTE_EXTRA = "#94a3b8"

#: Fallback para agrupaciones sin tipo (vista de modulos): paleta ciclica.
_COLORES = [
    "#7c5cff", "#22d3ee", "#f472b6", "#fb923c", "#4ade80",
    "#60a5fa", "#c084fc", "#facc15", "#2dd4bf", "#f87171",
    "#a3e635", "#e879f9",
]


def render_graph_cloud(
    report,
    title="galaxy-brain — grafo",
    modo="simbolos",
    graph_report=None,
    procedencia=None,
    capas=False,
    refresco=0,
    ciclo=None,
    tocados=None,
    actividad=None,
    capturas=None,
    suelo=None,
    sin_leer=0,
    # Epoch de generacion, puesto por QUIEN LLAMA (como el pie): el render sigue
    # siendo determinista y el JS puede envejecer la actividad con la edad real.
    gen_ts=None,
):
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
    maxit = 300  # iteraciones del sim en el navegador; 0 = posiciones definitivas
    nuevos_n = set(report.get("new_nodes") or [])
    nuevas_c = {tuple(e) for e in (report.get("new_calls") or [])}
    importaciones = []

    # Los ciclos son lo UNICO que bloquea un commit, asi que no pueden ser un
    # color mas: se marcan el nodo y el tramo. La fuente es el informe de grafo
    # —el de simbolos no los calcula— venga como informe principal (modo modulos)
    # o como acompanante (modo unificado).
    fuente_ciclos = graph_report if graph_report else report
    ciclos = fuente_ciclos.get("cycles") or []
    en_ciclo = {n for ciclo in ciclos for n in ciclo}
    pasos_ciclicos = {
        (ciclo[i], ciclo[(i + 1) % len(ciclo)]) for ciclo in ciclos for i in range(len(ciclo))
    }
    if modo == "simbolos":
        kinds = {n["qual"]: n["kind"] for n in report.get("nodes", [])}
        grupo_de = {n["qual"]: n.get("module", "") for n in report.get("nodes", [])}
        # La prosa que explica cada simbolo ya esta escrita y vive pegada a el.
        # No hay que generarla, hay que recogerla — y asi el mapa se explica con
        # las palabras de quien escribio el codigo, no con las de un modelo.
        docs = {n["qual"]: (n.get("doc") or "") for n in report.get("nodes", [])}
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
        if capas:
            # `--capas` PLEGADA: deja de ser otra pagina y pasa a ser otra siembra
            # de este mismo lienzo. Responde la misma pregunta que antes —"¿que
            # depende de que?", en orden— pero con las mismas interacciones (zoom,
            # busqueda, foco) y una sola plantilla que mantener.
            #
            # Y sin simulacion: la fisica desharia justo el orden que esta vista
            # existe para ensenar. Por eso `maxit` baja a 0.
            aristas_capa = {}
            for a, b in llamadas:
                aristas_capa.setdefault(a, []).append(b)
            niveles = _layers(implicados, aristas_capa, [])
            por_nivel = {}
            for n in implicados:
                por_nivel.setdefault(niveles.get(n, 0), []).append(n)
            hondo = max(por_nivel) or 1
            margen = lado * 0.06
            util = lado - 2 * margen
            pos = {
                n: (
                    margen + util * ((k + 0.5) / len(fila)),
                    margen + util * (nivel / hondo),
                )
                for nivel, fila in por_nivel.items()
                for k, n in enumerate(sorted(fila))
            }
            maxit = 0
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
            # Aristas: se dibujan como LINEA, no como punto.
            leyenda += (
                '<span><i class="linea" style="color:%s"></i>import (exacto)</span>'
                '<span><i class="linea" style="color:#94a3b8"></i>llamada (inferida)</span>'
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

    # El ciclo del error viene ya computado por quien llama (como la procedencia:
    # este renderizador no lee historico ni git, solo dibuja datos de entrada).
    info_ciclo = (ciclo or {}).get("nodos") or {}
    if info_ciclo:
        # Aro discontinuo, que es como se dibuja en el lienzo (no punto relleno).
        leyenda += "".join(
            '<span><i class="aro" style="color:%s"></i>%s</span>' % (_CICLO_ERROR_COLOR[e], e)
            for e in ("capturada", "leida", "intervenida", "en-silencio")
        )

    # La capa de cambio viene, como el ciclo, ya computada por quien llama: este
    # renderizador no ejecuta git, solo dibuja. Sin repo (o sin nada tocado) el
    # conjunto llega vacio y la capa calla entera: ni leyenda, ni cabecera.
    tocados = set(tocados or ())

    # La actividad viene ya derivada por quien llama (como el ciclo y la capa de
    # cambio): este renderizador no ejecuta git ni recorre worktrees, solo dibuja.
    # Sin agentes vivos, el diccionario llega vacio y la consola no existe.
    _act = actividad or {}
    _por_nodo = {q: d.get("agentes", []) for q, d in (_act.get("por_nodo") or {}).items()
                 if d.get("agentes")}
    _orden_agentes = sorted(a["nombre"] for a in (_act.get("agentes") or []))
    _color_agente = {
        nombre: (_COLOR_AGENTE[i] if i < len(_COLOR_AGENTE) else _COLOR_AGENTE_EXTRA)
        for i, nombre in enumerate(_orden_agentes)
    }
    _agentes_js = {
        a["nombre"]: {
            "c": _color_agente.get(a["nombre"], _COLOR_AGENTE_EXTRA),
            "nodos": len(a.get("nodos") or []),
            "vecinos": len(a.get("vecinos") or []),
            "hace": a.get("hace_seg"),
            "fuera": a.get("fuera_del_mapa", 0),
            "base": a.get("base", ""),
            "misma": 1 if a.get("misma_base") else 0,
            # Qué escribió, exactamente: firmas contra el mapa canónico. La
            # consola convierte cada uno en un evento `escribe` con sustancia.
            "cambios": a.get("cambios") or [],
            # Su consola en vivo (stdout del agente): la terminal del lienzo.
            "consola": a.get("consola") or [],
            # El veredicto del GRAFO sobre su trabajo, si corre con escalera.
            # Va al mapa porque un bucle que acepta codigo sin que nadie lo mire
            # no puede ser opaco: que decidio y por que tiene que verse.
            "escalera": a.get("escalera") or None,
        }
        for a in (_act.get("agentes") or [])
    }
    en_obra = sorted(n for n in implicados if n in tocados)
    if en_obra:
        # Halo por detras al 30%%, igual que en el lienzo: el nodo conserva su
        # color de tipo y el fucsia solo lo rodea.
        leyenda += (
            '<span><i style="background:#64748b;box-shadow:0 0 0 3px %s"></i>'
            'en obra (sin commitear)</span>' % _rgba(_COLOR_OBRA, 0.3)
        )

    if _agentes_js:
        # Las marcas del lienzo se explican, pero los NOMBRES no entran aqui.
        #
        # La leyenda es el vocabulario del mapa —modulo, clase, funcion, metodo,
        # import, llamada, ciclo— y un vocabulario que cambia segun quien este
        # trabajando deja de ser vocabulario: cada agente que entraba o salia
        # reescribia la fila y movia de sitio lo estable (reportado en uso real,
        # 8-ago). Quien es cada color ya lo dice SU tarjeta, que es donde el
        # nombre significa algo. Aqui solo se explica la marca, una vez.
        vivos = sorted(_agentes_js)
        leyenda += '<span class="efimero"><i class="agente" style="color:%s"></i>' \
                   'agente (su color, en su tarjeta)</span>' % _agentes_js[vivos[0]]["c"]
        if len(vivos) > 1:
            # El aro blanco solo puede aparecer con dos o mas agentes vivos, asi
            # que la entrada solo existe entonces (una leyenda que explica marcas
            # imposibles tambien miente).
            # Mismo nombre que en la consola (CRUCE): un hecho, un nombre.
            leyenda += '<span><i class="agente" style="color:#fff"></i>CRUCE (2+ a la vez)</span>'
        # La sinapsis: cada arista que sale de un nodo tocado fluye con el color
        # de su agente. La entrada es una (la forma explica; el color varia).
        leyenda += (
            '<span><i class="linea" style="color:#94a3b8"></i>'
            "se&ntilde;al fluyendo hacia su onda</span>"
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
            "ci": 1 if n in en_ciclo else 0,
            "d": (docs.get(n, "") if modo == "simbolos" else "")[:160],
            # Estado del ciclo del error del nodo: color del borde, etiqueta y la
            # cadena por firma para la ficha. Vacio si el fichero no tiene capturas.
            "ec": _CICLO_ERROR_COLOR.get(info_ciclo.get(n, {}).get("estado"), ""),
            "ee": info_ciclo.get(n, {}).get("estado", ""),
            "el": info_ciclo.get(n, {}).get("lineas", []),
            # Capa de cambio: 1 si el fichero de este nodo esta tocado sin commitear.
            "tc": 1 if n in tocados else 0,
            # Que agentes (worktrees) estan tocando este nodo AHORA. Derivado del
            # disco, nadie lo declara. Vacio cuando no hay nadie trabajando.
            "ag": _por_nodo.get(n, []),
        }
        for n in implicados
    ]
    import json as _json

    indice = {n: i for i, n in enumerate(implicados)}
    # Cada arista lleva su clase: 1 = llamada (se pinta), 0 = jerarquia (tenue).
    # Cuarto elemento: 1 si el tramo cierra un ciclo. Va aparte de la clase porque
    # un ciclo puede recorrer aristas de cualquier capa, y porque es el unico hecho
    # que detiene un commit: tiene que verse por encima de todo lo demas.
    lista_aristas = [
        [indice[a], indice[b], 2 if (a, b) in nuevas_c else 1, 1 if (a, b) in pasos_ciclicos else 0]
        for a, b in llamadas if a in indice and b in indice
    ] + [
        [indice[a], indice[b], 0, 1 if (a, b) in pasos_ciclicos else 0]
        for a, b in jerarquia if a in indice and b in indice
    ] + [
        # Clase 3: import entre modulos. Hecho exacto, no inferencia.
        [indice[a], indice[b], 3, 1 if (a, b) in pasos_ciclicos else 0]
        for a, b in importaciones if a in indice and b in indice
    ]

    # La procedencia la inyecta quien llama, NO se lee del reloj aqui: si este
    # renderizador mirara la hora dejaria de ser determinista, y dos capturas del
    # mismo proyecto no se podrian comparar byte a byte. Mismo dato de entrada,
    # mismo fichero — el que cambia es el dato, no la funcion.
    if procedencia:
        pie = "%s  ·  %s" % (procedencia, pie) if pie else procedencia

    # La procedencia del MOTOR, no solo del dato: el hash de la plantilla en el
    # pie. Se persiguio media hora a un fantasma (un hook regenerando el mapa
    # con bytecode rancio) porque el HTML no decia QUE codigo lo genero; con
    # esto, dos generadores desfasados se delatan a simple vista.
    motor = _hashlib.sha1(_NUBE.encode("utf-8")).hexdigest()[:8]
    pie = "%s  ·  motor %s" % (pie, motor) if pie else "motor %s" % motor

    return _NUBE % {
        "title": _html.escape(title),
        "resumen": _html.escape(resumen),
        "pie": _html.escape(pie),
        "nodos": _en_script(_json.dumps(datos, ensure_ascii=False)),
        "aristas": _en_script(_json.dumps(lista_aristas)),
        # Epoch de generacion: el JS calcula con el la edad REAL de la actividad
        # (la que tenia al generarse + lo que la pagina lleva servida). Sin esto,
        # una foto estatica anima flujo eternamente y lee como "pasando ahora".
        # `null` cuando quien llama no lo sella: el JS envejece entonces solo
        # con el tiempo de pagina abierta.
        "gen_ts": str(int(gen_ts)) if gen_ts is not None else "null",
        "leyenda": leyenda,
        # El embudo del ciclo del error en la cabecera, ya formateado por quien
        # llama. Cadena vacia (ni hueco) si el proyecto no tiene capturas.
        "ciclo": (
            '\n  <span class="meta">ciclo: %s</span>' % _html.escape(ciclo["embudo"])
            if ciclo and ciclo.get("embudo")
            else ""
        ),
        # La capa de cambio en la cabecera, solo si hay algo: una linea fija de
        # ceros en cada mapa seria ruido repetido (H6). El recuento es de NODOS
        # marcados, que es lo que el ojo va a buscar en el lienzo.
        "obra": (
            '\n  <span class="meta">en obra: %d modulo(s) tocado(s) sin commitear</span>'
            % len(en_obra)
            if en_obra
            else ""
        ),
        "color_import": _COLOR_IMPORT,
        "color_ciclo": _COLOR_CICLO,
        "color_obra": _COLOR_OBRA,
        "agentes": _en_script(_json.dumps(_agentes_js, ensure_ascii=False)),
        # La consola de errores entra al lienzo por defecto: las capturas
        # recientes, con su nodo, para que el feed diga `peta` en movimiento.
        "capturas": _en_script(_json.dumps(capturas or [], ensure_ascii=False)),
        # El recuento REAL de capturas sin leer del proyecto: la ventana de 10
        # de arriba no puede contarlas todas y un numero a medias miente.
        "sin_leer": str(int(sin_leer or 0)),
        "suelo": (
            '\n  <span class="meta">suelo: %s</span>' % _html.escape(suelo)
            if suelo else ""
        ),
        "maxit": maxit,
        # Recargar la pagina no la actualiza sola: hace falta que ALGO regenere el
        # fichero. Por eso esto es opt-in y no el defecto — un refresco sobre un
        # fichero que nadie regenera solo consigue parpadear.
        # Recarga por JS, no <meta http-equiv>: el meta no se puede aplazar, y
        # una recarga que te borra lo tecleado en buscar enseña a no buscar.
        "refresco": str(int(refresco or 0)),
    }


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
  /* Lo EFIMERO (quien trabaja ahora) va detras de una linea: el vocabulario
     del mapa no se mezcla con quien esta de paso. */
  .leyenda span.efimero{border-left:1px solid var(--linea);padding-left:10px;margin-left:2px}
  .leyenda i{width:8px;height:8px;border-radius:50%%;display:inline-block}
  /* Cada entrada se dibuja CON LA MARCA QUE USA EL LIENZO. Con todas como punto
     relleno, la leyenda prometia un nodo naranja solido para "capturada" y lo que
     hay en el mapa es un aro discontinuo: buscabas algo que no existe. */
  .leyenda i.aro{background:transparent;border:1.6px dashed currentColor;
                 width:9px;height:9px}
  .leyenda i.linea{width:14px;height:0;border-radius:0;border-top:2px solid currentColor}
  /* Agente: aro SOLIDO del color del agente alrededor del nodo — la marca del
     lienzo. Distinto del aro discontinuo (ciclo del error) y del halo difuso
     (capa de cambio). */
  .leyenda i.agente{background:#64748b;border:2px solid currentColor;width:7px;height:7px}
  canvas{display:block;cursor:grab}
  canvas.arrastrando{cursor:grabbing}
  /* A la DERECHA y alto: en hover es una vista de paso; al hacer clic queda
     fijado y el hover deja de cambiarlo, para poder leerlo con calma mientras
     se mira otra cosa del mapa. */
  #ficha{position:fixed;top:92px;right:12px;z-index:5;background:var(--panel);
         border:1px solid var(--linea);border-radius:6px;padding:10px 13px;width:340px;
         max-height:calc(100vh - 120px);overflow-y:auto;opacity:.93;
         font:12px ui-monospace,Consolas,monospace;display:none}
  #ficha.fijado{opacity:1;border-color:#7c5cff;box-shadow:0 8px 28px rgba(0,0,0,.55)}
  #ficha b{color:var(--tinta)} #ficha span{color:var(--suave)}
  #ficha .cerrar{float:right;margin-left:8px;cursor:pointer;color:var(--suave);
                 font-weight:700;line-height:1}
  #ficha .cerrar:hover{color:var(--tinta)}
  #ficha .pista{display:block;margin-top:7px;padding-top:6px;
                border-top:1px solid var(--linea);color:var(--suave);font-size:10px}
  /* La consola de actividad: el VIDEO, donde el mapa es la foto. Cada recarga
     deriva eventos comparando la instantanea actual con la anterior (guardada
     en el navegador): toco, solto, creo, se cruzo. Hechos con hora. */
  #consola{position:fixed;bottom:12px;left:12px;z-index:5;background:var(--panel);
           border:1px solid var(--linea);border-radius:6px;width:410px;max-height:38vh;
           overflow-y:auto;font:11px ui-monospace,Consolas,monospace;display:none;
           /* sin padding SUPERIOR: la cabecera sticky se pegaba 5px por debajo
              del borde y las filas asomaban por encima */
           padding:0 0 5px}
  #consola .cab,#errores .cab{position:sticky;top:0;display:flex;justify-content:space-between;
           align-items:center;padding:3px 10px;background:var(--panel);
           border-bottom:1px solid var(--linea);color:var(--suave);cursor:move}
  #consola .cab b,#errores .cab b{cursor:pointer;padding:0 5px;font-weight:700;user-select:none}
  #consola .cab b:hover,#errores .cab b:hover{color:var(--tinta)}
  #consola .fila,#errores .fila{padding:2px 10px;display:flex;gap:7px;align-items:baseline}
  #consola .hora,#errores .hora{color:var(--suave);flex:none}
  #consola .quien,#errores .quien{font-weight:700;flex:none}
  #consola .que,#errores .que{color:var(--tinta);flex:none}
  #consola .detalle,#errores .detalle{color:var(--suave);word-break:break-all}
  /* La consola de ERRORES, separada de la de actividad a proposito: mezclarlas
     enterraba las capturas bajo los toca/escribe de una tirada (6-ago). */
  #errores{position:fixed;bottom:34px;right:12px;z-index:5;background:var(--panel);
           border:1px solid var(--linea);border-radius:6px;width:380px;max-height:32vh;
           overflow-y:auto;font:11px ui-monospace,Consolas,monospace;display:none;
           padding:0 0 5px}
  #pie{position:fixed;bottom:12px;right:12px;z-index:5;
       font:10px ui-monospace,Consolas,monospace;color:var(--suave);max-width:40vw;text-align:right}
  /* La terminal del agente: su consola cmd EN VIVO, anclada encima de sus
     nodos. Refleja su stdout (teeado por el orquestador al lado del worktree),
     no una interpretacion. Clic: foco en ese agente. */
  #terminales .term{position:fixed;z-index:4;transform:translate(-50%%,-100%%);
        background:#04070c;border:1px solid rgba(255,255,255,.14);border-radius:6px;
        padding:3px 7px;width:240px;font:9px/1.5 ui-monospace,Consolas,monospace;
        cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.5)}
  #terminales .tcab{font-weight:700;margin-bottom:1px;font-size:10px;
        display:flex;align-items:center;gap:4px}
  #terminales .tdat{margin-left:auto;color:var(--suave);font-weight:400;font-size:9px}
  #terminales .tav{color:#f59e0b;font-size:9px;white-space:nowrap;overflow:hidden;
        text-overflow:ellipsis}
  #terminales .term.foco{border-color:#7c5cff;box-shadow:0 8px 24px rgba(0,0,0,.6)}
  #terminales .tbot{margin-left:6px}
  #terminales .tcab b{cursor:pointer;color:var(--suave);font-weight:700;
        padding:0 3px;user-select:none}
  #terminales .tcab b:hover{color:#fff}
  #terminales .tl{color:#9fb0c0;white-space:nowrap;overflow:hidden;
        text-overflow:ellipsis}
  #terminales .cur{animation:parpadeo 1s steps(1) infinite}
  #terminales .tl.nueva{animation:caer .35s ease-out}
  #hilos .hilo{position:fixed;z-index:3;height:0;border-top:1px dashed;
        opacity:.55;pointer-events:none;transform-origin:0 0}
  @keyframes parpadeo{50%%{opacity:0}}
  @keyframes caer{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
</style>
<header>
  <h1>%(title)s</h1>
  <span class="meta">%(resumen)s</span>%(ciclo)s%(suelo)s%(obra)s
  <span id="estado">layout optimizando&hellip;</span>
  <input id="buscar" placeholder="buscar simbolo..." autocomplete="off">
  <button id="btnPausa" title="pausar/reanudar la fisica">&#9208;</button>
  <button id="btnEncaja" title="reencuadrar">&#8862;</button>
  <button id="btnConsola" title="consola de actividad de los agentes">&#8801;</button>
  <button id="btnErrores" title="consola de errores (capturas de gb)">&#9888;</button>
  <span class="leyenda">%(leyenda)s</span>
</header>
<canvas id="lienzo"></canvas>
<div id="ficha"></div>
<div id="terminales"></div>
<div id="consola"></div>
<div id="errores"></div>
<div id="pie">%(pie)s</div>
<script>
// ================= datos =================
const NODOS = %(nodos)s, ARISTAS = %(aristas)s, LADO = 1000, GEN_TS = %(gen_ts)s;
const IMPORT_COLOR = '%(color_import)s', CICLO_COLOR = '%(color_ciclo)s';
const OBRA_COLOR = '%(color_obra)s';
const AGENTES = %(agentes)s;
const CAPTURAS = %(capturas)s;
const REFRESCO = %(refresco)s;
const SIN_LEER = %(sin_leer)s;
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
const MAXIT = %(maxit)s, GRAV = 0.06;
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
// La camara sobrevive a una recarga. Sin esto, un refresco automatico te
// devolveria al encuadre inicial cada vez y explorar seria pelearte con la
// pagina; con esto la recarga es casi invisible. La clave lleva el titulo para
// que dos mapas abiertos a la vez no se pisen el encuadre.
const CAMARA = 'gb-camara:' + document.title;
try{
  const guardada = JSON.parse(sessionStorage.getItem(CAMARA) || 'null');
  if(guardada){ esc=guardada.e; ox=guardada.x; oy=guardada.y; camaraLibre=true; }
}catch(_){}
addEventListener('beforeunload', ()=>{
  try{ if(camaraLibre) sessionStorage.setItem(CAMARA, JSON.stringify({e:esc,x:ox,y:oy})); }catch(_){}
});
function encaje(){
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  for(let i=0;i<N;i++){ x0=Math.min(x0,X[i]); y0=Math.min(y0,Y[i]); x1=Math.max(x1,X[i]); y1=Math.max(y1,Y[i]); }
  const pad=70, w=Math.max(x1-x0,1), h=Math.max(y1-y0,1);
  const e = Math.min((cv.width-2*pad)/w, (cv.height-60-2*pad)/h);
  return [e, pad+(cv.width-2*pad-w*e)/2 - x0*e, 60+pad+(cv.height-60-2*pad-h*e)/2 - y0*e];
}
function medir(){ cv.width=innerWidth; cv.height=innerHeight;
  // El refit SOLO si la camara no es del usuario: medir() corre al arrancar
  // DESPUES de restaurar la camara guardada, y sin esta guarda la pisaba en
  // cada recarga — el bug existio siempre, pero la re-animacion lo enmascaraba;
  // al heredar las posiciones (mapa quieto) se volvio visible (uso real, 4-ago).
  if(!camaraLibre){ const r=encaje(); esc=r[0]; ox=r[1]; oy=r[2]; } }

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
let activo=null, fijado=null, filtro='', agenteFoco=null, cercaAg=new Set();

// Vecindario DIRIGIDO. `vecinos` sirve para atenuar el dibujo, pero para leer un
// nodo hace falta saber en que direccion va cada arista: "a quien llamo" y "quien
// me llama" son preguntas distintas, y confundirlas es lo que hace inutil a la
// mayoria de visores de grafos.
const entran = NODOS.map(()=>[]), salen = NODOS.map(()=>[]);
for(const par of ARISTAS){
  const tp = par[2]|0;
  if(tp===0) continue;               // jerarquia = pertenencia, no flujo
  salen[par[0]].push([par[1], tp]);
  entran[par[1]].push([par[0], tp]);
}
// Los nombres vienen del disco: un modulo puede llamarse como a alguien se le
// ocurra. Van escapados antes de tocar innerHTML.
// OJO con el nombre: `esc` ya existe y es la ESCALA del zoom. Llamar a esto `esc`
// fue un `const` duplicado en el mismo ambito, o sea un SyntaxError, o sea la
// pagina entera en blanco. Y 358 tests en verde, porque comprobaban que las
// cadenas estuvieran, nunca que el script parseara.
const escapa = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function _lista(pares, clase, tope){
  const nombres = pares.filter(p => p[1]===clase).map(p => NODOS[p[0]].l);
  if(!nombres.length) return '';
  const unicos = [...new Set(nombres)].sort();
  const cabeza = unicos.slice(0, tope).map(escapa).join(', ');
  return cabeza + (unicos.length > tope ? ' <span>+' + (unicos.length - tope) + '</span>' : '');
}

function muestraFicha(i){
  if(i===null){ ficha.style.display='none'; return; }
  const n=NODOS[i];
  // Hechos, no prosa: quien lo llama, a quien llama, donde vive y si esta en un
  // ciclo. Una explicacion generada exigiria un modelo, y una explicacion
  // sutilmente falsa aqui llegaria con la misma autoridad que el resto del mapa,
  // que es determinista de punta a punta.
  const filas = [];
  // La descripcion primero: es lo que contesta "que es esto" antes de "con quien
  // habla". Sale del docstring, o sea de quien escribio el codigo — no generada.
  if(n.d) filas.push('<i>'+escapa(n.d)+'</i>');
  else filas.push('<span>sin describir</span>');
  const meta = [n.k||'', n.g && n.g!==n.id ? 'en ' + escapa(n.g) : ''].filter(Boolean).join(' &middot; ');
  if(meta) filas.push('<span>'+meta+'</span>');
  const bloques = [
    ['llamado por', _lista(entran[i], 1, 4) || _lista(entran[i], 2, 4)],
    ['llama a',     _lista(salen[i], 1, 4)  || _lista(salen[i], 2, 4)],
    ['importado por', _lista(entran[i], 3, 4)],
    ['importa',       _lista(salen[i], 3, 4)],
  ];
  for(const [rotulo, contenido] of bloques){
    if(contenido) filas.push('<span>'+rotulo+':</span> '+contenido);
  }
  if((entran[i].length+salen[i].length)===0){
    // Decirlo es el dato: un simbolo que nadie llama es precisamente algo que se
    // quiere VER, no una ficha vacia que parezca un fallo de la pagina.
    filas.push('<span>sin llamadas resueltas ni imports</span>');
  }
  if(n.ee){
    // La cadena del ciclo del error, por firma: hechos encadenados con su
    // ventana temporal, nunca un veredicto. Los textos vienen ya montados desde
    // Python (con datos del historico y de git); aqui solo se escapan y pintan.
    filas.push('<span>ciclo del error:</span> <span style="color:'+n.ec+'">'+escapa(n.ee)+'</span>');
    for(const l of (n.el||[])) filas.push('&middot; '+escapa(l));
  }
  const marcas = [];
  if(n.ci) marcas.push('<span style="color:'+CICLO_COLOR+'">en un ciclo</span>');
  if(n.nu) marcas.push('<span style="color:#22d3ee">nuevo</span>');
  if(n.tc) marcas.push('<span style="color:'+OBRA_COLOR+'">tocado sin commitear</span>');
  if(marcas.length) filas.push(marcas.join(' &middot; '));

  // Fijado (clic) vs de paso (hover): el borde y la X lo dicen. Sin esa
  // diferencia, un clic que no llego a fijar es invisible y parece que la pagina
  // no responde — que es justo lo que pasaba.
  const esFijado = (fijado!==null && fijado===i);
  const cierre = esFijado ? '<span class="cerrar" id="cerrarFicha">&#10005;</span>' : '';
  const pista = esFijado
    ? '<span class="pista">fijado &middot; clic otra vez (o la X) para soltarlo</span>'
    : '<span class="pista">clic para fijarlo aqui</span>';
  ficha.className = esFijado ? 'fijado' : '';
  ficha.innerHTML = cierre + '<b>'+escapa(n.id)+'</b><br>' + filas.join('<br>') + pista;
  ficha.style.display='block';
  const x = document.getElementById('cerrarFicha');
  if(x) x.addEventListener('click', ()=>{ fijado=null; muestraFicha(activo); recuerda(); });
}

// ================= dibujo =================
function pinta(t){
  cx.clearRect(0,0,cv.width,cv.height);
  const foco = fijado!==null ? fijado : activo;
  const cerca = foco!==null ? vecinos[foco] : null;
  // Respiracion en espacio de DIBUJO, no de fisica: la estructura queda quieta
  // y el grafo respira. Fase por indice: determinista. Y sobre reloj de PARED
  // (timeOrigin+t), no el de animacion: ese arranca en 0 en cada recarga, y
  // con --refresco la fase saltaba de golpe cada N segundos — todos los nodos
  // brincaban un poco en cada recarga (uso real, 4-ago).
  const reloj = performance.timeOrigin + t;
  const WX=new Float64Array(N), WY=new Float64Array(N);
  const vivo = iter>=MAXIT ? 1 : 0;
  for(let i=0;i<N;i++){
    WX[i]=X[i]*esc+ox + vivo*2.2*Math.sin(reloj/1100+i*2.1);
    WY[i]=Y[i]*esc+oy + vivo*2.2*Math.cos(reloj/1300+i*1.3);
  }
  cx.lineWidth=1;
  // Orden de pintado = orden de lectura. Jerarquia (0) casi invisible debajo,
  // solo sujeta; imports entre modulos (3) como esqueleto ambar, que es el hecho
  // exacto; llamadas (1) encima; lo nuevo (2) en cian, que es lo que se mira.
  for(const capa of [0,3,1,2]) for(const par of ARISTAS){
    const a=par[0], b=par[1], tp=par[2]|0;
    if(tp!==capa) continue;
    const tocada = foco!==null && (a===foco || b===foco);
    if(agenteFoco!==null && !cercaAg.has(a) && !cercaAg.has(b)){ cx.globalAlpha=0.015; }
    else if(foco!==null && !tocada){ cx.globalAlpha=0.02; }
    else { cx.globalAlpha = tocada ? 0.9 : (par[3] ? 0.95 : (capa===0 ? 0.09 : capa===3 ? 0.5 : (capa===2 ? 0.7 : 0.3))); }
    // El tramo ciclico manda sobre su capa: es el unico hecho que detiene un commit.
    cx.strokeStyle = par[3] ? CICLO_COLOR : (capa===2 ? '#22d3ee' : capa===3 ? IMPORT_COLOR : NODOS[a].c);
    cx.lineWidth = par[3] ? 2.4 : (capa===3 ? 1.8 : 1);
    cx.beginPath(); cx.moveTo(WX[a],WY[a]); cx.lineTo(WX[b],WY[b]); cx.stroke();
  }
  // ---- sinapsis: la señal del agente fluyendo por su onda --------------------
  // Cada arista que sale de un nodo tocado se enciende con el color de SU agente
  // y un paquete viaja del nodo tocado hacia el vecino: el cambio propagandose
  // hacia quien le llama. La jerarquia (capa 0) no es comunicacion y no fluye.
  // Fase distinta por arista (si no, todas palpitarian a la vez); sin modulo de
  // JS a proposito — este script vive en un template %%-formateado de Python.
  for(const par of ARISTAS){
    const a=par[0], b=par[1], tp=par[2]|0;
    if(tp===0) continue;
    const na=NODOS[a], nb=NODOS[b];
    const agA=(na.ag&&na.ag.length)?1:0, agB=(nb.ag&&nb.ag.length)?1:0;
    if(!agA && !agB) continue;
    const desde = agA ? a : b, hasta = agA ? b : a;
    const quien = agA ? na.ag : nb.ag;
    if(agenteFoco!==null && quien.indexOf(agenteFoco)<0) continue;
    const vigor = vigorOnda(quien);
    if(vigor<=0) continue;   // actividad de hace >10 min: la onda ya no es "ahora"
    const c = quien.length>1 ? '#ffffff' : ((AGENTES[quien[0]]||{}).c||OBRA_COLOR);
    cx.globalAlpha=0.3*vigor; cx.strokeStyle=c; cx.lineWidth=1.2;
    cx.beginPath(); cx.moveTo(WX[desde],WY[desde]); cx.lineTo(WX[hasta],WY[hasta]); cx.stroke();
    let fase = reloj/1300 + (a*31+b*17)*0.013;
    fase = fase - Math.floor(fase);
    const sx=WX[desde]+(WX[hasta]-WX[desde])*fase, sy=WY[desde]+(WY[hasta]-WY[desde])*fase;
    cx.globalAlpha=0.9*vigor; cx.fillStyle=c;
    cx.beginPath(); cx.arc(sx,sy,1.7*Math.min(Math.max(esc,0.6),1.5),0,6.284); cx.fill();
  }
  cx.lineWidth=1;
  cx.globalAlpha=1;
  const fase=(Math.sin(reloj/180)+1)/2;   // pulso de busqueda: formula de GitNexus
  for(let i=0;i<N;i++){
    const n=NODOS[i];
    const coincide = filtro && n.id.toLowerCase().includes(filtro);
    const relacionado = foco===null || i===foco || cerca.has(i);
    let rr = n.r*Math.min(Math.max(esc,0.55),1.6);
    rr *= 1 + vivo*0.05*Math.sin(reloj/900+i*2.4);      // respiracion
    let color = n.c;
    if(filtro && !coincide){ color=n.cd; }
    else if(foco!==null && !relacionado){ color=n.cd; }
    if(agenteFoco!==null && !cercaAg.has(i)){ color=n.cd; }
    if(coincide){ rr *= 1.2+fase*0.5; if(fase>0.5) color='#06b6d4'; }
    if(i===foco){ rr *= 1+0.12*Math.sin(reloj/250); }
    if(n.tc){
      // Capa de cambio: halo RELLENO bajo el nodo (path propio, antes del
      // circulo). Todos los demas estados son strokes sobre el borde; esto se
      // distingue por forma, no solo por color, y no pisa rojo/cian ni los
      // anillos discontinuos del ciclo del error.
      // QUIETO y suave: tocado-sin-commitear es un estado del ARBOL, o sea
      // contexto, no la noticia. Lo que pulsa es el agente, mas abajo.
      cx.globalAlpha=0.28; cx.fillStyle=OBRA_COLOR;
      cx.beginPath(); cx.arc(WX[i],WY[i],rr+6,0,6.284); cx.fill();
      cx.globalAlpha=1;
    }
    // ESTO si es un agente trabajando aqui AHORA, y lleva SU color, no el de
    // la capa de cambio. Pulsa porque el movimiento es lo unico que el ojo
    // coge sin buscar entre 900 nodos. Dos o mas agentes en el mismo nodo:
    // aro blanco y grueso, que es el caso que hay que mirar.
    //
    // Y se APAGA con la edad, con el mismo `vigorOnda` que las aristas. La
    // politica ya estaba decidida —entera 3 min, muerta a los 10— pero solo
    // gobernaba la onda, no el nodo: un mapa estatico de hace horas seguia
    // pintando el aro fucsia y se leia como "hay alguien aqui ahora mismo".
    // Costo una busqueda de un agente colgado que no existia (10-ago-2026).
    const vigorAg = (n.ag && n.ag.length) ? vigorOnda(n.ag) : 0;
    if(vigorAg>0){
      const ca = (AGENTES[n.ag[0]]||{}).c || OBRA_COLOR;
      const propio = agenteFoco===null || n.ag.indexOf(agenteFoco)>=0;
      const pu = 0.5 + 0.5*Math.sin(reloj/380 + i*0.7);
      cx.globalAlpha=(0.22+0.5*pu)*(propio?1:0.12)*vigorAg; cx.fillStyle=ca;
      cx.beginPath(); cx.arc(WX[i],WY[i],rr+8+5*pu,0,6.284); cx.fill();
      cx.globalAlpha=(propio?1:0.15)*vigorAg; cx.strokeStyle = n.ag.length>1 ? '#ffffff' : ca;
      cx.lineWidth = n.ag.length>1 ? 3 : 2.4;
      cx.beginPath(); cx.arc(WX[i],WY[i],rr+4,0,6.284); cx.stroke();
      cx.globalAlpha=1; cx.lineWidth=1;
    }
    cx.beginPath(); cx.arc(WX[i],WY[i],rr,0,6.284);
    cx.fillStyle=color; cx.fill();
    if(n.nu){ cx.strokeStyle='#22d3ee'; cx.lineWidth=1.2; cx.stroke(); cx.lineWidth=1; }
    if(n.ci){ cx.strokeStyle=CICLO_COLOR; cx.lineWidth=2; cx.stroke(); cx.lineWidth=1; }
    if(i===foco || coincide){
      cx.strokeStyle='#fff'; cx.lineWidth=1.5; cx.stroke(); cx.lineWidth=1;
      cx.fillStyle='#e8edf3'; cx.font='11px ui-monospace,Consolas,monospace';
      cx.fillText(n.l, WX[i]+rr+4, WY[i]+3);
    }
    if(n.ec){
      // Anillo discontinuo APARTE del borde del nodo (path nuevo, por eso va al
      // final: los strokes de arriba reusan el path del circulo). El estado del
      // ciclo del error no compite con el rojo del ciclo de imports ni con el
      // cian de lo nuevo — informa, no bloquea.
      cx.strokeStyle=n.ec; cx.setLineDash([3,2]); cx.lineWidth=1.6;
      cx.beginPath(); cx.arc(WX[i],WY[i],rr+3,0,6.284); cx.stroke();
      cx.setLineDash([]); cx.lineWidth=1;
    }
  }
  // La consola del agente, ENCIMA del nodo que esta tocando. Va en su propia
  // pasada, despues de todos los nodos, para que ninguna quede tapada.
  //
  // Lo que dice son HECHOS derivados del disco: que toca, con cuantos nodos
  // habla, hace cuanto. Su narrativa ("estoy refactorizando el store") solo la
  // tiene el agente, y pedirsela seria volver al registro declarado que se
  // descarto: en cuanto uno se olvida de declarar, el panel miente con cara de
  // hecho.
  if(esc>0.45) for(let i=0;i<N;i++){
    const n=NODOS[i];
    if(!n.ag || !n.ag.length) continue;
    if(agenteFoco!==null && n.ag.indexOf(agenteFoco)<0) continue;
    if(vigorOnda(n.ag)<=0) continue;   // muerta: ni aro ni tarjeta, o el texto miente
    const varios = n.ag.length>1;
    const a = AGENTES[n.ag[0]] || {};
    const l1 = varios ? (n.ag.length+' agentes a la vez') : n.ag[0];
    let l2 = (a.nodos||0)+' nodo(s) - habla con '+(a.vecinos||0);
    // `haceAhora`, no `a.hace`: el del payload esta congelado en la foto y la
    // tarjeta decia "hace 3s" para siempre. La funcion existia para esto y este
    // sitio no la llamaba — media conexion, como el aro de arriba.
    const _h = haceAhora(a);
    if(_h!=null) l2 += ' - hace '+fmtHace(_h);
    const l3 = varios ? n.ag.join(' + ')
                      : ((a.fuera ? a.fuera+' fichero(s) aun sin sitio en el mapa' : '')
                         || (a.misma ? '' : 'OJO: parte de otra base ('+a.base+')'));
    const lineas = l3 ? [l1,l2,l3] : [l1,l2];
    cx.font='10px ui-monospace,Consolas,monospace';
    let an=0; for(const t of lineas) an=Math.max(an, cx.measureText(t).width);
    const pw=an+14, ph=lineas.length*13+9;
    const px=WX[i]-pw/2, py=WY[i]-n.r*Math.min(Math.max(esc,0.55),1.6)-ph-11;
    // Tallo hasta el nodo: sin el, la caja flota y no se sabe de quien habla.
    const cc = varios ? '#ffffff' : ((AGENTES[n.ag[0]]||{}).c || OBRA_COLOR);
    cx.strokeStyle = cc; cx.globalAlpha=0.8;
    cx.beginPath(); cx.moveTo(WX[i],py+ph); cx.lineTo(WX[i],WY[i]); cx.stroke();
    cx.globalAlpha=0.94; cx.fillStyle='#111722';
    cx.beginPath(); cx.rect(px,py,pw,ph); cx.fill();
    cx.globalAlpha=1; cx.lineWidth = varios ? 2.2 : 1.4;
    cx.strokeStyle = cc; cx.stroke(); cx.lineWidth=1;
    cx.fillStyle = cc;
    cx.fillText(lineas[0], px+7, py+14);
    cx.fillStyle='#7d8b9c';
    for(let k=1;k<lineas.length;k++) cx.fillText(lineas[k], px+7, py+14+k*13);
  }
}

// ============ posiciones heredadas ============
// Las posiciones sobreviven a la recarga, como la camara. Sin esto, cada
// auto-refresco reiniciaba la fisica desde la siembra y el mapa BAILABA cada
// N segundos (salio en prueba de uso, 4-ago). Al volver, cada nodo hereda su
// sitio ya convergido y pinta quieto; con pocos nodos nuevos se deja un
// asentamiento corto y frio para colocarlos sin sacudir al resto; con muchos
// (>20 por ciento) la forma cambio de verdad y la convergencia se re-anima.
const POSICIONES = 'gb-pos:' + document.title;
try{
  const previas = JSON.parse(sessionStorage.getItem(POSICIONES) || 'null');
  if(previas && MAXIT && N>1){
    let usadas = 0;
    for(let i=0;i<N;i++){ const p = previas[NODOS[i].id]; if(p){ X[i]=p[0]; Y[i]=p[1]; usadas++; } }
    if(usadas === N) iter = MAXIT;
    else if(usadas > N*0.8) iter = Math.max(0, MAXIT-40);
    if(iter){
      temp = Math.max(0, (LADO/10)*(1 - iter/(MAXIT+1)));
      // El encuadre no se toca aqui: medir() (que corre despues, ya con el
      // canvas a tamano real) encaja si la camara no es del usuario.
      if(iter>=MAXIT) estado.style.opacity=0;
    }
  }
}catch(_){}
addEventListener('beforeunload', ()=>{
  try{
    const sitio = {};
    for(let i=0;i<N;i++) sitio[NODOS[i].id] = [Math.round(X[i]*10)/10, Math.round(Y[i]*10)/10];
    sessionStorage.setItem(POSICIONES, JSON.stringify(sitio));
  }catch(_){}
});

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
  // 6 px, no 3: con 3 el temblor normal de la mano al hacer clic contaba como
  // arrastre y el nodo no llegaba a fijarse nunca.
  if(Math.hypot(e.clientX-lx,e.clientY-ly)>6) movido=true;
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
    if(!movido){ fijado = (fijado===agarrado) ? null : agarrado; muestraFicha(fijado); recuerda(); }
    else cola=90;
    agarrado=null;
  } else if(panning && !movido){ fijado=null; muestraFicha(null); recuerda(); }
  panning=false; cv.classList.remove('arrastrando');
});
cv.addEventListener('wheel', e=>{
  e.preventDefault(); camaraLibre=true;
  const k = e.deltaY>0 ? 0.9 : 1.1;
  ox = e.clientX-(e.clientX-ox)*k; oy = e.clientY-(e.clientY-oy)*k; esc*=k; recuerda();
}, {passive:false});
buscar.addEventListener('input', e=>{ filtro=e.target.value.trim().toLowerCase(); });
document.getElementById('btnPausa').addEventListener('click', ev=>{
  corriendo=!corriendo; ev.target.innerHTML = corriendo ? '&#9208;' : '&#9654;';
});
document.getElementById('btnEncaja').addEventListener('click', ()=>{
  const r=encaje(); esc=r[0]; ox=r[1]; oy=r[2];
});
addEventListener('resize', ()=>{ if(!camaraLibre) medir(); else { cv.width=innerWidth; cv.height=innerHeight; } });
// La pagina se recarga sola cada pocos segundos, y una recarga destruye TODO el
// estado: el nodo fijado, el zoom y el encuadre. Sin esto, fijar una ficha es
// imposible en un mapa vivo — se borraba antes de poder leerla.
//
// El nodo se guarda por ID, nunca por indice: entre dos regeneraciones el grafo
// cambia y el indice 412 pasa a ser otro simbolo. Guardar el indice habria
// devuelto la ficha equivocada con toda la autoridad del resto del mapa.
const MEM='gb-mapa-estado';
function recuerda(){
  try{
    sessionStorage.setItem(MEM, JSON.stringify({
      f: fijado===null ? null : NODOS[fijado].id,
      e: esc, x: ox, y: oy, lib: camaraLibre ? 1 : 0, af: agenteFoco
    }));
  }catch(_){}
}
function recupera(){
  let s; try{ s=JSON.parse(sessionStorage.getItem(MEM)||'null'); }catch(_){ return; }
  if(!s) return;
  if(s.lib && isFinite(s.e) && isFinite(s.x) && isFinite(s.y)){
    esc=s.e; ox=s.x; oy=s.y; camaraLibre=true;
  }
  if(s.f){
    const i = NODOS.findIndex(n => n.id === s.f);
    // Si el simbolo ya no existe, se suelta y se calla: mejor sin ficha que una
    // ficha de algo que se borro.
    if(i>=0){ fijado=i; muestraFicha(i); }
  }
  // El foco por agente tambien sobrevive al refresco — y si el agente ya no
  // esta (commiteo, o su worktree se fue), se suelta sin decir nada.
  if(s.af && AGENTES[s.af]){ agenteFoco=s.af; calculaCercaAg(); }
}
addEventListener('beforeunload', recuerda);

// ---- panel de agentes -------------------------------------------------------
// El roster de la sala de control. La onda de un agente son sus nodos mas un
// salto por las aristas: lo mismo que su consola dice que "habla", pero visible
// de golpe al hacer clic. Todo derivado; el panel no existe sin agentes.
function calculaCercaAg(){
  cercaAg=new Set();
  if(agenteFoco===null) return;
  NODOS.forEach((n,i)=>{ if(n.ag && n.ag.indexOf(agenteFoco)>=0) cercaAg.add(i); });
  const base=new Set(cercaAg);
  for(const par of ARISTAS){
    if(base.has(par[0])) cercaAg.add(par[1]);
    if(base.has(par[1])) cercaAg.add(par[0]);
  }
}
// El panel de agentes se retiro (6-ago): su tarjeta se FUSIONO con la terminal
// y vive anclada al nodo del agente — una sola pieza por agente, donde opera.
function fmtHace(s){ return s==null ? '' : (s<90 ? Math.round(s)+'s' : Math.round(s/60)+'m'); }
// La edad REAL de la actividad: la que tenia al generarse el mapa mas lo que ha
// pasado desde la generacion (GEN_TS). El `hace` del payload esta congelado en
// la foto; sin esto la tarjeta miente mas cuanto mas vieja es la pestana.
function haceAhora(a){
  if(!a || a.hace==null) return null;
  const extra = GEN_TS!=null ? Math.max(0, Date.now()/1000 - GEN_TS) : performance.now()/1000;
  return a.hace + extra;
}
// La onda del agente se apaga con la edad: fluye entera 3 min, se atenua y a los
// 10 esta muerta. Una foto estatica que anima flujo eternamente lee como "esta
// pasando ahora", cuando el hecho es "estaba pasando cuando se genero" — la
// misma disciplina que el pie: decir de cuando es el dato.
const ONDA_FRESCA=180, ONDA_MUERTA=600;
function vigorOnda(quien){
  let hace=null;
  for(const q of quien){ const h=haceAhora(AGENTES[q]); if(h!=null && (hace==null||h<hace)) hace=h; }
  if(hace==null) return 1;  // sin mtime no se inventa una muerte: se dibuja
  if(hace<=ONDA_FRESCA) return 1;
  return Math.max(0, 1-(hace-ONDA_FRESCA)/(ONDA_MUERTA-ONDA_FRESCA));
}

// Cualquier panel con cabecera se arrastra por ella y recuerda donde lo dejaste
// (por pestaña): dos consolas fijas en esquinas acaban superpuestas en cuanto
// la ventana encoge — la posicion es de quien mira, como la talla.
function hazArrastrable(el, clave){
  let pos=null;
  try{ pos=JSON.parse(sessionStorage.getItem(clave)||'null'); }catch(_){}
  function aplica(){
    if(!pos) return;
    el.style.left=pos[0]+'px'; el.style.top=pos[1]+'px';
    el.style.right='auto'; el.style.bottom='auto';
  }
  aplica();
  let arr=null;
  el.addEventListener('mousedown', ev=>{
    const cab=ev.target && ev.target.closest ? ev.target.closest('.cab') : null;
    if(!cab || (ev.target.dataset && ev.target.dataset.acc)) return;
    const r=el.getBoundingClientRect();
    arr={dx:ev.clientX-r.left, dy:ev.clientY-r.top};
    window._arrastrandoTerm=true;  // la recarga tampoco interrumpe este arrastre
    ev.preventDefault();
  });
  addEventListener('mousemove', ev=>{
    if(!arr) return;
    pos=[Math.max(0,ev.clientX-arr.dx), Math.max(0,ev.clientY-arr.dy)];
    aplica();
  });
  addEventListener('mouseup', ()=>{
    if(!arr) return;
    arr=null;
    window._arrastrandoTerm=false;
    try{ sessionStorage.setItem(clave, JSON.stringify(pos)); }catch(_){}
  });
}

// ---- consola de actividad ---------------------------------------------------
// "Lo que van haciendo" en lo que se puede saber sin que nadie lo declare: cada
// recarga compara la instantanea actual (AGENTES + que nodo toca quien) con la
// anterior, guardada en el navegador, y LOS EVENTOS SON LA DIFERENCIA. La
// narrativa del agente ("estoy refactorizando el store") solo la tiene el; esto
// es el registro de sus huellas, con la cadencia de la regeneracion.
function eventosEntre(prev, ahora){
  const ev=[];
  const antes=prev||{ag:{},nodos:{}};
  for(const nombre of Object.keys(ahora.ag)){
    const a=ahora.ag[nombre], pa=antes.ag[nombre];
    if(!pa){
      ev.push({a:nombre,t:'aparece',d:(a.nodos||0)+' nodo(s) en su onda'});
      // Lo que ya lleva escrito al aparecer tambien es un hecho: sin esto, un
      // agente que arranca con trabajo hecho parece que no ha hecho nada.
      for(const h of (a.cambios||[]).slice(0,4)) ev.push({a:nombre,t:'escribe',d:h});
      if((a.cambios||[]).length>4) ev.push({a:nombre,t:'escribe',d:'+'+((a.cambios||[]).length-4)+' hecho(s) mas'});
      continue;
    }
    // "escribe" con sustancia: los hechos de firma NUEVOS desde la instantanea
    // anterior — que escribio exactamente, no "ultima actividad hace 2s". El
    // texto generico queda solo de reserva, para cambios sin firma (cuerpos).
    const antesC={}; for(const h of (pa.cambios||[])) antesC[h]=1;
    const nuevos=(a.cambios||[]).filter(h=>!antesC[h]);
    for(const h of nuevos.slice(0,4)) ev.push({a:nombre,t:'escribe',d:h});
    if(nuevos.length>4) ev.push({a:nombre,t:'escribe',d:'+'+(nuevos.length-4)+' hecho(s) mas'});
    if(!nuevos.length && a.hace!=null && pa.hace!=null && a.hace<pa.hace)
      ev.push({a:nombre,t:'escribe',d:'sin cambio de firma (cuerpos o docs) · hace '+a.hace+'s'});
    if((a.fuera||0)>(pa.fuera||0))
      ev.push({a:nombre,t:'crea',d:(a.fuera-(pa.fuera||0))+' fichero(s) aun sin sitio en el mapa'});
  }
  for(const nombre of Object.keys(antes.ag))
    if(!ahora.ag[nombre]) ev.push({a:nombre,t:'se va',d:'sin cambios pendientes (commit o descarte)'});
  const na=ahora.nodos||{}, np=antes.nodos||{};
  for(const q of Object.keys(na)){
    const ags=na[q], pags=np[q]||[];
    for(const nombre of ags) if(pags.indexOf(nombre)<0) ev.push({a:nombre,t:'toca',d:q});
    if(ags.length>1 && pags.length<2) ev.push({a:ags.join(' + '),t:'CRUCE',d:q});
  }
  for(const q of Object.keys(np)) for(const nombre of np[q])
    if((na[q]||[]).indexOf(nombre)<0 && ahora.ag[nombre]) ev.push({a:nombre,t:'suelta',d:q});
  return ev;
}
const consolaEl=document.getElementById('consola');
const CMEM='gb-mapa-consola';
(function(){
  const nodosAg={};
  NODOS.forEach(n=>{ if(n.ag && n.ag.length) nodosAg[n.id]=n.ag; });
  const ahora={ag:AGENTES, nodos:nodosAg};
  let est=null; try{ est=JSON.parse(sessionStorage.getItem(CMEM)||'null'); }catch(_){}
  const log=(est && est.log)||[];
  const hora=new Date().toLocaleTimeString();
  for(const e of eventosEntre(est && est.snap, ahora))
    log.push({h:hora, c: e.t==='CRUCE' ? '#ffffff' : ((AGENTES[e.a]||{}).c||'#94a3b8'),
              a:e.a, t:e.t, d:e.d});
  // Las capturas NO entran a este feed: se probo y una tirada las entierra
  // bajo los toca/escribe. Viven en su propia consola de errores (#errores).
  while(log.length>200) log.shift();
  let abierto = est ? est.abierto!==0 : true;
  // Tres tallas, no un resize libre: anclada abajo-izquierda, el asa nativa de
  // CSS crece hacia abajo-derecha y se sale de la pantalla. La talla se
  // recuerda entre recargas, como todo lo demas.
  const TAM=[[300,'22vh'],[410,'38vh'],[580,'62vh']];
  let tam = (est && typeof est.tam==='number') ? est.tam : 1;
  function guarda(){
    try{ sessionStorage.setItem(CMEM, JSON.stringify(
      {snap:ahora, log:log, abierto:abierto?1:0, tam:tam})); }catch(_){}
  }
  guarda();
  function pintaConsola(){
    // ABIERTO manda: con el log vacio se dice "0 eventos" en vez de esconder
    // el panel — un boton que conmuta algo invisible parece un boton roto
    // (paso: pestaña nueva, sessionStorage virgen, ≡ "no funcionaba").
    if(!abierto){ consolaEl.style.display='none'; return; }
    // La consola DE un agente: el foco del panel filtra tambien aqui (un CRUCE
    // en el que participa cuenta como suyo). Sin foco, la de todos.
    const filas = agenteFoco
      ? log.filter(e=>e.a===agenteFoco || e.a.split(' + ').indexOf(agenteFoco)>=0)
      : log;
    consolaEl.style.width=TAM[tam][0]+'px';
    consolaEl.style.maxHeight=TAM[tam][1];
    consolaEl.innerHTML =
      '<div class="cab"><span>'+(agenteFoco
        ? 'consola de '+escapa(agenteFoco)
        : 'actividad (hechos derivados)')+'</span>'+
      '<span><b data-acc="menos" title="mas pequena">&#8722;</b>'+
      '<b data-acc="mas" title="mas grande">+</b>'+
      '<b data-acc="cerrar" title="ocultar">&#10005;</b></span></div>'+
      (filas.length ? filas.map(e=>
      '<div class="fila"><span class="hora">'+e.h+'</span>'+
      '<span class="quien" style="color:'+e.c+'">'+escapa(e.a)+'</span>'+
      '<span class="que">'+escapa(e.t)+'</span><span class="detalle">'+escapa(e.d)+'</span></div>'
      ).join('')
      : '<div class="fila"><span class="detalle">'+(agenteFoco
          ? '(sin eventos registrados de '+escapa(agenteFoco)+')'
          : '(0 eventos: se derivan comparando instantaneas entre recargas — '+
            'hacen falta DOS cosas: trabajo en el arbol y el mapa latiendo '+
            '(gb symbols --html --watch --fondo). Una sola regeneracion al '+
            'final siempre dira cero)')+'</span></div>');
    consolaEl.style.display='block';
    consolaEl.scrollTop=consolaEl.scrollHeight;
  }
  window._pintaConsola=pintaConsola;
  // Delegacion: pintaConsola reconstruye el innerHTML, asi que los botones no
  // pueden llevar listeners propios — se escucha en el contenedor, que vive.
  consolaEl.addEventListener('click', ev=>{
    const acc = ev.target && ev.target.dataset ? ev.target.dataset.acc : null;
    if(!acc) return;
    if(acc==='cerrar') abierto=false;
    else if(acc==='menos') tam=Math.max(0, tam-1);
    else if(acc==='mas') tam=Math.min(TAM.length-1, tam+1);
    guarda(); pintaConsola();
  });
  document.getElementById('btnConsola').addEventListener('click', ()=>{
    abierto=!abierto; guarda(); pintaConsola();
  });
  hazArrastrable(consolaEl, 'gb-mapa-consola-pos');
  pintaConsola();

  // ---- terminales de agente: su consola cmd, anclada encima de sus nodos ----
  // El contenido es el stdout REAL del agente (AGENTES[n].consola, teeado por
  // el orquestador y leido del disco), no los hechos de firma: esos ya viven
  // en la consola de abajo. Cursor parpadeando mientras el agente esta vivo.
  const termCont=document.getElementById('terminales');
  const IDXN={}; NODOS.forEach((n,i)=>{ IDXN[n.id]=i; });
  // La talla la elige quien mira: tres discretas con -/+ (mismo motivo que la
  // consola: resize libre no vale con el ancla en el nodo), recordada entre
  // recargas. [ancho px, lineas visibles]
  const TAMT=[[180,2],[240,3],[340,6]];
  const TMEM='gb-mapa-terminal';
  let tamT=1;
  try{ const g=sessionStorage.getItem(TMEM);
       if(g!=null) tamT=Math.max(0,Math.min(TAMT.length-1,+g||0)); }catch(_){}
  const TERMS=[]; const anclados={}; let sueltos=0;
  // La lluvia: la pagina recuerda la ultima linea que YA se vio (por agente) y
  // las posteriores se revelan de una en una — la conversacion cae, no salta a
  // golpes de recarga. La marca de lo visto sobrevive al refresco.
  const VMEM='gb-mapa-terminal-visto';
  let vistos={};
  try{ vistos=JSON.parse(sessionStorage.getItem(VMEM)||'{}')||{}; }catch(_){}
  function renderTerm(t, cayendo){
    const a=AGENTES[t.nom]; if(!a) return;
    const total=(a.consola||[]).length;
    // vivo/hace con la edad REAL, no la congelada en la foto: un cursor
    // parpadeando dos horas despues es la misma mentira que la onda eterna.
    const hAhora = haceAhora(a);
    const vivo = (hAhora!=null && hAhora<120) || t.reveladas<total;
    t.el.style.width=TAMT[tamT][0]+'px';
    t.el.className='term'+(agenteFoco===t.nom?' foco':'');
    // La tarjeta y la terminal son UNA pieza: cabecera con los datos del
    // agente (lo que era el panel) y debajo su consola, si habla.
    let h='<div class="tcab" style="color:'+a.c+'">&#9679; '+escapa(t.nom)+
      '<span class="tdat">'+(a.nodos||0)+'n'+(hAhora!=null?' &middot; '+fmtHace(hAhora):'')+'</span>'+
      '<span class="tbot"><b data-acc="tmenos" title="mas pequena">&#8722;</b>'+
      '<b data-acc="tmas" title="mas grande">+</b></span></div>';
    if(!a.misma) h+='<div class="tav">&#9888; parte de otra base ('+escapa(a.base)+')</div>';
    else if(a.fuera) h+='<div class="tav" style="color:var(--suave)">'+a.fuera+' fichero(s) sin sitio en el mapa</div>';
    // El veredicto del GRAFO, si este agente corre con escalera. Se pinta el
    // camino entero (0:rechazar -> 1:aceptar) y no solo el final: lo que ensena
    // como se construyo la respuesta es la secuencia, no el ultimo peldano.
    if(a.escalera){
      const e=a.escalera;
      const col = e.veredicto==='aceptar' ? '#7ec97e' : (e.veredicto==='rechazar' ? '#e0b341' : 'var(--suave)');
      const ruta=(e.peldanos||[]).map(p=>p.n+':'+p.veredicto).join(' → ');
      h+='<div class="tav" style="color:'+col+'">'+escapa(e.veredicto.toUpperCase())+
         (e.ancla?' &middot; '+escapa(e.ancla):'')+
         '<div style="color:var(--suave);font-size:.9em">'+escapa(e.motivo)+'</div>'+
         (ruta?'<div style="color:var(--suave);font-size:.85em">'+escapa(ruta)+'</div>':'')+
         '</div>';
    }
    let visibles=(a.consola||[]).slice(0,t.reveladas).slice(-TAMT[tamT][1]);
    if(!(a.consola||[]).length){
      // Sin stdout tee-ado (p. ej. el arbol principal, que no tiene orquestador):
      // la tarjeta enseña sus hechos de firma; si tampoco hay (el mapa canonico
      // se deriva de ese mismo arbol), que nodos toca. Nunca muda.
      visibles=(a.cambios||[]).slice(-TAMT[tamT][1]);
      if(!visibles.length){
        const mios=NODOS.filter(n=>(n.ag||[]).indexOf(t.nom)>=0).map(n=>n.id);
        visibles=mios.length
          ? ['toca: '+mios.slice(0,3).join(', ')+(mios.length>3?' +'+(mios.length-3):'')]
          : ['(sin consola tee-ada ni cambios de firma)'];
      }
    }
    h+=visibles.map((l,i)=>
      '<div class="tl'+(cayendo && i===visibles.length-1?' nueva':'')+'">'+escapa(l)+'</div>').join('')+
      (vivo?'<span class="cur" style="color:'+a.c+'">&#9612;</span>':'');
    t.el.innerHTML=h;
  }
  // El hilo tarjeta-nodo: al arrastrarla lejos se perdia DE QUE nodo colgaba.
  // Un div de 1px rotado (nada de SVG: su namespace es una URL literal y el
  // mapa se prueba autocontenido con un simple `http no aparece`).
  const hilos=document.createElement('div');
  hilos.id='hilos';
  document.body.appendChild(hilos);
  for(const nom of Object.keys(AGENTES).sort()){
    const a=AGENTES[nom];
    let idx=null;
    for(const n of NODOS){ if((n.ag||[]).indexOf(nom)>=0){ idx=IDXN[n.id]; break; } }
    const el=document.createElement('div');
    el.className='term'; el.dataset.ag=nom;
    termCont.appendChild(el);
    const orden = idx==null ? 0 : (anclados[idx]=(anclados[idx]||0)+1)-1;
    const total=(a.consola||[]).length;
    let desde=total;  // sin marca previa: todo visto, nada que llover
    const marca=vistos[nom];
    if(marca){
      desde=0;
      for(let i=total-1;i>=0;i--){ if(a.consola[i]===marca){ desde=i+1; break; } }
      // La marca puede haberse salido de la ventana de 40 lineas (agente muy
      // hablador): llover 40 desde cero tarda 28 s y la tarjeta se ve VACIA
      // mientras tanto. Rastro perdido: se enseña casi todo y llueve el final.
      if(desde===0) desde=Math.max(0, total-6);
    }
    if(desde>0) vistos[nom]=a.consola[desde-1];
    let hilo=null;
    if(idx!=null){
      hilo=document.createElement('div');
      hilo.className='hilo';
      hilo.style.borderTopColor=a.c;
      hilos.appendChild(hilo);
    }
    const t={el:el, nom:nom, idx:idx, orden:orden, hilo:hilo,
             reveladas:desde, suelto: idx==null ? sueltos++ : -1};
    renderTerm(t);
    TERMS.push(t);
  }
  try{ sessionStorage.setItem(VMEM, JSON.stringify(vistos)); }catch(_){}
  let tickHace=0;
  setInterval(()=>{
    let cambio=false;
    for(const t of TERMS){
      const cons=(AGENTES[t.nom]||{}).consola||[];
      if(t.reveladas<cons.length){
        // Sin deuda eterna: si la lluvia va mas de 12 lineas por detras del
        // agente, salta al presente y llueven solo las ultimas.
        if(cons.length-t.reveladas>12) t.reveladas=cons.length-6;
        t.reveladas++;
        vistos[t.nom]=cons[t.reveladas-1];
        renderTerm(t, true);
        cambio=true;
      }
    }
    if(cambio){ try{ sessionStorage.setItem(VMEM, JSON.stringify(vistos)); }catch(_){} }
    // Cada ~7 s se re-pinta la cabecera de las tarjetas para que el "hace" y el
    // cursor de vivo envejezcan con la edad real — salvo con texto seleccionado:
    // re-pintar debajo de un Ctrl+C a medias es el mismo robo que la recarga.
    tickHace=(tickHace+1)%%10;
    if(tickHace===0 && !cambio){
      const sel=window.getSelection?window.getSelection():null;
      if(!(sel&&!sel.isCollapsed)) for(const t of TERMS) renderTerm(t);
    }
  }, 700);
  // Desplazables: el arrastre guarda un DESVIO por agente (recordado entre
  // recargas), asi la terminal sigue a su nodo con la camara pero desde donde
  // tu la dejaste — la cura de la superposicion sin soltar el ancla.
  const OMEM='gb-mapa-terminal-pos';
  let desvios={};
  try{ desvios=JSON.parse(sessionStorage.getItem(OMEM)||'{}')||{}; }catch(_){}
  let arrastreT=null, seMovioT=false;
  termCont.addEventListener('mousedown', ev=>{
    if(ev.target && ev.target.dataset && ev.target.dataset.acc) return; // -/+
    let el=ev.target;
    while(el && el!==termCont && !(el.dataset && el.dataset.ag)) el=el.parentNode;
    if(!el || el===termCont || !el.dataset.ag) return;
    const d=desvios[el.dataset.ag]||[0,0];
    arrastreT={nom:el.dataset.ag, x:ev.clientX, y:ev.clientY, dx:d[0], dy:d[1]};
    seMovioT=false;
    window._arrastrandoTerm=true;  // la recarga automatica se aplaza mientras
    ev.preventDefault();
  });
  addEventListener('mousemove', ev=>{
    if(!arrastreT) return;
    const nx=ev.clientX-arrastreT.x, ny=ev.clientY-arrastreT.y;
    if(Math.abs(nx)+Math.abs(ny)>3) seMovioT=true;
    desvios[arrastreT.nom]=[arrastreT.dx+nx, arrastreT.dy+ny];
  });
  addEventListener('mouseup', ()=>{
    window._arrastrandoTerm=false;
    if(!arrastreT) return;
    arrastreT=null;
    try{ sessionStorage.setItem(OMEM, JSON.stringify(desvios)); }catch(_){}
  });
  termCont.addEventListener('click', ev=>{
    const acc = ev.target && ev.target.dataset ? ev.target.dataset.acc : null;
    if(acc==='tmenos' || acc==='tmas'){
      tamT=Math.max(0, Math.min(TAMT.length-1, tamT+(acc==='tmas'?1:-1)));
      try{ sessionStorage.setItem(TMEM, String(tamT)); }catch(_){}
      for(const t of TERMS) renderTerm(t);
      return;
    }
    if(seMovioT){ seMovioT=false; return; }  // arrastrar no es enfocar
    let el=ev.target;
    while(el && el!==termCont && !(el.dataset && el.dataset.ag)) el=el.parentNode;
    const nom=(el && el.dataset) ? el.dataset.ag : null;
    if(!nom) return;
    agenteFoco=(agenteFoco===nom)?null:nom;
    calculaCercaAg(); recuerda(); pintaConsola();
    for(const t of TERMS) renderTerm(t);  // el foco se ve en la tarjeta
  });
  if(TERMS.length){
    (function animaTerms(){
      for(const t of TERMS){
        const d=desvios[t.nom]||[0,0];
        if(t.idx==null){
          // Agente sin nodo en el mapa todavia: su terminal se apila a la
          // izquierda, bajo la cabecera REAL — la altura fija de antes se
          // solapaba con la barra de buscar cuando la leyenda crecia.
          const hh=((document.querySelector('header')||{}).offsetHeight||84)+10;
          t.el.style.transform='none';
          t.el.style.left=(12+d[0])+'px';
          t.el.style.top=(hh+(t.el.offsetHeight+8)*t.suelto+d[1])+'px';
          continue;
        }
        const nx=X[t.idx]*esc+ox, ny=Y[t.idx]*esc+oy;
        const cx=nx+d[0], cy=ny-14-(t.el.offsetHeight+6)*t.orden+d[1];
        t.el.style.left=cx+'px';
        t.el.style.top=cy+'px';
        if(t.hilo){
          const hx=cx-nx, hy=cy-ny;
          t.hilo.style.left=nx+'px'; t.hilo.style.top=ny+'px';
          t.hilo.style.width=Math.hypot(hx,hy)+'px';
          t.hilo.style.transform='rotate('+Math.atan2(hy,hx)+'rad)';
        }
      }
      requestAnimationFrame(animaTerms);
    })();
  }
})();

// ---- consola de errores -----------------------------------------------------
// Separada de la de actividad A PROPOSITO: se probo mezclarlas y una tirada
// entierra las capturas bajo los toca/escribe. Una fila por captura, el estado
// de lectura en el color, y el gb show exacto. El boton &#9888; la abre/cierra.
(function(){
  const erroresEl=document.getElementById('errores');
  const btn=document.getElementById('btnErrores');
  if(!erroresEl || !btn) return;
  const EMEM='gb-mapa-errores';
  let est=null; try{ est=JSON.parse(sessionStorage.getItem(EMEM)||'null'); }catch(_){}
  let abierto = est ? est.abierto!==0 : true;
  const TAME=[[300,'22vh'],[380,'32vh'],[520,'55vh']];
  let tamE = (est && typeof est.tam==='number') ? est.tam : 1;
  function guarda(){ try{ sessionStorage.setItem(EMEM,
    JSON.stringify({abierto:abierto?1:0, tam:tamE})); }catch(_){} }
  function pinta(){
    if(!abierto){ erroresEl.style.display='none'; return; }
    erroresEl.style.width=TAME[tamE][0]+'px';
    erroresEl.style.maxHeight=TAME[tamE][1];
    const filas=(CAPTURAS||[]).length ? (CAPTURAS||[]).map(c=>
      '<div class="fila"><span class="hora">'+escapa((c.ts||'').slice(11,19))+'</span>'+
      '<span class="quien" style="color:'+(c.leida?'var(--suave)':'#f87171')+'">'+
      escapa(c.nodo||c.donde||'?')+'</span>'+
      '<span class="que">'+escapa(c.tipo||'?')+'</span>'+
      '<span class="detalle">'+(c.leida?'leida':'SIN LEER')+
      ' · gb show '+escapa(String(c.id).slice(0,8))+'</span></div>').join('')
      : '<div class="fila"><span class="detalle">(0 capturas: nada ha petado '+
        'en este proyecto)</span></div>';
    erroresEl.innerHTML='<div class="cab"><span>consola de errores · '+(SIN_LEER||0)+
      ' sin leer</span><span><b data-acc="emenos" title="mas pequena">&#8722;</b>'+
      '<b data-acc="emas" title="mas grande">+</b>'+
      '<b data-acc="cerrar" title="ocultar">&#10005;</b></span></div>'+filas;
    erroresEl.style.display='block';
  }
  erroresEl.addEventListener('click', ev=>{
    const acc=ev.target&&ev.target.dataset?ev.target.dataset.acc:null;
    if(!acc) return;
    if(acc==='cerrar') abierto=false;
    else if(acc==='emenos') tamE=Math.max(0, tamE-1);
    else if(acc==='emas') tamE=Math.min(TAME.length-1, tamE+1);
    guarda(); pinta();
  });
  btn.addEventListener('click', ()=>{ abierto=!abierto; guarda(); pinta(); });
  hazArrastrable(erroresEl, 'gb-mapa-errores-pos');
  pinta();
})();

// La recarga automatica, por JS y con modales: se APLAZA mientras se escribe
// en buscar, se arrastra una tarjeta o hay texto seleccionado. Un refresco que
// borra lo tecleado — o la seleccion justo antes del Ctrl+C — enseña a no usar
// la busqueda ni a copiar del mapa; y eso es peor que un mapa 10 s mas viejo.
if(REFRESCO>0){
  // Aplazar no puede ser aplazar PARA SIEMPRE: una seleccion olvidada dejaba
  // el mapa congelado indefinidamente y se leia como "no pasa nada" — el
  // sintoma que costo tres sesiones sin ver la actividad (8-ago). Se aplaza
  // hasta 10 ticks (~30 s con refresco 3) y luego manda el dato fresco: nadie
  // tarda medio minuto en copiar, y un mapa viejo miente.
  let aplazados=0;
  setInterval(()=>{
    if(document.activeElement===buscar) return;   // escribir SI bloquea sin tope
    if(window._arrastrandoTerm) return;           // arrastrar tambien
    const sel=window.getSelection?window.getSelection():null;
    if(sel&&!sel.isCollapsed&&aplazados<10){ aplazados++; return; }
    aplazados=0;
    location.reload();
  }, REFRESCO*1000);
}
// Lo buscado sobrevive a la recarga: valor restaurado y filtro re-aplicado.
try{ const _b=sessionStorage.getItem('gb-mapa-buscar');
     if(_b && !buscar.value){ buscar.value=_b; buscar.dispatchEvent(new Event('input')); } }catch(_){}
buscar.addEventListener('input', ()=>{
  try{ sessionStorage.setItem('gb-mapa-buscar', buscar.value); }catch(_){}
});

medir(); recupera(); requestAnimationFrame(bucle);
</script>
"""
