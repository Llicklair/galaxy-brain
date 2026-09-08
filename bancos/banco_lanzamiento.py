"""El banco de las aristas de lanzamiento: verdad de campo para `cruzadas`.

Un arbol poliglota generado con la verdad ESCRITA antes de medir:

- 4 lanzamientos con destino escrito y unico -> 4 aristas, que ademas forman
  un CICLO trilingue (py -> js -> rb -> py) que el gate tiene que ver.
- 1 lanzamiento con el comando en una variable -> sitio SI, arista NO.
- 1 destino con basename ambiguo (dos dup.js) -> sitio SI, arista NO.

Se corre a mano (`python bancos/banco_lanzamiento.py`) y el resultado se
apunta en docs/pruebas-de-uso.md con fecha, como los demas bancos. CUMPLE =
aristas halladas EXACTAMENTE las esperadas (ni una de mas: una arista
inventada es peor que un hueco), el ciclo visto y el gate en rojo por el.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from galaxybrain import cli, graph  # noqa: E402

ARBOL = {
    "orquesta.py": 'import subprocess\nsubprocess.run(["node", "worker.js"])\n',
    "worker.js": 'const { spawnSync } = require("child_process");\n'
                 'spawnSync("ruby", ["motor.rb"]);\n',
    "motor.rb": 'system("python orquesta.py")\n',
    "plantilla.lua": 'os.execute("php render.php")\n',
    "render.php": "<?php echo 1;\n",
    # comando en variable: sitio sin destino, y ese cero es correcto
    "arranque2.js": "spawnSync(process.env.CMD);\n",
    # basename ambiguo: dos dup.js, nadie puede decir a cual apunta
    "llama_dup.py": 'import subprocess\nsubprocess.run(["node", "dup.js"])\n',
    os.path.join("uno", "dup.js"): "console.log(1);\n",
    os.path.join("dos", "dup.js"): "console.log(2);\n",
}

ESPERADAS = {
    ("orquesta", "worker"),
    ("worker", "motor"),
    ("motor", "orquesta"),
    ("plantilla", "render"),
}


def main():
    with tempfile.TemporaryDirectory() as raiz:
        for rel, texto in ARBOL.items():
            ruta = os.path.join(raiz, rel)
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(texto)

        report = graph.analyze(raiz, constructor=cli._constructor_fusionado)
        halladas = {(a["de"], a["a"]) for a in report["aristas_lanzamiento"]}
        ciclo = any(
            {"orquesta", "worker", "motor"} <= set(c) for c in report["cycles"])
        gate = cli._graph_gate(report)

        print("sitios con destino esperado: %d de %d aristas halladas"
              % (len(halladas & ESPERADAS), len(ESPERADAS)))
        print("aristas inventadas: %d %s"
              % (len(halladas - ESPERADAS), sorted(halladas - ESPERADAS) or ""))
        print("ciclo trilingue py->js->rb visto: %s" % ("SI" if ciclo else "NO"))
        print("gate en rojo por el ciclo: %s (rc=%d)"
              % ("SI" if gate != 0 else "NO", gate))

        cumple = (halladas == ESPERADAS) and ciclo and gate != 0
        print("VEREDICTO: %s" % ("CUMPLE" if cumple else "NO CUMPLE"))
        return 0 if cumple else 1


if __name__ == "__main__":
    raise SystemExit(main())
