"""C sobre las formas de una libreria REAL, no las del fixture de conformidad.

Salio del banco de repos reales (libyaml, 24-sep-2026): con la suite en verde,
gb veia 90 funciones de 228 y la maquina de estados entera no tenia llamantes.
Dos causas, las dos de la TABLA de C:

  - el simbolo era el patron `$RET $NAME($$$) { $$$ }`, que solo casa un tipo
    de retorno de UN nodo: `static int f(...)`, `char *f(...)` y la definicion
    K&R no eran simbolos — y en una libreria C casi todo lo interno es static;
  - la llamada solo se veia en sentencia (`f(x);`) o en asignacion, y C
    encadena con `return f(x);` e `if (!f(x))`.

Y lo que ya estaba bien queda como regresion: `#include <list.h>` es del
sistema aunque exista un `list.h` propio.
"""


import pytest
from test_conformidad_lenguajes import necesita_astgrep

from galaxybrain import lenguajes

UTIL_H = """#ifndef UTIL_H
#define UTIL_H
int publica(int x);
#endif
"""

UTIL_C = """#include "util.h"

static int
interna(int a)
{
    return a + 1;
}

int publica(int x)
{
    if (!interna(x))
        return 0;
    return interna(x) * 2;
}
"""

LIST_H = "int longitud(void);\n"

MAIN_C = """#include <stdio.h>
#include <list.h>
#include "util.h"

char *
nombre(void)
{
    return 0;
}

int kr(a, b)
    int a;
    int b;
{
    return a - b;
}

inline static unsigned long larga(void) { return 1; }

int main(void)
{
    return publica(kr(1, 2)) + (nombre() != 0) + (int) larga();
}
"""


def _repo(tmp_path):
    root = tmp_path / "libc"
    (root / "src").mkdir(parents=True)
    (root / "src" / "util.h").write_text(UTIL_H, encoding="utf-8")
    (root / "src" / "util.c").write_text(UTIL_C, encoding="utf-8")
    (root / "src" / "list.h").write_text(LIST_H, encoding="utf-8")
    (root / "src" / "main.c").write_text(MAIN_C, encoding="utf-8")
    return str(root)


@pytest.fixture
def informe(tmp_path):
    return lenguajes.analyze(_repo(tmp_path))


@necesita_astgrep
def test_static_puntero_kr_e_inline_son_simbolos(informe):
    quals = {n["qual"] for n in informe["nodes"] if n["kind"] == "function"}
    assert {"util.interna", "util.publica", "main.nombre", "main.kr",
            "main.larga", "main.main"} <= quals


@necesita_astgrep
def test_el_simbolo_static_cubre_su_cuerpo_entero(informe):
    interna = next(n for n in informe["nodes"] if n["qual"] == "util.interna")
    assert (interna["line"], interna["end"]) == (3, 7)


@necesita_astgrep
def test_la_llamada_en_return_y_en_if_deja_arista(informe):
    llamadas = {(o, d) for o, d, t in informe["edges"] if t == "CALLS"}
    assert ("util.publica", "util.interna") in llamadas          # if (!f(x)) / return f(x)
    assert ("main.main", "util.publica") in llamadas              # declarada en .h, definida en .c
    assert ("main.main", "main.kr") in llamadas                   # anidada: f(g(x))
    assert ("main.main", "main.nombre") in llamadas


@necesita_astgrep
def test_include_de_sistema_no_cae_en_la_cabecera_propia(informe):
    aristas = {(o, d) for o, d, t in informe["edges"] if t == "IMPORTS"}
    assert ("main", "util") in aristas                            # "util.h", local
    assert ("main", "list") not in aristas                        # <list.h>, del sistema
    assert ("util", "util") not in aristas                        # util.c + util.h: un modulo
