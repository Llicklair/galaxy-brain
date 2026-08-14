"""El mapa vivo como UN fichero HTML — la version fina del canvas recortado.

La v1 (viz.py, 1.803 lineas) murio por su maquinaria, no por su idea: watch
propio con candado, relanzamientos, procesos colgados, y cinco semanas sin una
medicion a favor (SCOPE.md, recorte 3229ddd). Esta version no tiene maquinaria
QUE PUEDA morir: `gb who --watch --html` escribe un HTML autocontenido por
tick (escritura atomica) y el navegador se refresca solo con <meta refresh>.
Sin servidor, sin websockets, sin proceso extra.

La apuesta original decia "un mapa parado con fecha no miente" — y se midio
falsa (14-ago-2026): la fecha estaba y aun asi un "nadie esta tocando nada" de
hace una hora se leyo en presente. La fecha es un dato; la MENTIRA esta en el
tiempo verbal. Por eso la foto ahora se envejece sola: lleva su epoca y un
reloj inline la cuenta en pantalla; pasado su limite —la ventana de presencia
si es foto unica, 3 ticks si la escribia un watch— se marca VIEJA y atenua lo
que enseña. El mismo mecanismo delata el watch muerto: el <meta refresh>
recarga el mismo fichero congelado, y el reloj lo dice en vez de disimularlo.

Todo lo que pinta viene de `actividad.instantanea()`: presencia derivada,
simbolo exacto, cruces. Cero fuentes propias de verdad.
"""

import html as _html
import os
import time

# La ventana de presencia mas ancha (commit reciente). Una foto mas vieja que
# esto no puede estar enseñando NADA que siga siendo presencia: es el limite
# natural para declararla vieja. Importada, no duplicada, para que no deriven.
from .actividad import VENTANA_COMMIT


def _e(texto):
    return _html.escape(str(texto), quote=True)


def render(foto, refresco=0):
    """El HTML del mapa, autocontenido. `refresco` > 0 añade el auto-reload."""
    ahora = time.time()
    # Con watch, 3 ticks sin reescritura = el escritor murio (con suelo de 10s
    # para refrescos de 1-3s: un so cargado no es un watch muerto). Sin watch,
    # la foto es legitima hasta que es mas vieja que la propia presencia.
    limite = max(3 * refresco, 10) if refresco else VENTANA_COMMIT
    partes = []
    partes.append("<!doctype html><html lang='es'><head><meta charset='utf-8'>")
    if refresco:
        partes.append("<meta http-equiv='refresh' content='%d'>" % max(1, refresco))
    partes.append("<title>gb who — mapa vivo</title><style>")
    partes.append(
        "body{background:#0d1117;color:#c9d1d9;font-family:Consolas,monospace;"
        "margin:2em;line-height:1.5}"
        "h1{font-size:1.1em;color:#58a6ff}"
        ".meta{color:#8b949e;font-size:.85em;margin-bottom:1.5em}"
        ".agente{border:1px solid #30363d;border-radius:8px;padding:.8em 1.2em;"
        "margin:.8em 0;background:#161b22}"
        ".nombre{color:#7ee787;font-weight:bold}"
        ".hace{color:#8b949e;font-size:.85em;margin-left:.6em}"
        ".base-mal{color:#f85149;font-size:.85em;margin-left:.6em}"
        ".simbolo{color:#c9d1d9;margin-left:1.5em}"
        ".fuera{color:#d29922;margin-left:1.5em}"
        ".commit{color:#8b949e;margin-left:1.5em;font-size:.9em}"
        ".cruces{border:1px solid #f85149;border-radius:8px;padding:.8em 1.2em;"
        "margin-top:1.5em;background:#2d1517}"
        ".cruces h2{color:#f85149;font-size:1em;margin:0 0 .5em 0}"
        ".cruce{color:#ffa198;margin-left:1em}"
        ".vacio{color:#8b949e;font-style:italic}"
        "#vieja{border:1px solid #f85149;border-radius:8px;padding:.8em 1.2em;"
        "margin:.8em 0;background:#2d1517;color:#ffa198;font-weight:bold}"
        ".parada .agente,.parada .cruces,.parada .vacio{opacity:.35}"
        "</style></head>")
    partes.append("<body data-gen='%d' data-limite='%d'>" % (int(ahora), limite))
    partes.append("<h1>gb who — quien toca que</h1>")
    hora = time.strftime("%H:%M:%S", time.localtime(ahora))
    partes.append(
        "<div class='meta'>base %s · foto de las %s<span id='edad'></span>%s · "
        "derivado de los worktrees (arbol sucio + consola + commit reciente) — "
        "nadie declara nada</div>"
        % (_e(foto.get("base") or "?"), hora,
           (" · refresco %ds" % refresco) if refresco
           else " · foto unica, no se refresca sola — el mapa vivo: "
                "gb who --watch --html"))
    if refresco:
        partes.append(
            "<div id='vieja' hidden>EL WATCH YA NO ESCRIBE — esta foto deberia "
            "renovarse cada %ds y lleva mas de %ds quieta. El mapa esta "
            "congelado, no vacio: relanza gb who --watch --html</div>"
            % (refresco, limite))
    else:
        partes.append(
            "<div id='vieja' hidden>FOTO VIEJA — mas de %ds: mas antigua que "
            "cualquier presencia que pueda enseñar. Lo de abajo fue verdad a "
            "las %s, no ahora. El mapa vivo: gb who --watch --html</div>"
            % (limite, hora))

    if foto.get("motivo"):
        partes.append("<p class='vacio'>%s</p>" % _e(foto["motivo"]))
    elif not foto.get("agentes"):
        partes.append(
            "<p class='vacio'>Nadie tocaba nada a las %s. Quien "
            "commiteo hace rato no aparece: es historia, no presencia.</p>"
            % hora)

    for a in foto.get("agentes") or []:
        hace = ("hace %ds" % a["hace_seg"]) if a.get("hace_seg") is not None else "sin edad"
        partes.append("<div class='agente'><span class='nombre'>%s</span>"
                      "<span class='hace'>%s · base %s · %d fichero(s)</span>%s"
                      % (_e(a["nombre"]), _e(hace), _e(a.get("base") or "?"),
                         a.get("ficheros") or 0,
                         "" if a.get("misma_base")
                         else "<span class='base-mal'>BASE DISTINTA</span>"))
        for s in (a.get("simbolos") or a.get("nodos") or [])[:12]:
            partes.append("<div class='simbolo'>toca %s</div>" % _e(s))
        if a.get("fuera_del_mapa"):
            partes.append("<div class='fuera'>+ %d fichero(s) aun fuera del mapa "
                          "(codigo nuevo)</div>" % a["fuera_del_mapa"])
        if a.get("commitados"):
            partes.append("<div class='commit'>commiteo hace poco: %s</div>"
                          % _e(", ".join(a["commitados"][:5])))
        partes.append("</div>")

    if foto.get("cruces"):
        partes.append("<div class='cruces'><h2>CRUCES — dos o mas agentes "
                      "sobre el mismo nodo</h2>")
        for qual in foto["cruces"]:
            quienes = (foto.get("por_nodo") or {}).get(qual, {}).get("agentes") or []
            partes.append("<div class='cruce'>! %s &larr; %s</div>"
                          % (_e(qual), _e(", ".join(quienes))))
        partes.append("</div>")

    # El reloj: la unica pieza con JS de todo gb, y solo mira Date.now(). La
    # edad se calcula en el navegador porque es EL que puede seguir abierto
    # cuando ya no hay nadie escribiendo; clamp a 0 por si los relojes difieren.
    partes.append(
        "<script>(function(){var b=document.body,"
        "g=1000*+b.dataset.gen,l=1000*+b.dataset.limite;"
        "function f(s){return s<60?s+'s':s<3600?Math.floor(s/60)+'m'"
        ":Math.floor(s/3600)+'h'}"
        "function t(){var e=Math.max(0,Date.now()-g);"
        "document.getElementById('edad').textContent="
        "' \\u00b7 hace '+f(Math.round(e/1000));"
        "if(e>l){document.getElementById('vieja').hidden=false;"
        "b.classList.add('parada')}}"
        "t();setInterval(t,1000)})()</script>")
    partes.append("</body></html>")
    return "".join(partes)


def escribir(destino, foto, refresco=0):
    """Escritura atomica: el navegador nunca lee un HTML a medias."""
    tmp = destino + ".tmp"
    try:
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(render(foto, refresco))
        os.replace(tmp, destino)
    except OSError:
        return None
    return destino
