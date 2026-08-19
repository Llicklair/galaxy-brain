"""Cuándo pararte a ponerte al día — la parte accionable de la película.

Con cuatro agentes a la vez el problema no es verlos, es saber cuándo sincronizar.
Por reloj («cada 10 minutos») se desperdicia trabajo cuando nadie te toca nada, y
se llega tarde cuando sí. Aquí la respuesta la da el grafo: hay deuda solo si lo
que el otro cambió es tu nodo o un vecino tuyo.

Sigue sin orquestar nada (ADR 0006): esto dice el hecho, no da la orden.
"""

import subprocess

import pytest
from test_cronologia import _git, _git_fechado, _modulo, _trabaja  # noqa: F401

from galaxybrain import actividad, cli, symbols


@pytest.fixture
def cadena(tmp_path):
    """Cuatro módulos en cadena: d → c → b → a."""
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
    _git_fechado(root, 7200, "commit", "-qm", "base")
    return root


def _agente(repo, nombre):
    ruta = repo.parent / nombre
    _git(repo, "worktree", "add", "-q", "--detach", str(ruta), "HEAD")
    return ruta


@pytest.fixture
def cuatro(cadena):
    arboles = {}
    for nombre, modulo, hace in (("uno", "a", 40), ("dos", "b", 30),
                                 ("tres", "c", 20), ("cuatro", "d", 10)):
        arbol = _agente(cadena, nombre)
        _trabaja(arbol, modulo, hace, "\n# %s\n" % nombre)
        arboles[nombre] = arbol
    return cadena, arboles


def _deuda(raiz, arbol):
    return actividad.deuda(str(raiz), symbols.analyze(str(raiz)), arbol=str(arbol))


def test_lo_que_otro_toco_y_tu_no_tienes_es_deuda(cuatro):
    raiz, arboles = cuatro
    d = _deuda(raiz, arboles["dos"])

    assert d["mio"] == ["lib.b"]
    assert [x["agente"] for x in d["deuda"]] == ["uno", "tres"] or \
           sorted(x["agente"] for x in d["deuda"]) == ["tres", "uno"]


def test_solo_cuenta_lo_que_toca_lo_tuyo(cuatro):
    """`cuatro` trabaja en `lib.d`, que solo cuelga de `lib.c`. Lo que hicieran
    `uno` o `dos` no le cambia el suelo, y avisarle seria ruido — un aviso que
    no exige nada se acaba ignorando, incluidos los que si importan."""
    raiz, arboles = cuatro
    d = _deuda(raiz, arboles["cuatro"])

    assert [x["agente"] for x in d["deuda"]] == ["tres"]


def test_lo_que_ya_tienes_deja_de_ser_deuda(cuatro):
    raiz, arboles = cuatro
    sha = subprocess.run(["git", "log", "-1", "--format=%h"], cwd=str(arboles["uno"]),
                         capture_output=True, text=True, check=True).stdout.strip()
    antes = [x["id"] for x in _deuda(raiz, arboles["dos"])["deuda"]]
    assert sha in antes

    _git(arboles["dos"], "merge", "-q", "--no-edit", sha)

    despues = [x["id"] for x in _deuda(raiz, arboles["dos"])["deuda"]]
    assert sha not in despues


def test_integrar_no_acredita_el_trabajo_del_otro(cuatro):
    """El fallo que destapó la tirada real: tras mergear, el diff del merge
    contra su primer padre son los ficheros del OTRO. Sin filtrarlo, `dos`
    figuraba tocando `lib.a` —que nunca escribió— y a `uno` le aparecía una
    deuda «mismo-nodo» contra su propio trabajo."""
    raiz, arboles = cuatro
    sha = subprocess.run(["git", "log", "-1", "--format=%h"], cwd=str(arboles["uno"]),
                         capture_output=True, text=True, check=True).stdout.strip()
    _git(arboles["dos"], "merge", "-q", "--no-edit", sha)

    assert _deuda(raiz, arboles["dos"])["mio"] == ["lib.b"]
    assert all(x["clase"] != "mismo-nodo" for x in _deuda(raiz, arboles["uno"])["deuda"])


def test_el_mismo_nodo_va_primero(cadena):
    """Dos agentes escribiendo el MISMO módulo es un choque, y cuanto más tarde
    se mire más caro sale el merge. Va arriba, antes que los vecinos."""
    a = _agente(cadena, "uno")
    b = _agente(cadena, "dos")
    _trabaja(a, "b", 40, "\n# uno tambien anda en b\n")   # mismo nodo que dos
    c = _agente(cadena, "tres")
    _trabaja(c, "c", 30, "\n# tres\n")                    # vecino de b
    _trabaja(b, "b", 20, "\n# dos\n")

    d = _deuda(cadena, b)
    assert d["deuda"][0]["clase"] == "mismo-nodo"
    assert d["deuda"][0]["agente"] == "uno"


def test_lo_que_otro_tiene_sin_commitear_no_es_deuda(cuatro):
    """No hay nada que traerse todavía: avisar de ello seria una alarma sin
    accion posible, y esas son las que enseñan a ignorar el aviso."""
    raiz, arboles = cuatro
    sucio = arboles["uno"] / "lib" / "a.py"
    sucio.write_text(sucio.read_text(encoding="utf-8") + "\n# a medias\n",
                     encoding="utf-8")

    d = _deuda(raiz, arboles["dos"])
    assert all(x["id"] for x in d["deuda"]), "una edicion sin commitear entro como deuda"


def test_sin_tocar_nada_no_hay_deuda_y_lo_dice(cuatro):
    """Un árbol limpio no tiene suelo que se le mueva: se dice el motivo en vez
    de devolver una lista vacía, que se lee como «todo en orden»."""
    raiz, _ = cuatro
    quinto = _agente(raiz, "quinto")

    d = _deuda(raiz, quinto)
    assert d["deuda"] == []
    assert "no ha tocado ningun nodo" in d["motivo"]


def test_sin_repo_git_lo_dice(tmp_path):
    d = actividad.deuda(str(tmp_path), {"nodes": []})
    assert d["deuda"] == []
    assert "sin repositorio git" in d["motivo"]


def test_una_deuda_vieja_no_caduca(cadena):
    """La película es de esta sesión; la deuda no.

    Lo que otro commiteó hace tres horas y tú nunca te trajiste TE SIGUE
    FALTANDO. Acotar la deuda por reloj la haría envejecer hasta desaparecer, y
    una deuda que se calla sola es peor que no medirla: el silencio se lee como
    «no hay nada».
    """
    viejo = _agente(cadena, "viejo")
    _trabaja(viejo, "a", 10800, "\n# de hace tres horas\n")   # fuera de la ventana
    yo = _agente(cadena, "yo")
    _trabaja(yo, "b", 20, "\n# yo, ahora\n")

    d = _deuda(cadena, yo)
    assert [x["agente"] for x in d["deuda"]] == ["viejo"]
    assert d["deuda"][0]["hace_seg"] > 3600


def test_avisa_cuando_apoyarse_en_el_otro_cerraria_un_ciclo(cuatro):
    """El fallo que destapó la tirada real con cuatro agentes: tres integraron
    bien y el cuarto se cargó su propio árbol llamando al módulo que ya le
    llamaba a él. Traerse el código de otro es gratis; APOYARSE en él no
    siempre, y un ciclo de imports no avisa: revienta al arrancar.

    `uno` trabaja en `lib.a`, y `lib.b` —el de `dos`— ya la llama.
    """
    raiz, arboles = cuatro
    d = _deuda(raiz, arboles["uno"])

    porb = [x for x in d["deuda"] if "lib.b" in x["por"]]
    assert porb, "el andamio no produjo la deuda que se quiere juzgar"
    assert all(x["ciclo_si_llamas"] for x in porb)


def test_no_avisa_cuando_apoyarse_es_seguro(cuatro):
    """Y no al revés: `cuatro` cuelga de `lib.c`, así que llamar a lo de `tres`
    es justo la dirección que ya existe. Un aviso aquí sería el ruido que enseña
    a ignorar el aviso de verdad."""
    raiz, arboles = cuatro
    d = _deuda(raiz, arboles["cuatro"])

    assert d["deuda"], "el andamio no produjo deuda que juzgar"
    assert all(not x["ciclo_si_llamas"] for x in d["deuda"])


def test_gb_sync_contesta_desde_el_worktree_del_agente(cuatro, capsys, monkeypatch):
    """De punta a punta: el agente lo ejecuta EN SU ÁRBOL y le habla de lo suyo."""
    _, arboles = cuatro
    monkeypatch.chdir(arboles["dos"])

    assert cli.main(["sync"]) == 0
    salida = capsys.readouterr().out
    assert "lib.b" in salida


def test_desde_su_arbol_el_agente_ve_su_suelo_aunque_lleve_horas(cadena, capsys, monkeypatch):
    """El fallo que solo aparecía ejecutándolo COMO lo ejecuta un agente.

    `rev-parse --show-toplevel` desde un worktree devuelve ESE worktree, no el
    repo principal. Con su propia cabeza como base, el rango salía `HEAD..HEAD`
    —vacío— y la única red que quedaba era la ventana de tiempo: a la hora,
    `gb sync` le contestaba «no has tocado nada» a un agente con tres commits
    encima, y se callaba una deuda que existía.

    Llamado con la raíz canónica (como en los demás tests) nunca fallaba. Por eso
    este test entra por el CLI y desde el árbol.
    """
    yo = _agente(cadena, "yo")
    _trabaja(yo, "b", 10800, "\n# mio, hace tres horas\n")
    otro = _agente(cadena, "otro")
    _trabaja(otro, "a", 9000, "\n# suyo, hace dos horas y media\n")
    monkeypatch.chdir(yo)

    assert cli.main(["sync"]) == 0
    salida = capsys.readouterr().out
    assert "lib.b" in salida, "no reconoce su propio suelo"
    assert "otro" in salida, "se calla una deuda vieja"


def test_gb_sync_nunca_gatea(cuatro, capsys, monkeypatch):
    """Sale 0 aunque haya choque. Salir != 0 seria convertir un hecho en una
    puerta y decidir por el orquestador — lo que la ADR 0006 dice que gb no
    hace — y repetiria el error ya documentado en `cmd_check`: gatear una señal
    enseña a saltársela."""
    cadena, arboles = cuatro
    otro = _agente(cadena, "quinto")
    _trabaja(otro, "b", 5, "\n# quinto tambien anda en b\n")   # choque con dos
    monkeypatch.chdir(arboles["dos"])

    assert cli.main(["sync"]) == 0
    assert "mismo-nodo" in capsys.readouterr().out


def test_check_avisa_de_la_deuda_sin_que_le_pregunten(cuatro, capsys, monkeypatch):
    """`gb sync` solo sirve si sabes que existe, y eso es el mismo agujero de
    siempre: un hecho que solo aparece si preguntas por él es un hecho que casi
    nadie ve. `check` es lo que un agente corre de verdad —lo llama hasta el
    pre-commit—, así que el aviso monta ahí."""
    _, arboles = cuatro
    monkeypatch.chdir(arboles["dos"])

    cli.main(["check"])
    assert "[gb sync]" in capsys.readouterr().out


def test_check_calla_cuando_trabajas_solo(cadena, capsys, monkeypatch):
    """Sin otro worktree no hay con quien chocar. Un aviso que sale siempre es
    el que se acaba ignorando, y ademas se ahorra analizar los simbolos."""
    monkeypatch.chdir(cadena)

    cli.main(["check"])
    assert "[gb sync]" not in capsys.readouterr().out


@pytest.fixture
def diamante(tmp_path):
    """Un grafo donde el ciclo NO se ve de un salto: m→n, p→q, q→m.

    Nadie forma ciclo todavía. Pero si `m` llamara a `p`, se cerraría
    m→p→q→m — y entre `p` y `m` no hay ninguna arista directa que lo delate.
    """
    root = tmp_path / "proyecto"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (root / "lib" / "n.py").write_text("def paso_n(x):\n    return x\n", encoding="utf-8")
    (root / "lib" / "m.py").write_text(
        "from lib.n import paso_n\n\n\ndef paso_m(x):\n    return paso_n(x)\n", encoding="utf-8")
    (root / "lib" / "q.py").write_text(
        "from lib.m import paso_m\n\n\ndef paso_q(x):\n    return paso_m(x)\n", encoding="utf-8")
    (root / "lib" / "p.py").write_text(
        "from lib.q import paso_q\n\n\ndef paso_p(x):\n    return paso_q(x)\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git_fechado(root, 7200, "commit", "-qm", "base")
    return root


def test_el_ciclo_que_no_se_ve_de_un_salto_tambien_avisa(diamante):
    """Un solo salto caza el ciclo corto y deja pasar el largo, que rompe igual.

    `yo` trabaja en `lib.m`. El otro hace UN commit que toca `lib.n` (vecino
    mío, y llamarlo es seguro: ya le llamo) y `lib.p`. De `p` a `m` no hay
    arista directa —el chequeo de un salto diría «adelante»— pero sí camino:
    p→q→m. Llamar a `p` desde `m` revienta al arrancar.

    Lo destapó un agente en la tirada del 19-ago-2026: se abstuvo razonando la
    cadena entera por su cuenta. El siguiente no tiene por qué darse cuenta.
    """
    yo = _agente(diamante, "yo")
    _trabaja(yo, "m", 40, "\n# mio\n")

    otro = _agente(diamante, "otro")
    for mod in ("n", "p"):
        ruta = otro / "lib" / ("%s.py" % mod)
        ruta.write_text(ruta.read_text(encoding="utf-8") + "\n# suyo\n", encoding="utf-8")
    _git(otro, "add", "-A")
    _git_fechado(otro, 20, "commit", "-qm", "n y p en el mismo commit")

    d = _deuda(diamante, yo)
    assert d["deuda"], "el andamio no produjo deuda que juzgar"
    assert d["deuda"][0]["ciclo_si_llamas"] is True
