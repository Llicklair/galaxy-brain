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
    "dart": ("a.dart", "int suma(int a, int b) => a + b;\n"),
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
    # --- Dart: solo casaba el import desnudo con simples ------------------
    # (petitparser, 24-sep-2026: 147 de 646 aristas perdidas)
    ("dart", "simples"): "import 'a.dart';\n",
    ("dart", "dobles"): 'import "a.dart";\n',
    ("dart", "con-alias"): "import 'a.dart' as a;\n",
    ("dart", "show"): "import 'a.dart' show suma;\n",
    ("dart", "barril-export"): "export 'a.dart';\n",
    ("dart", "part"): "part 'a.dart';\n",
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


@necesita_astgrep
def test_el_gate_bloquea_en_un_repo_que_no_es_python(tmp_path):
    """El gate no estaba sin construir: estaba MUDO. El constructor
    multilenguaje llevaba cableado desde el ADR 0009, pero sin aristas de
    import no habia ciclos que encontrar ni fronteras que cruzar, asi que
    `gb graph --gate` pasaba en verde sobre cualquier repo JS sin comprobar
    nada — el falso verde que la regla 9 persigue. Con los patrones curados
    el ciclo sale y el cruce declarado tambien; esto lo fija como contrato."""
    from galaxybrain import graph

    raiz = os.path.join(str(tmp_path), "app")
    os.makedirs(os.path.join(raiz, "nucleo"))
    os.makedirs(os.path.join(raiz, "ui"))
    with open(os.path.join(raiz, "nucleo", "motor.js"), "w", encoding="utf-8") as fh:
        fh.write("import { pinta } from '../ui/vista.js';\n"
                 "export function calcula(x) { return pinta(x); }\n")
    with open(os.path.join(raiz, "ui", "vista.js"), "w", encoding="utf-8") as fh:
        fh.write("import { calcula } from '../nucleo/motor.js';\n"
                 "export function pinta(x) { return calcula(x) + 1; }\n")
    with open(os.path.join(raiz, ".gb-boundaries"), "w", encoding="utf-8") as fh:
        fh.write("NUCLEO = nucleo.motor\nUI = ui.vista\n\nNUCLEO -/-> UI\n")

    # El mismo motor que elige la CLI para un repo sin Python.
    informe = graph.analyze(raiz, constructor=lenguajes.build_graph)

    assert informe["modules"] == 2, informe["modules"]
    assert informe["cycles"], "el ciclo de imports de JS no se ve"
    assert informe["violations"], "el cruce de frontera declarado no se ve"


@necesita_astgrep
def test_rust_un_crate_externo_no_cae_en_un_modulo_propio(tmp_path):
    """tach, 24-sep-2026: `use globset::Glob` casaba (sin mayusculas, por
    sufijo) con `resolvers/glob.rs` y fabricaba un ciclo que el gate bloquearia;
    `std::sync` y `once_cell::sync` caian en `commands/sync.rs`. En Rust el
    primer segmento decide: crate/self/super o un modulo de primer nivel del
    crate es interno; lo demas es un crate externo."""
    raiz = os.path.join(str(tmp_path), "crate")
    ficheros = {
        "src/lib.rs": "mod config;\nmod resolvers;\nmod commands;\nuse config::Ajustes;\n",
        "src/config.rs": "pub struct Ajustes { pub x: i32 }\n",
        "src/resolvers/mod.rs": "pub mod glob;\n",
        "src/resolvers/glob.rs": "use crate::config::Ajustes;\npub fn casa() {}\n",
        "src/commands/mod.rs": "pub mod sync;\n",
        "src/commands/sync.rs": "use super::super::config::Ajustes;\npub fn sincroniza() {}\n",
        "src/walker.rs": ("use globset::Glob;\nuse glob::Pattern;\nuse std::sync::Arc;\n"
                          "use once_cell::sync::Lazy;\nuse crate::config::Ajustes;\npub fn anda() {}\n"),
    }
    for rel, fuente in ficheros.items():
        ruta = os.path.join(raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(fuente)
    aristas = {(e[0], e[1]) for e in lenguajes.analyze(raiz)["edges"] if e[2] == "IMPORTS"}
    desde_walker = {d for o, d in aristas if o.endswith("walker")}

    assert not any(d.endswith(("glob", "sync")) for d in desde_walker), desde_walker
    assert any(d.endswith("config") for d in desde_walker), "se perdio `use crate::config`"
    assert any(o.endswith("lib") and d.endswith("config") for o, d in aristas), \
        "se perdio `use config::X` desde la raiz del crate"
    assert any(o.endswith("glob") and d.endswith("config") for o, d in aristas), aristas


@necesita_astgrep
def test_java_un_import_externo_no_cae_en_una_clase_propia(tmp_path):
    """Banco de repos reales, 24-sep-2026. Un import de Java es un nombre
    cualificado ENTERO, y los atajos por sufijo lo casaban con clases propias:
    `java.util.List` -> `Util.java` (javapoet, 17 de 32 aristas falsas),
    `org.w3c.dom.Element` -> `nodes/Element.java` y `java.util.regex.Pattern`
    -> `helper/Regex.java` (jsoup). Y la otra mitad: `import static` y
    `import pkg.*` no casaban con ningun patron y su dependencia se perdia."""
    raiz = os.path.join(str(tmp_path), "jv")
    ficheros = {
        "src/com/app/Util.java": "package com.app;\npublic class Util { static void f() { } }\n",
        "src/com/app/nodes/Element.java": "package com.app.nodes;\npublic class Element { }\n",
        "src/com/app/helper/Regex.java": "package com.app.helper;\npublic class Regex { }\n",
        "src/com/app/W3C.java": ("package com.app;\nimport java.util.List;\n"
                                 "import org.w3c.dom.Element;\nimport java.util.regex.Pattern;\n"
                                 "public class W3C { }\n"),
        "src/com/app/Usa.java": ("package com.app;\nimport static com.app.Util.f;\n"
                                 "import com.app.nodes.*;\npublic class Usa { }\n"),
    }
    for rel, fuente in ficheros.items():
        ruta = os.path.join(raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(fuente)
    aristas = {(e[0], e[1]) for e in lenguajes.analyze(raiz)["edges"] if e[2] == "IMPORTS"}

    assert not [d for o, d in aristas if o.endswith("W3C")], aristas
    assert any(o.endswith("Usa") and d.endswith("app.Util") for o, d in aristas), \
        "se perdio `import static`: %s" % aristas
    assert any(o.endswith("Usa") and d.endswith("nodes.Element") for o, d in aristas), \
        "se perdio `import pkg.*` de un paquete de un solo modulo: %s" % aristas


@necesita_astgrep
def test_java_ve_los_metodos_y_tipos_de_cualquier_forma(tmp_path):
    """javapoet: 225 de 816 metodos y 56 de 87 tipos no eran simbolos porque
    el patron exigia una forma. Por KIND salen todos los que tienen cuerpo."""
    raiz = os.path.join(str(tmp_path), "formas")
    os.makedirs(raiz)
    with open(os.path.join(raiz, "P.java"), "w", encoding="utf-8") as fh:
        fh.write("package p;\npublic final class P extends Object implements Runnable {\n"
                 "  void sinMod() { }\n"
                 "  public void conThrows() throws Exception { }\n"
                 "  static <T> T generico(T t) { return t; }\n"
                 "  public void run() { }\n"
                 "  static class Anidada { }\n"
                 "  private enum Tipo { A }\n"
                 "  interface Iface { void abstracto(); default void pordefecto() { } }\n"
                 "}\n")
    quals = {n["qual"] for n in lenguajes.analyze(raiz)["nodes"]}
    for nombre in ("P", "sinMod", "conThrows", "generico", "run", "Anidada", "Tipo",
                   "Iface", "pordefecto"):
        assert "P." + nombre in quals, (nombre, sorted(quals))
    assert "P.abstracto" not in quals, "un metodo sin cuerpo no tiene codigo que llamar"
