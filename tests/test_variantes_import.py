"""La conformidad por MATRIZ, no por ejemplar.

Cada lenguaje se validaba con UNA forma sintactica elegida a ojo, y eso
certificaba en verde una cobertura que el ecosistema real no tenia: el
15-ago-2026 se midio que `from "./a.js"` dejaba arista y `from './a.js'`
no dejaba NINGUNA — solo cambian las comillas, y la sonda estaba escrita
con dobles. Un punto ciego de la sonda, no del patron.

Aqui una variante que el lenguaje considera equivalente se prueba como
equivalente. Las formas no son inventadas: son las que aparecen en codigo
de verdad — barriles de re-export y `import './x.css'` en frontend,
`require()` en backend, `import()` perezoso en cualquier bundle moderno.

Lo que NO cubre una variante se declara en `PENDIENTES` con su motivo, que
es la misma doctrina que `carencias`: un hueco dicho no es una mentira.
"""
import os

import pytest

from galaxybrain import lenguajes

necesita_astgrep = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

#: El modulo importado, por lenguaje: (fichero, fuente).
DESTINO = {
    "js": ("a.js", "export function suma(a, b) { return a + b; }\n"),
    "ts": ("a.ts", "export function suma(a: number, b: number) { return a + b; }\n"),
    "tsx": ("a.tsx", "export function suma(a: number, b: number) { return a + b; }\n"),
    "ruby": ("a.rb", "def suma(a, b)\n  a + b\nend\n"),
    "php": ("a.php", "<?php\nfunction suma($a, $b) { return $a + $b; }\n"),
    "lua": ("a.lua", "function suma(a, b) return a + b end\n"),
    "c": ("a.h", "int suma(int a, int b) { return a + b; }\n"),
}

#: La extension del fichero importador cuando NO es la del destino (en C se
#: incluye una cabecera desde una unidad de compilacion).
EXT_IMPORTADOR = {"c": "c"}

#: (lenguaje, etiqueta) -> fuente del importador. TODAS deben dejar arista
#: b -> a: son la misma dependencia escrita de formas que el lenguaje
#: considera equivalentes.
VARIANTES = {
    # --- comillas: el rojo que motivo esta matriz -------------------------
    ("js", "named-dobles"): 'import { suma } from "./a.js";\n',
    ("js", "named-simples"): "import { suma } from './a.js';\n",
    ("ts", "named-simples"): "import { suma } from './a';\n",
    ("tsx", "named-simples"): "import { suma } from './a';\n",
    # --- formas de importar (frontend y backend) --------------------------
    ("js", "default"): "import todo from './a.js';\n",
    ("js", "namespace"): "import * as todo from './a.js';\n",
    ("js", "efecto-lateral"): "import './a.js';\n",
    ("js", "commonjs"): "const { suma } = require('./a.js');\n",
    ("js", "dinamico"): "const p = import('./a.js');\n",
    # el barril: el patron mas comun de frontend para reexportar una carpeta
    ("js", "barril-estrella"): "export * from './a.js';\n",
    ("js", "barril-nombrado"): "export { suma } from './a.js';\n",
    # --- TypeScript: lo suyo propio --------------------------------------
    ("ts", "solo-tipo"): "import type { suma } from './a';\n",
    ("ts", "commonjs"): "const { suma } = require('./a');\n",
    ("tsx", "default"): "import todo from './a';\n",
    # --- Ruby: las dos comillas ya estaban; falta el require de ruta --------
    ("ruby", "relativo-simples"): "require_relative 'a'\ndef total(x)\n  suma(x, 1)\nend\n",
    ("ruby", "relativo-dobles"): 'require_relative "a"\ndef total(x)\n  suma(x, 1)\nend\n',
    ("ruby", "relativo-con-extension"): "require_relative 'a.rb'\ndef total(x)\n  suma(x, 1)\nend\n",
    # --- PHP: el espejo del bug de JS, aqui solo estaban las simples -------
    ("php", "require-once-simples"): "<?php\nrequire_once 'a.php';\nfunction total($x) { return suma($x, 1); }\n",
    ("php", "require-once-dobles"): '<?php\nrequire_once "a.php";\nfunction total($x) { return suma($x, 1); }\n',
    ("php", "include-dobles"): '<?php\ninclude "a.php";\nfunction total($x) { return suma($x, 1); }\n',
    ("php", "include-once"): "<?php\ninclude_once 'a.php';\nfunction total($x) { return suma($x, 1); }\n",
    ("php", "require-parentesis"): "<?php\nrequire('a.php');\nfunction total($x) { return suma($x, 1); }\n",
    # --- Lua: con y sin parentesis, ambas comillas ------------------------
    ("lua", "parentesis-dobles"): 'local a = require("a")\nfunction total(x) return suma(x, 1) end\n',
    ("lua", "parentesis-simples"): "local a = require('a')\nfunction total(x) return suma(x, 1) end\n",
    ("lua", "sin-parentesis-simples"): "local a = require 'a'\nfunction total(x) return suma(x, 1) end\n",
    ("lua", "sin-parentesis-dobles"): 'local a = require "a"\nfunction total(x) return suma(x, 1) end\n',
    # --- C: la cabecera del proyecto (los <> son del sistema, no del repo) --
    ("c", "include-comillas"): '#include "a.h"\nint total(int x) { return suma(x, 1); }\n',
}

#: Variantes que NO se exigen todavia, con su motivo. Vacio hoy: lo que
#: entra en la matriz entra para cumplirse. Si alguna resulta imposible con
#: la tecnica, se mueve aqui CON motivo y se declara en `carencias`.
PENDIENTES = {}


def _proyecto(tmp_path, lang, etiqueta):
    raiz = os.path.join(str(tmp_path), "var_%s_%s" % (lang, etiqueta))
    os.makedirs(raiz, exist_ok=True)
    destino_nombre, destino_fuente = DESTINO[lang]
    with open(os.path.join(raiz, destino_nombre), "w", encoding="utf-8") as fh:
        fh.write(destino_fuente)
    ext = EXT_IMPORTADOR.get(lang, destino_nombre.rsplit(".", 1)[1])
    with open(os.path.join(raiz, "b." + ext), "w", encoding="utf-8") as fh:
        fh.write(VARIANTES[(lang, etiqueta)])
    return raiz


@necesita_astgrep
@pytest.mark.parametrize("lang,etiqueta", sorted(VARIANTES))
def test_la_variante_deja_la_misma_arista(tmp_path, lang, etiqueta):
    """Misma dependencia, distinta sintaxis: misma arista."""
    if (lang, etiqueta) in PENDIENTES:
        pytest.skip(PENDIENTES[(lang, etiqueta)])
    raiz = _proyecto(tmp_path, lang, etiqueta)
    aristas = {(e[0], e[1]) for e in lenguajes.analyze(raiz)["edges"]
               if e[2] == "IMPORTS"}
    assert ("b", "a") in aristas, (
        "%s/%s no deja arista; sale %s" % (lang, etiqueta, aristas or "ninguna"))


def test_las_pendientes_llevan_motivo():
    """Una variante fuera de la matriz sin motivo escrito es cobertura
    fingida — el mismo criterio que `carencias` en la tabla."""
    for clave, motivo in PENDIENTES.items():
        assert motivo and len(motivo) > 20, "%s sin motivo escrito" % (clave,)
