"""Conformidad: cada lenguaje de la tabla extrae de verdad lo que promete.

Este fichero existe para que "soportamos N lenguajes" sea una afirmacion
VERIFICADA y no una lista de buenas intenciones. Un patron que deja de casar
—porque cambia ast-grep, porque cambia tree-sitter, porque estaba mal desde el
principio— tiene que salir aqui en rojo y no descubrirse cuando un usuario mire
un grafo vacio y crea que su proyecto no tiene simbolos.

Cada lenguaje aporta un fuente minimo con DOS funciones donde la segunda llama a
la primera. La prueba se deriva de la tabla, no de una lista paralela:

  - si el lenguaje declara patrones de simbolo -> tiene que salir algun simbolo
  - si declara patron de llamada             -> tiene que salir alguna arista CALLS
  - si declara `carencias`                   -> se comprueba que NO promete eso

Lo que un lenguaje no consigue va en `carencias` y se enseña al usuario. Es la
misma ley de la Fase 0 aplicada al catalogo: declarar el limite, nunca fingirlo.
"""

import os

import pytest

from galaxybrain import lenguajes

necesita_astgrep = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

#: lenguaje -> (nombre de fichero, fuente con `suma` y `total`, donde total llama a suma)
FUENTES = {
    "js": ("a.js", "export function suma(a, b) { return a + b; }\n"
                   "export function total(x) { return suma(x, 1); }\n"),
    "ts": ("a.ts", "export function suma(a: number, b: number): number { return a + b; }\n"
                   "export function total(x: number): number { return suma(x, 1); }\n"),
    "tsx": ("a.tsx", "export function suma(a: number, b: number) { return a + b; }\n"
                     "export function total(x: number) { return suma(x, 1); }\n"),
    "go": ("a.go", "package main\n\n"
                   "func Suma(a int, b int) int { return a + b }\n\n"
                   "func Total(x int) int { return Suma(x, 1) }\n"),
    "rust": ("a.rs", "pub fn suma(a: i32, b: i32) -> i32 { a + b }\n\n"
                     "pub fn total(x: i32) -> i32 { suma(x, 1) }\n"),
    "java": ("A.java", "public class A {\n"
                       "  public int suma(int a, int b) { return a + b; }\n"
                       "  public int total(int x) { return suma(x, 1); }\n}\n"),
    "kotlin": ("a.kt", "fun suma(a: Int, b: Int): Int { return a + b }\n\n"
                       "fun total(x: Int): Int { return suma(x, 1) }\n"),
    "swift": ("a.swift", "func suma(a: Int, b: Int) -> Int { return a + b }\n\n"
                         "func total(x: Int) -> Int { return suma(a: x, b: 1) }\n"),
    "ruby": ("a.rb", "def suma(a, b)\n  a + b\nend\n\n"
                     "def total(x)\n  suma(x, 1)\nend\n"),
    "php": ("a.php", "<?php\nfunction suma($a, $b) { return $a + $b; }\n\n"
                     "function total($x) { return suma($x, 1); }\n"),
    "lua": ("a.lua", "function suma(a, b) return a + b end\n\n"
                     "function total(x) return suma(x, 1) end\n"),
    "scala": ("a.scala", "def suma(a: Int, b: Int): Int = a + b\n\n"
                         "def total(x: Int): Int = suma(x, 1)\n"),
    "elixir": ("a.ex", "defmodule A do\n"
                       "  def suma(a, b), do: a + b\n"
                       "  def total(x), do: suma(x, 1)\nend\n"),
    "csharp": ("A.cs", "class A {\n"
                       "  public int suma(int a, int b) { return a + b; }\n"
                       "  public int total(int x) { return suma(x, 1); }\n}\n"),
    # En C la llamada va en SENTENCIA o en asignacion, que son las dos formas que
    # el motor ve; `return suma(x, 1);` anida la llamada dentro del return y no
    # deja arista — esta declarado en sus carencias.
    "c": ("a.c", "int suma(int a, int b) { return a + b; }\n\n"
                 "int total(int x) {\n    int r = suma(x, 1);\n    return r;\n}\n"),
    "dart": ("a.dart", "int suma(int a, int b) { return a + b; }\n\n"
                       "int total(int x) { return suma(x, 1); }\n"),
}


def _proyecto(tmp_path, lang):
    nombre, fuente = FUENTES[lang]
    root = str(tmp_path / lang)
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, nombre), "w", encoding="utf-8") as fh:
        fh.write(fuente)
    return root


def test_todos_los_lenguajes_de_la_tabla_tienen_sonda():
    """Sin esto, añadir un lenguaje a la tabla sin probarlo pasaria en verde —
    y el catalogo volveria a ser una lista de intenciones."""
    assert set(FUENTES) == set(lenguajes.LENGUAJES), (
        "cada entrada de LENGUAJES necesita un fuente de conformidad"
    )


@necesita_astgrep
@pytest.mark.parametrize("lang", sorted(FUENTES))
def test_extrae_simbolos_si_los_promete(tmp_path, lang):
    cfg = lenguajes.LENGUAJES[lang]
    informe = lenguajes.analyze(_proyecto(tmp_path, lang))
    simbolos = [n for n in informe["nodes"] if n["kind"] != "module"]

    if not cfg["simbolos"]:
        assert cfg["carencias"], "%s no extrae simbolos y no lo declara" % lang
        return
    assert simbolos, "%s promete patrones de simbolo y no extrajo ninguno" % lang
    # y con tramo real: sin `end` la seleccion de tests pierde el 100% del ahorro
    assert all(n["end"] for n in simbolos), "%s: simbolos sin linea final" % lang


@necesita_astgrep
@pytest.mark.parametrize("lang", sorted(FUENTES))
def test_resuelve_la_llamada_interna_si_la_promete(tmp_path, lang):
    """`total` llama a `suma` en el mismo fichero: es la arista mas facil que
    existe. Si un lenguaje no la saca, no tiene grafo de llamadas — y entonces
    `gb calls` y `gb tests` no le sirven, que es justo lo que hay que declarar."""
    cfg = lenguajes.LENGUAJES[lang]
    informe = lenguajes.analyze(_proyecto(tmp_path, lang))
    llamadas = [e for e in informe["edges"] if e[2] == "CALLS"]

    if not cfg["llamada"]:
        assert cfg["carencias"], "%s no extrae llamadas y no lo declara" % lang
        return
    if not cfg["simbolos"]:
        return                      # sin simbolos no hay destino que resolver
    assert llamadas, "%s promete llamadas y no resolvio ni la interna" % lang


@necesita_astgrep
@pytest.mark.parametrize("lang", sorted(FUENTES))
def test_lo_que_no_puede_se_dice_en_el_informe(tmp_path, lang):
    """Una carencia que no llega al usuario no sirve de nada: se comprueba que
    viaja en `not_covered`, que es lo que se imprime."""
    cfg = lenguajes.LENGUAJES[lang]
    if not cfg["carencias"]:
        return
    informe = lenguajes.analyze(_proyecto(tmp_path, lang))

    for texto in cfg["carencias"]:
        assert any(texto in linea for linea in informe["not_covered"]), texto


# --- el grafo de modulos, solo donde la resolucion es un hecho ---------------

#: Lenguajes cuyo import apunta a una RUTA, que es lo unico que se puede resolver
#: contra el disco sin adivinar. Los de paquete/namespace se casan por sufijo y
#: se prueban aparte.
RELATIVOS = {
    "js": ("a.js", "b.js", "export function suma(a, b) { return a + b; }\n",
           'import { suma } from "./a.js";\nexport function total(x) { return suma(x, 1); }\n'),
    "ruby": ("a.rb", "b.rb", "def suma(a, b)\n  a + b\nend\n",
             "require_relative 'a'\ndef total(x)\n  suma(x, 1)\nend\n"),
    "php": ("a.php", "b.php", "<?php\nfunction suma($a, $b) { return $a + $b; }\n",
            "<?php\nrequire_once 'a.php';\nfunction total($x) { return suma($x, 1); }\n"),
    "lua": ("a.lua", "b.lua", "function suma(a, b) return a + b end\n",
            'local a = require("a")\nfunction total(x) return suma(x, 1) end\n'),
}


@necesita_astgrep
@pytest.mark.parametrize("lang", sorted(RELATIVOS))
def test_la_arista_de_import_sale_donde_la_resolucion_es_un_hecho(tmp_path, lang):
    fa, fb, sa, sb = RELATIVOS[lang]
    root = str(tmp_path / ("imp_" + lang))
    os.makedirs(root, exist_ok=True)
    for nombre, fuente in ((fa, sa), (fb, sb)):
        with open(os.path.join(root, nombre), "w", encoding="utf-8") as fh:
            fh.write(fuente)

    aristas = {(e[0], e[1]) for e in lenguajes.analyze(root)["edges"] if e[2] == "IMPORTS"}

    assert ("b", "a") in aristas, "%s: %s" % (lang, aristas)


# --- la licencia para estrechar la seleccion de tests ------------------------


def test_la_licencia_para_estrechar_es_opt_in():
    """`tia` por defecto False. Un lenguaje nuevo NO puede estrechar el dia que
    entra en la tabla: primero su banco con rojos reales, despues la licencia."""
    from galaxybrain import lenguajes as tabla

    concedidas = {i for i, cfg in tabla.LENGUAJES.items() if cfg["tia"]}
    assert concedidas == {"js", "ts", "go", "csharp"}, (
        "solo tienen banco medido js/ts (node --test), go (go test) y csharp "
        "(dotnet test): 0 falsos verdes, cascada exacta y 52%% de ahorro en los tres. "
        "Concedidas ahora: %s" % sorted(concedidas)
    )


def test_sin_licencia_la_seleccion_corre_todo_y_lo_dice():
    """El contrato que evita el verde falso. Rust lo motivo: la llamada dentro de
    `format!("...", emitir(xs))` es invisible, y con ella se caia un test de los
    impactados — sin dar verde falso solo porque todos recorrian la cadena."""
    from galaxybrain import impacted

    assert impacted._sin_licencia_para_estrechar({"lenguajes": ["rust"]}) == "rust"
    assert impacted._sin_licencia_para_estrechar({"lenguajes": ["js"]}) == ""
    assert impacted._sin_licencia_para_estrechar({"lenguajes": ["js", "go"]}) == ""
    assert impacted._sin_licencia_para_estrechar({"lenguajes": ["csharp"]}) == ""
    assert impacted._sin_licencia_para_estrechar({"lenguajes": ["go", "java"]}) == "java"


def test_la_via_python_no_pasa_por_la_licencia():
    """El motor maduro tiene su propio banco (42/42) y su propia caida segura:
    su informe no declara `lenguajes` y no se toca."""
    from galaxybrain import impacted

    assert impacted._sin_licencia_para_estrechar({"nodes": [], "edges": []}) == ""


@necesita_astgrep
def test_resuelve_la_llamada_cualificada_entre_modulos(tmp_path):
    """`paquete.Funcion()` es la forma NORMAL de llamar fuera del modulo propio
    en Go, Java, C#, Kotlin y Scala. Descartarla dejaba su grafo de llamadas
    practicamente vacio: en el banco de Go, cero aristas entre paquetes.

    Se resuelve como los imports —casando contra simbolos que EXISTEN— y solo si
    hay exactamente uno. El control de abajo es la otra mitad: un prefijo que no
    es un modulo del proyecto (una variable) NO fabrica arista."""
    root = str(tmp_path / "go")
    os.makedirs(os.path.join(root, "iva"), exist_ok=True)
    os.makedirs(os.path.join(root, "carrito"), exist_ok=True)
    with open(os.path.join(root, "iva", "iva.go"), "w", encoding="utf-8") as fh:
        fh.write("package iva\n\nfunc Iva() float64 { return 0.21 }\n")
    with open(os.path.join(root, "carrito", "carrito.go"), "w", encoding="utf-8") as fh:
        fh.write('package carrito\n\nimport "bench/iva"\n\n'
                 "func Total(x float64) float64 { return x * iva.Iva() }\n")

    llamadas = {(e[0], e[1]) for e in lenguajes.analyze(root)["edges"] if e[2] == "CALLS"}

    assert ("carrito.carrito.Total", "iva.iva.Iva") in llamadas, llamadas


@necesita_astgrep
def test_un_prefijo_que_no_es_modulo_no_fabrica_arista(tmp_path):
    """`xs.reduce(...)` en JS: el prefijo es una VARIABLE, no un modulo. Sigue
    contando como techo, que es donde debe quedarse — una arista inventada es
    peor que una arista ausente (ADR 0008)."""
    root = str(tmp_path / "js")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "a.js"), "w", encoding="utf-8") as fh:
        fh.write("export function reduce(x) { return x; }\n"
                 "export function suma(xs) { return xs.reduce((a, b) => a + b, 0); }\n")

    informe = lenguajes.analyze(root)
    llamadas = {(e[0], e[1]) for e in informe["edges"] if e[2] == "CALLS"}

    assert ("a.suma", "a.reduce") not in llamadas, "resolvio un metodo de variable"
    assert informe["unresolved"].get("atributo-de-variable")


@necesita_astgrep
def test_un_import_de_terceros_no_fabrica_arista(tmp_path):
    """Un paquete externo no es codigo de este proyecto: su arista no diria nada
    del acoplamiento propio, y una arista falsa es peor que ninguna."""
    root = str(tmp_path / "ext")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "a.js"), "w", encoding="utf-8") as fh:
        fh.write('import React from "react";\nexport function x() { return 1; }\n')

    assert not [e for e in lenguajes.analyze(root)["edges"] if e[2] == "IMPORTS"]
