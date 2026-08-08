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
    "c": ("a.c", "int suma(int a, int b) { return a + b; }\n\n"
                 "int total(int x) { return suma(x, 1); }\n"),
    "cpp": ("a.cpp", "int suma(int a, int b) { return a + b; }\n\n"
                     "int total(int x) { return suma(x, 1); }\n"),
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


@necesita_astgrep
def test_un_import_de_terceros_no_fabrica_arista(tmp_path):
    """Un paquete externo no es codigo de este proyecto: su arista no diria nada
    del acoplamiento propio, y una arista falsa es peor que ninguna."""
    root = str(tmp_path / "ext")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "a.js"), "w", encoding="utf-8") as fh:
        fh.write('import React from "react";\nexport function x() { return 1; }\n')

    assert not [e for e in lenguajes.analyze(root)["edges"] if e[2] == "IMPORTS"]
