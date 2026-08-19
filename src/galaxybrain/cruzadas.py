"""Las llamadas ENTRE LENGUAJES que se pueden leer del código, sin ejecutarlo.

La literatura da este problema por abierto, pero ataca el caso difícil: FFI,
donde el destino es un símbolo que se resuelve en tiempo de ejecución. El caso
corriente de un repo mixto es más tonto y más frecuente — alguien **lanza un
proceso** — y deja dos rastros que NO son lo mismo y por eso no se mezclan:

1. **El sitio de llamada.** `spawnSync`, `ProcessBuilder`, `exec.Command`,
   `system(...)`, `Process.Start`. Es sintaxis pura: se encuentra siempre y en
   todos los lenguajes. Medido sobre el proyecto políglota: 13 de 13.
2. **El destino.** Solo se sabe si está escrito ahí: un literal que apunta a un
   fichero que EXISTE en el árbol. Con la ruta escrita (`spawnSync("ruby",
   ["paso.rb"])`, `os.execute("php x.php")`) sale el 100 %; cuando el comando
   viaja en una variable de entorno, el 0 % — y ese cero es correcto, porque
   ahí no hay nada escrito que resolver.

Por eso la arista sale marcada como **candidata**: dice «este fichero lanza
ese», no «esto ocurrió». Quien confirma es la tirada — el `parent_span` del
trace W3C que escriben los hooks (`cli._cadena_para_mapa`). Una es lo que el
código dice; la otra es lo que pasó, y el mapa las pinta distintas.

Lo que NO se hace: adivinar el destino cuando viene de una variable. Una arista
inventada es peor que un hueco, porque manda a leer el fichero que no es.
"""

import os
import re

#: El patron de "aqui se lanza un proceso", por extension. Sintaxis, no
#: semantica: por eso acierta siempre y no depende de resolver nombres.
LANZADORES = {
    ".js": (r"\bspawnSync\s*\(", r"\bspawn\s*\(", r"\bexecFile\s*\(", r"\bexecSync\s*\("),
    ".mjs": (r"\bspawnSync\s*\(", r"\bspawn\s*\(", r"\bexecFile\s*\("),
    ".ts": (r"\bspawnSync\s*\(", r"\bspawn\s*\(", r"\bexecFile\s*\("),
    ".tsx": (r"\bspawnSync\s*\(", r"\bspawn\s*\("),
    ".py": (r"\bsubprocess\.(?:run|Popen|call|check_output|check_call)\s*\(", r"\bos\.system\s*\("),
    ".rb": (r"\bsystem\s*\(", r"\bProcess\.spawn\b", r"\bIO\.popen\b"),
    ".php": (r"\bpassthru\s*\(", r"\bshell_exec\s*\(", r"\bproc_open\s*\(", r"\bexec\s*\("),
    ".lua": (r"\bos\.execute\s*\(", r"\bio\.popen\s*\("),
    ".java": (r"\bProcessBuilder\s*\(", r"Runtime\.getRuntime\(\)\.exec\s*\("),
    ".kt": (r"\bProcessBuilder\s*\(",),
    ".scala": (r"\bProcessBuilder\s*\(",),
    ".cs": (r"\bProcess\.Start\s*\(", r"\bProcessStartInfo\s*\("),
    ".c": (r"\bsystem\s*\(", r"\bCreateProcess[AW]?\s*\(", r"\bexecv?[lp]?e?\s*\("),
    ".h": (r"\bCreateProcess[AW]?\s*\(",),
    ".go": (r"\bexec\.Command\s*\(",),
    ".rs": (r"Command::new\s*\(",),
    ".dart": (r"\bProcess\.(?:run|start|runSync)\s*\(",),
}

_LITERAL = re.compile(r"""["']([^"']{2,160})["']""")

#: Cuanto se lee de un fichero como mucho. Un `.min.js` de 4 MB no aporta
#: sitios de llamada utiles y si aporta medio segundo de espera.
TOPE_BYTES = 400_000


def _literales_de(linea):
    """Los trozos de un literal que pueden ser un fichero.

    El literal puede ser el fichero suelto (`"paso.rb"`) o una LINEA DE COMANDO
    entera (`"php paso.php"`, `"go run paso.go"`). Mirar solo el literal
    completo perdia justo las segundas, que son mayoria en lua, php y C — los
    que ejecutan por shell. Medido: 60 % -> 100 % en el banco literal.
    """
    for cand in _LITERAL.findall(linea):
        yield cand
        for trozo in re.split(r"\s+", cand):
            if trozo:
                yield trozo


def sitios(root, tope=2000):
    """Donde se lanza un proceso, y a quien cuando esta escrito.

    Devuelve una lista de `{fichero, lang, linea, texto, destino}`. `destino` es
    la ruta absoluta del fichero llamado, o None si el comando viene de una
    variable — que es un hecho tambien, y por eso el sitio se devuelve igual.
    """
    del_arbol, vistos = {}, 0
    for base, dirs, nombres in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                   ("node_modules", "target", "build", "dist", "obj", "bin",
                    "__pycache__", "venv", ".venv")]
        for nombre in nombres:
            if os.path.splitext(nombre)[1].lower() in LANZADORES:
                del_arbol.setdefault(nombre.lower(), os.path.join(base, nombre))
                vistos += 1
        if vistos >= tope:
            break

    fuera = []
    for nombre_bajo, ruta in sorted(del_arbol.items()):
        ext = os.path.splitext(ruta)[1].lower()
        try:
            if os.path.getsize(ruta) > TOPE_BYTES:
                continue
            with open(ruta, encoding="utf-8", errors="replace") as fh:
                texto = fh.read()
        except OSError:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            if not any(re.search(p, linea) for p in LANZADORES[ext]):
                continue
            destino = None
            for trozo in _literales_de(linea):
                base_t = os.path.basename(trozo).lower()
                if base_t in del_arbol and base_t != nombre_bajo:
                    destino = del_arbol[base_t]
                    break
            fuera.append({
                "fichero": ruta,
                "lang": ext.lstrip("."),
                "linea": n,
                "texto": linea.strip()[:120],
                "destino": destino,
            })
    return fuera


def aristas(root, informe_simbolos, informe_grafo=None, tope=2000):
    """Los sitios con destino resuelto, como aristas entre nodos del mapa.

    Solo las resueltas: una arista sin destino no es media arista, es ninguna.
    Los sitios sin resolver siguen ahi (`sitios()`) porque saber que un fichero
    LANZA algo es util aunque no se sepa a quien.
    """


    # Los modulos salen de los DOS informes: en un proyecto pequeño o sin
    # funciones, el de simbolos puede no traer ninguno y el del grafo si. Con
    # uno solo, las aristas se caian sin decir por que (medido en el banco
    # literal: 5 sitios resueltos y 0 aristas dibujadas).
    modulos = {}
    for informe in (informe_simbolos, informe_grafo):
        for n in (informe or {}).get("nodes", []) or ():
            if n.get("kind") == "module" and n.get("qual"):
                modulos.setdefault(os.path.normcase(n["qual"]), n["qual"])

    def qual_de(ruta):
        """Ruta -> nombre de modulo, para CUALQUIER extension.

        `graph.module_name` corta tres caracteres porque es de y para Python:
        con `.lua` o `.php` devolvia `paso_lua.` —con el punto colgando— y la
        arista no casaba con ningun nodo. Aqui se quita la extension de verdad.
        """
        try:
            rel = os.path.relpath(ruta, root).replace("\\", "/")
        except ValueError:   # otra unidad de disco en Windows
            return ""
        partes = [p for p in rel.split("/") if p and p != "."]
        if partes and partes[0] == "src":
            partes = partes[1:]
        if not partes:
            return ""
        if partes[-1] == "__init__.py":
            partes = partes[:-1]
        else:
            partes[-1] = os.path.splitext(partes[-1])[0]
        return ".".join(partes)

    def nodo_de(ruta):
        return modulos.get(os.path.normcase(qual_de(ruta)))

    fuera, vistas = [], set()
    for sitio in sitios(root, tope):
        if not sitio["destino"]:
            continue
        de, a = nodo_de(sitio["fichero"]), nodo_de(sitio["destino"])
        if not de or not a or de == a or (de, a) in vistas:
            continue
        vistas.add((de, a))
        fuera.append({"de": de, "a": a, "linea": sitio["linea"],
                      "lang": sitio["lang"]})
    return fuera
