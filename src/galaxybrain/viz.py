"""El mapa, en imagen. Un solo fichero HTML autocontenido.

§10 nivel 3 pide *"un mapa, no una lectura"*, y `gb graph` ya lo da en texto. Esto es
el mismo hecho pintado: no hay dato nuevo, hay otra forma de mirarlo.

Dos decisiones que no son estéticas:

**Posiciones DETERMINISTAS, calculadas en Python.** Un layout de fuerzas queda más
bonito y salta en cada ejecución, y entonces dos capturas del mismo proyecto no se
pueden comparar — que es justamente lo que uno quiere al mirar crecer algo. Aquí la
posición sale de la estructura (capas por profundidad de dependencia, orden alfabético
dentro de cada capa), así que **el mismo grafo da siempre la misma imagen** y lo que
se mueve es porque el proyecto se movió.

**Cero dependencias, un fichero.** Nada de CDN, ni npm, ni build. El SVG se calcula
aquí y el HTML se escribe entero; se abre con doble clic o desde VS Code. Esto no es
purismo: la regla de cero dependencias existe para que `gb` se pueda instalar en el
venv de cualquier proyecto sin arrastrar nada, y un visor no es motivo para romperla.

Los ciclos van marcados, porque son el único hecho de este mapa que exige una decisión.
Con `--since`, lo NUEVO va marcado aparte: ver crecer un proyecto es, sobre todo, ver
qué apareció desde la última vez.
"""

import html as _html


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
