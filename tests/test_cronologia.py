"""La película, no la foto: en qué orden trabajó cada agente y a quién llegó.

`instantanea` contesta «¿quién está tocando esto AHORA?». Con cuatro agentes a
la vez esa respuesta se queda corta: la pregunta útil es en qué MOMENTO tocó
cada uno y cómo se propagó lo que hizo por el grafo hasta el trabajo de otro.

Aquí se prueba con cuatro, y encadenados a propósito (a ← b ← c ← d), porque una
cadena es lo único que distingue «se propagó» de «coincidieron»: si el orden no
importara, los cuatro pares saldrían iguales.

Nadie declara nada, igual que en el resto del módulo: los eventos salen de los
commits de cada worktree y de los mtime de lo que aún no está commiteado.
"""

import os
import subprocess
import time

import pytest

from galaxybrain import actividad, symbols


def _git(root, *args):
    subprocess.run(["git"] + list(args), cwd=str(root), check=True,
                   capture_output=True, text=True)


def _git_fechado(root, hace_seg, *args):
    """Un commit con fecha explícita: la del hecho, no la del reloj del test.

    En EPOCH y no en prosa, por lo mismo que en `test_actividad`: un
    `GIT_COMMITTER_DATE="2 hours ago"` depende de qué formato entienda cada git.
    """
    sello = "@%d +0000" % int(time.time() - hace_seg)
    entorno = dict(os.environ, GIT_COMMITTER_DATE=sello, GIT_AUTHOR_DATE=sello)
    subprocess.run(["git"] + list(args), cwd=str(root), check=True,
                   capture_output=True, text=True, env=entorno)


def _modulo(root, nombre, importa=None):
    """Un módulo que LLAMA al de al lado.

    Los nombres van con apellido (`paso_a`, `paso_b`) y no todos `paso`: con el
    mismo nombre, la función local tapa a la importada y el analizador resuelve
    la llamada dentro del propio módulo — cero aristas y cero propagación. Costó
    dos tests en rojo que no eran del código, sino del andamio.
    """
    if importa:
        cuerpo = ("from lib.%s import paso_%s\n\n\ndef paso_%s(x):\n    return paso_%s(x)\n"
                  % (importa, importa, nombre, importa))
    else:
        cuerpo = "def paso_%s(x):\n    return x\n" % nombre
    (root / "lib" / ("%s.py" % nombre)).write_text(cuerpo, encoding="utf-8")


@pytest.fixture
def cadena(tmp_path):
    """Cuatro módulos en cadena: d → c → b → a. Un repo, base en el pasado."""
    root = tmp_path / "proyecto"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    _modulo(root, "a")
    _modulo(root, "b", importa="a")
    _modulo(root, "c", importa="b")
    _modulo(root, "d", importa="c")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    # En el pasado: montar el andamio no es trabajo en curso, y con fecha de
    # ahora el árbol raíz saldría como un quinto agente en cada test.
    _git_fechado(root, 7200, "commit", "-qm", "base")
    return root


def _agente(repo, nombre):
    ruta = repo.parent / nombre
    _git(repo, "worktree", "add", "-q", "--detach", str(ruta), "HEAD")
    return ruta


def _trabaja(arbol, modulo, hace_seg, texto):
    """Ese agente edita su módulo y lo commitea, fechado."""
    ruta = arbol / "lib" / ("%s.py" % modulo)
    ruta.write_text(ruta.read_text(encoding="utf-8") + texto, encoding="utf-8")
    _git(arbol, "add", "-A")
    _git_fechado(arbol, hace_seg, "commit", "-qm", "cambio en %s" % modulo)


@pytest.fixture
def cuatro(cadena):
    """Cuatro agentes trabajando a la vez, en este orden: a, b, c, d.

    Las horas van decreciendo (hace 40 s, 30, 20, 10) porque lo que se prueba es
    la SECUENCIA: quien tocó `a` lo hizo antes que quien tocó `b`, que lo importa.
    """
    arboles = {}
    for nombre, modulo, hace in (("uno", "a", 40), ("dos", "b", 30),
                                 ("tres", "c", 20), ("cuatro", "d", 10)):
        arbol = _agente(cadena, nombre)
        _trabaja(arbol, modulo, hace, "\n# %s\n" % nombre)
        arboles[nombre] = arbol
    return cadena, arboles


def test_sin_repo_git_lo_dice_y_no_inventa(tmp_path):
    pelicula = actividad.cronologia(str(tmp_path), {"nodes": []})
    assert pelicula["eventos"] == []
    assert "sin repositorio git" in pelicula["motivo"]


def test_los_cuatro_agentes_salen_en_el_orden_en_que_trabajaron(cuatro):
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    orden = [e["agente"] for e in pelicula["eventos"] if e["tipo"] == "commit"]
    assert orden == ["uno", "dos", "tres", "cuatro"]


def test_cada_evento_dice_que_nodo_toco_y_con_que_commit(cuatro):
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    porcion = {e["agente"]: e for e in pelicula["eventos"] if e["tipo"] == "commit"}
    assert porcion["uno"]["nodos"] == ["lib.a"]
    assert porcion["cuatro"]["nodos"] == ["lib.d"]
    # El id es lo que hace verificable el evento: sin él, «commit» es una palabra.
    assert all(e["id"] for e in porcion.values())


def test_la_informacion_se_propaga_por_la_cadena_y_en_un_solo_sentido(cuatro):
    """Lo que distingue esta capa de un simple log: cruzar la arista con el reloj.

    `uno` cambió `lib.a`; `dos` tocó después `lib.b`, que lo importa. Eso es
    propagación. Al revés no: `dos` trabajó DESPUÉS, así que no pudo llegarle
    nada suyo a `uno`.
    """
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    pares = {(p["de"], p["a"]) for p in pelicula["propagaciones"]}
    assert ("uno", "dos") in pares
    assert ("dos", "uno") not in pares


def test_la_propagacion_dice_por_donde_paso_y_cuanto_tardo(cuatro):
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    salto = next(p for p in pelicula["propagaciones"]
                 if (p["de"], p["a"]) == ("uno", "dos"))
    assert salto["por"] == "lib.b"          # el nodo por el que llegó
    assert salto["desde"] == ["lib.a"]      # lo que había cambiado el primero
    assert salto["seg"] > 0                 # y el reloj, que es la mitad del dato


def test_nadie_se_propaga_a_si_mismo(cuatro):
    """Un agente que toca dos módulos encadenados no se está comunicando con
    nadie: contarlo llenaría el mapa de conversaciones de uno solo."""
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    assert all(p["de"] != p["a"] for p in pelicula["propagaciones"])


def test_lo_editado_sin_commitear_entra_marcado_como_edicion(cuatro):
    """Un guardado no es un hito: se ve, pero se etiqueta distinto para que
    nadie lo lea como trabajo cerrado."""
    raiz, arboles = cuatro
    sucio = arboles["uno"] / "lib" / "a.py"
    sucio.write_text(sucio.read_text(encoding="utf-8") + "\n# sin commitear\n",
                     encoding="utf-8")

    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    ediciones = [e for e in pelicula["eventos"] if e["tipo"] == "edicion"]
    assert ediciones, "la edición sin commitear no aparece"
    assert ediciones[0]["nodos"] == ["lib.a"]
    assert ediciones[0]["id"] == ""   # no hay commit que citar, y no se inventa


def test_el_tope_recorta_por_lo_viejo_y_lo_dice(cuatro):
    """Un tope silencioso se lee como «esto es todo lo que pasó»."""
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe, tope=2)

    assert len(pelicula["eventos"]) == 2
    assert "fuera del tope" in pelicula["motivo"]
    # Se queda lo RECIENTE: recortar por el otro lado escondería lo que pasa ahora.
    assert [e["agente"] for e in pelicula["eventos"]] == ["tres", "cuatro"]


def test_tocar_cosas_vecinas_a_la_vez_NO_es_comunicacion(cuatro):
    """Lo que separa «se propagó» de «coincidieron», y sin esto la capa mentiría
    con cara de hecho.

    Los cuatro worktrees cuelgan de la misma base y ninguno ha visto al otro:
    aunque tocaron nodos vecinos en orden, no le llegó nada a nadie. Eso no es
    comunicación — es RIESGO DE CHOQUE, que es justo lo contrario, y llamarlo
    propagación sería vender una conversación que no existió.
    """
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    assert pelicula["propagaciones"], "el andamio no produjo saltos que juzgar"
    assert all(p["heredado"] is False for p in pelicula["propagaciones"])


def test_si_el_segundo_SI_tiene_el_commit_del_primero_la_informacion_llego(cuatro):
    """El caso positivo: `dos` se pone al día con `uno` y luego trabaja. Ahora sí
    pudo llegarle lo del otro, y el dato lo dice."""
    raiz, arboles = cuatro
    sha = subprocess.run(["git", "log", "-1", "--format=%h"], cwd=str(arboles["uno"]),
                         capture_output=True, text=True, check=True).stdout.strip()
    _git(arboles["dos"], "merge", "-q", "--no-edit", sha)
    _trabaja(arboles["dos"], "b", 5, "\n# despues de ponerme al dia\n")

    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    salto = next(p for p in pelicula["propagaciones"]
                 if (p["de"], p["a"]) == ("uno", "dos"))
    assert salto["heredado"] is True


def test_el_commit_de_otro_no_se_atribuye_a_quien_lo_mergea(cuatro):
    """Salió en la tirada real de cuatro agentes: en cuanto `dos` se puso al día,
    el commit de `uno` reaparecía como evento SUYO y la película enseñaba a
    alguien trabajando donde nunca estuvo. Se mira la línea de primeros padres:
    lo que ESTE árbol hizo, no lo que se trajo."""
    raiz, arboles = cuatro
    sha = subprocess.run(["git", "log", "-1", "--format=%h"], cwd=str(arboles["uno"]),
                         capture_output=True, text=True, check=True).stdout.strip()
    _git(arboles["dos"], "merge", "-q", "--no-edit", sha)

    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe)

    duenos = {e["agente"] for e in pelicula["eventos"] if e["id"] == sha}
    assert duenos == {"uno"}, "el commit de uno aparece como de %s" % sorted(duenos)


def test_la_ventana_deja_fuera_lo_viejo(cuatro):
    """La película es de esta sesión. Sin ventana, el repo entero es la película
    y deja de contestar «qué está pasando»."""
    raiz, _ = cuatro
    informe = symbols.analyze(str(raiz))
    pelicula = actividad.cronologia(str(raiz), informe, ventana=15)

    assert [e["agente"] for e in pelicula["eventos"]] == ["cuatro"]
