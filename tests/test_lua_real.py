"""Lua: el require nombra la ruta ENTERA, y las funciones se escriben como valor.

Medido sobre busted el 24-sep-2026 (banco de repos reales): `require 'pl.utils'`
caia en `busted/utils.lua` y `cliargs.core` en `busted/core.lua` (el sufijo
generico casaba un trozo del nombre), un `require('x.' .. v)` caia en `x`, cada
`function M.x()` salia dos veces (una con qual inventado) y `M.x = function` o el
campo de la tabla devuelta no eran simbolos.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)


def _escribe(raiz, rel, texto):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(texto)


def _informe(raiz):
    rep = lenguajes.analyze(str(raiz))
    imports = {(o, d) for o, d, t in rep["edges"] if t == "IMPORTS"}
    return rep, imports


def test_require_externo_no_cae_en_un_modulo_propio(tmp_path):
    _escribe(tmp_path, "app/utils.lua", "return {}\n")
    _escribe(tmp_path, "app/core.lua", "return {}\n")
    _escribe(tmp_path, "app/uno.lua",
             "local u = require 'pl.utils'\nlocal c = require 'cliargs.core'\n"
             "local x = require('app.' .. nombre)\nlocal s = require 'string'\n")
    _, imports = _informe(tmp_path)
    assert not {d for o, d in imports if o == "app.uno"}


def test_require_interno_por_ruta_init_y_rockspec(tmp_path):
    _escribe(tmp_path, "app/utils.lua", "return {}\n")
    _escribe(tmp_path, "app/sub/init.lua", "return {}\n")
    _escribe(tmp_path, "lib/raro.lua", "return {}\n")
    _escribe(tmp_path, "app-1.0-1.rockspec",
             "build = { modules = { ['app.renombrado'] = 'lib/raro.lua' } }\n")
    _escribe(tmp_path, "app/uno.lua",
             "local u = require 'app.utils'\nlocal s = require 'app.sub'\n"
             "local r = require 'app.renombrado'\n")
    _, imports = _informe(tmp_path)
    assert {("app.uno", "app.utils"), ("app.uno", "app.sub.init"),
            ("app.uno", "lib.raro")} <= imports


def test_funciones_como_valor_y_sin_duplicados(tmp_path):
    _escribe(tmp_path, "m.lua",
             "local M = {}\nfunction M.punto() end\nfunction M:dos() end\n"
             "M.asignada = function(x) return x end\n"
             "local suelta = function() end\n"
             "return { campo = function() return M.punto() end }\n")
    rep, _ = _informe(tmp_path)
    quals = [n["qual"] for n in rep["nodes"] if n["kind"] != "module"]
    assert {"m.punto", "m.dos", "m.asignada", "m.suelta", "m.campo"} <= set(quals)
    assert not [q for q in quals if q.startswith("m.M.")], quals
    assert ["m.campo", "m.punto", "CALLS"] in rep["edges"]
