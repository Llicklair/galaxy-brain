"""El mapa, en imagen. Un solo fichero HTML autocontenido.

§10 nivel 3 pide *"un mapa, no una lectura"*, y `gb graph` ya lo da en texto. Esto es
el mismo hecho pintado: no hay dato nuevo, hay otra forma de mirarlo.

Dos decisiones que no son estéticas:

**Posiciones DETERMINISTAS, calculadas en Python.** Dos capturas del mismo proyecto
tienen que poder compararse; si las cajas bailan solas, mirar crecer algo no dice
nada. Aquí el mismo grafo da siempre la misma imagen, y lo que se mueva es porque el
proyecto se movió.

Aviso sobre una afirmación anterior de este mismo fichero, que era **falsa**: se dijo
que un layout de fuerzas renuncia al determinismo. No es cierto — un layout de
fuerzas solo baila si lo arrancas al azar. Con posiciones iniciales deterministas e
iteraciones fijas sale idéntico siempre, así que se puede tener el aspecto orgánico
*y* la comparabilidad. Ver `force_layout`.

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


def force_layout(nodes, edges, iteraciones=320, lado=1000.0):
    """Fruchterman-Reingold, **determinista**: mismo grafo, mismas posiciones.

    Un layout de fuerzas solo baila entre ejecuciones si lo arrancas al azar. Aquí
    los nodos empiezan repartidos en un círculo por orden alfabético y se corren
    iteraciones fijas, así que el resultado es reproducible byte a byte — se puede
    tener el aspecto orgánico Y poder comparar dos capturas del mismo proyecto.

    O(n²) por iteración: de sobra hasta unos pocos miles de nodos, que es el techo
    en el que un grafo así sigue siendo legible de todas formas.
    """
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: (lado / 2, lado / 2)}

    indice = {nodo: i for i, nodo in enumerate(nodes)}
    radio = lado / 2.5
    pos = {}
    for i, nodo in enumerate(nodes):
        angulo = 2 * math.pi * i / n
        pos[nodo] = [lado / 2 + radio * math.cos(angulo), lado / 2 + radio * math.sin(angulo)]

    pares = [
        (indice[a], indice[b])
        for a, b in edges
        if a in indice and b in indice and a != b
    ]
    k = math.sqrt((lado * lado) / n)
    temperatura = lado / 10.0
    enfriamiento = temperatura / (iteraciones + 1)

    lista = [pos[nodo] for nodo in nodes]
    for _ in range(iteraciones):
        desplazamiento = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            xi, yi = lista[i]
            for j in range(i + 1, n):
                dx = xi - lista[j][0]
                dy = yi - lista[j][1]
                dist2 = dx * dx + dy * dy
                if dist2 < 0.01:
                    # Superpuestos: se separan de forma DETERMINISTA (por indice), no
                    # con un aleatorio, que es lo que rompe la reproducibilidad.
                    dx, dy, dist2 = 0.01 * (i + 1), 0.01 * (j + 1), 0.0002
                dist = math.sqrt(dist2)
                fuerza = (k * k) / dist
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
            dx, dy = desplazamiento[i]
            largo = math.sqrt(dx * dx + dy * dy) or 1.0
            paso = min(largo, temperatura)
            lista[i][0] += dx / largo * paso
            lista[i][1] += dy / largo * paso
            lista[i][0] = max(10.0, min(lado - 10.0, lista[i][0]))
            lista[i][1] = max(10.0, min(lado - 10.0, lista[i][1]))
        temperatura -= enfriamiento

    return {nodo: (round(lista[i][0], 2), round(lista[i][1], 2)) for nodo, i in indice.items()}


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


#: Paleta por cluster: saturada, para fondo casi negro. Los tonos apagados que
#: funcionan sobre papel se comen unos a otros aqui — con 150 circulos pequenios lo
#: unico que separa un grupo de otro es el color, asi que tiene que gritar.
#: Asignada por orden alfabetico del grupo: mismo proyecto, mismos colores siempre.
_COLORES = [
    "#7c5cff", "#22d3ee", "#f472b6", "#fb923c", "#4ade80",
    "#60a5fa", "#c084fc", "#facc15", "#2dd4bf", "#f87171",
    "#a3e635", "#e879f9",
]


def render_graph_cloud(report, title="galaxy-brain — grafo", modo="simbolos"):
    """La nube: nodos repartidos por fuerzas, coloreados por módulo, navegable.

    Mismo dato que el informe, otro modo de mirarlo — este responde *"¿qué forma
    tiene esto?"* y el de capas responde *"¿qué depende de qué?"*. Las posiciones se
    calculan aquí (deterministas), así que el navegador solo dibuja: ni layout en
    JS, ni librería, ni WebGL.
    """
    if modo == "simbolos":
        llamadas = [(a, b) for a, b, tipo in report.get("edges", []) if tipo == "CALLS"]
        kinds = {n["qual"]: n["kind"] for n in report.get("nodes", [])}
        grupo_de = {n["qual"]: n.get("module", "") for n in report.get("nodes", [])}
        implicados = sorted({x for par in llamadas for x in par})
        total = report.get("calls_candidates") or 0
        pct = round(100 * report.get("calls_resolved", 0) / total) if total else 0
        resumen = "%d simbolos · %d llamadas resueltas de %d (%d%%)" % (
            len(implicados), report.get("calls_resolved", 0), total, pct)
        pie = "sin resolver: " + ", ".join(
            "%s %d" % (k, v) for k, v in sorted((report.get("unresolved") or {}).items())
        )
    else:
        llamadas = [(a, b) for a, b in (report.get("edge_list") or [])]
        implicados = sorted(report.get("fan_in", {}))
        kinds = {m: "module" for m in implicados}
        grupo_de = {m: m.split(".")[0] for m in implicados}
        resumen = "%d modulos · %d aristas · %d ciclo(s)" % (
            report.get("modules", 0), report.get("edges", 0), len(report.get("cycles") or []))
        pie = str(report.get("root", ""))

    pos = force_layout(implicados, llamadas)
    grados = {}
    for a, b in llamadas:
        grados[a] = grados.get(a, 0) + 1
        grados[b] = grados.get(b, 0) + 1

    grupos = sorted({grupo_de.get(n, "") for n in implicados})
    color_de = {g: _COLORES[i % len(_COLORES)] for i, g in enumerate(grupos)}

    datos = [
        {
            "id": n,
            "x": pos[n][0],
            "y": pos[n][1],
            "r": round(4 + 2.2 * math.sqrt(grados.get(n, 0)), 2),
            "c": color_de.get(grupo_de.get(n, ""), _COLORES[0]),
            "g": grupo_de.get(n, ""),
            "k": kinds.get(n, ""),
            "l": n.split(".")[-1],
        }
        for n in implicados
    ]
    import json as _json

    return _NUBE % {
        "title": _html.escape(title),
        "resumen": _html.escape(resumen),
        "pie": _html.escape(pie),
        "nodos": _json.dumps(datos, ensure_ascii=False),
        "aristas": _json.dumps(
            [[implicados.index(a), implicados.index(b)] for a, b in llamadas
             if a in pos and b in pos],
        ),
        "leyenda": "".join(
            '<span><i style="background:%s"></i>%s</span>'
            % (color_de[g], _html.escape(g.split(".")[-1] or "—"))
            for g in grupos[:12]
        ),
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
  :root{--fondo:#0a0d14;--tinta:#e8edf3;--suave:#7d8b9c;--linea:#1e2836;--panel:#111722}
  @media (prefers-color-scheme:light){
    :root{--fondo:#eef1f4;--tinta:#131c24;--suave:#5b6b78;--linea:#c3cdd6;--panel:#fff}}
  *{box-sizing:border-box}
  body{margin:0;background:var(--fondo);color:var(--tinta);overflow:hidden;
       font:13px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
  header{position:fixed;top:0;left:0;right:0;z-index:5;padding:10px 14px;
         background:var(--panel);border-bottom:1px solid var(--linea);
         display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  h1{font:600 14px ui-monospace,Consolas,monospace;margin:0;letter-spacing:-.02em}
  .meta{font:11px ui-monospace,Consolas,monospace;color:var(--suave)}
  input{background:var(--fondo);border:1px solid var(--linea);color:var(--tinta);
        border-radius:4px;padding:5px 9px;font:12px ui-monospace,Consolas,monospace;width:210px}
  input:focus{outline:2px solid #4a7fb5;outline-offset:1px}
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
  <input id="buscar" placeholder="buscar simbolo..." autocomplete="off">
  <span class="leyenda">%(leyenda)s</span>
</header>
<canvas id="lienzo"></canvas>
<div id="ficha"></div>
<div id="pie">%(pie)s</div>
<script>
const NODOS = %(nodos)s, ARISTAS = %(aristas)s;
const cv = document.getElementById('lienzo'), cx = cv.getContext('2d');
const ficha = document.getElementById('ficha'), buscar = document.getElementById('buscar');
let esc = 1, ox = 0, oy = 0, activo = null, filtro = '';
const vecinos = NODOS.map(() => new Set());
ARISTAS.forEach(([a, b]) => { vecinos[a].add(b); vecinos[b].add(a); });

function medir(){ cv.width = innerWidth; cv.height = innerHeight;
  const m = Math.min(cv.width, cv.height - 60) / 1020; esc = m; ox = (cv.width - 1000*m)/2; oy = 60 + (cv.height - 60 - 1000*m)/2; }
function px(n){ return [n.x*esc + ox, n.y*esc + oy]; }

function pinta(){
  cx.clearRect(0,0,cv.width,cv.height);
  const resalta = activo !== null ? vecinos[activo] : null;
  cx.lineWidth = 1;
  ARISTAS.forEach(([a,b]) => {
    const tocada = activo !== null && (a === activo || b === activo);
    if (activo !== null && !tocada) { cx.globalAlpha = 0.03; } else { cx.globalAlpha = tocada ? 0.9 : 0.16; }
    cx.strokeStyle = tocada ? NODOS[a].c : NODOS[a].c;
    const [x1,y1] = px(NODOS[a]), [x2,y2] = px(NODOS[b]);
    cx.beginPath(); cx.moveTo(x1,y1); cx.lineTo(x2,y2); cx.stroke();
  });
  NODOS.forEach((n,i) => {
    const coincide = filtro && n.id.toLowerCase().includes(filtro);
    const cerca = activo === null || i === activo || resalta.has(i);
    cx.globalAlpha = filtro ? (coincide ? 1 : 0.08) : (cerca ? 1 : 0.12);
    const [x,y] = px(n);
    cx.beginPath(); cx.arc(x, y, n.r*Math.max(esc,0.55), 0, 6.284);
    cx.fillStyle = n.c; cx.fill();
    if (i === activo || coincide){ cx.strokeStyle = '#fff'; cx.lineWidth = 1.5; cx.stroke(); }
    if (i === activo || coincide){
      cx.globalAlpha = 1;
      cx.fillStyle = getComputedStyle(document.body).color;
      cx.font = '10px ui-monospace,Consolas,monospace';
      cx.fillText(n.l, x + n.r*esc + 3, y + 3);
    }
  });
  cx.globalAlpha = 1;
}

function cercano(mx,my){
  let mejor = null, dmin = 18;
  NODOS.forEach((n,i) => { const [x,y] = px(n); const d = Math.hypot(x-mx, y-my);
    if (d < dmin){ dmin = d; mejor = i; } });
  return mejor;
}
cv.addEventListener('mousemove', e => {
  if (arrastrando){ ox += e.clientX-lx; oy += e.clientY-ly; lx=e.clientX; ly=e.clientY; pinta(); return; }
  const i = cercano(e.clientX, e.clientY);
  if (i !== activo){
    activo = i;
    if (i === null) ficha.style.display = 'none';
    else { const n = NODOS[i];
      ficha.innerHTML = '<b>'+n.id+'</b><br><span>'+(n.k||'')+' · '+vecinos[i].size+' conexiones · '+(n.g||'')+'</span>';
      ficha.style.display = 'block'; }
    pinta();
  }
});
let arrastrando=false, lx=0, ly=0;
cv.addEventListener('mousedown', e => { arrastrando=true; lx=e.clientX; ly=e.clientY; cv.classList.add('arrastrando'); });
addEventListener('mouseup', () => { arrastrando=false; cv.classList.remove('arrastrando'); });
cv.addEventListener('wheel', e => { e.preventDefault();
  const k = e.deltaY>0 ? 0.9 : 1.1;
  ox = e.clientX - (e.clientX-ox)*k; oy = e.clientY - (e.clientY-oy)*k; esc *= k; pinta();
}, {passive:false});
buscar.addEventListener('input', e => { filtro = e.target.value.trim().toLowerCase(); pinta(); });
addEventListener('resize', () => { medir(); pinta(); });
medir(); pinta();
</script>
"""
