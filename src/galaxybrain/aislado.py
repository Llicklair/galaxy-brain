"""Correr la verificación sobre un árbol limpio, no sobre el tuyo.

El verde que alguien reporta desde su copia de trabajo no es evidencia sobre el
cambio: es evidencia sobre su copia de trabajo. Un fichero que nunca se añadió,
una variable de entorno puesta a mano, un arreglo hecho fuera del diff — todo eso
sostiene un «pasan los tests» que no sobrevive al viaje.

Medido el 5-ago-2026 con tres agentes en paralelo: uno reportó «449 passed» de
buena fe y su diff, aplicado solo sobre base limpia, salía ROJO. Su método de
verificación vivía fuera del artefacto. Otro agente, sin saberlo, arregló el mismo
problema en un fichero compartido y rescató el verde del primero por accidente.

Aquí se monta un árbol desechable en `HEAD`, se le aplica encima el mismo diff que
se está midiendo, y se corre ahí. Lo que no viaja en el diff, no viaja — y se dice
cuánto se quedó fuera en vez de callarlo.

**Aísla el ÁRBOL, no el ENTORNO.** El proceso hereda tu `PATH`, tu `PYTHONPATH`, tu
venv y cualquier `.pth` instalado. Aislar también el entorno exigiría decidir qué es
«limpio» para cada stack, y eso es adivinar (regla 6: nada project-specific). Si tu
verde depende del entorno, esto no lo caza; caza lo que depende del árbol.
"""

import os
import shutil
import subprocess
import sys
import tempfile


def _entorno_sin_git():
    """El entorno del proceso, sin las variables que git inyecta en sus hooks.

    Si `gb tests --isolated` corre DENTRO de un hook (y el pre-commit de este
    repo lo hace posible), el GIT_INDEX_FILE/GIT_DIR heredado haria que los
    arboles desechables operasen sobre el repo del usuario: un `git apply` del
    checkpoint escribiendo en el indice real. Aqui todo git va con el entorno
    limpio; el repo objetivo lo dice `cwd`, no una variable heredada.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(cwd, *args, entrada=None):
    """git en bytes, nunca en texto.

    `subprocess(text=True)` decodifica con la codificación local — cp1252 en
    Windows — y corrompe los acentos de un diff hasta que `git apply` rechaza un
    parche perfectamente válido. Los parches se manejan crudos.
    """
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                           input=entrada, env=_entorno_sin_git())
    except OSError as error:
        return 1, b"", str(error).encode("utf-8", "replace")
    return r.returncode, r.stdout, r.stderr


def _texto(crudo):
    return crudo.decode("utf-8", errors="replace").strip()


def _raiz_git(root):
    rc, salida, _ = _git(root, "rev-parse", "--show-toplevel")
    if rc != 0:
        return None
    return os.path.abspath(_texto(salida))


def _sin_trackear(root):
    rc, salida, _ = _git(root, "status", "--porcelain")
    if rc != 0:
        return []
    fuera = []
    for linea in _texto(salida).splitlines():
        if linea.startswith("??"):
            fuera.append(linea[3:].strip().strip('"'))
    return sorted(fuera)


def _worktrees(root):
    """Los worktrees registrados: (ruta, HEAD). Incluye el principal."""
    rc, salida, _ = _git(root, "worktree", "list", "--porcelain")
    if rc != 0:
        return []
    fuera, ruta = [], None
    for linea in _texto(salida).splitlines():
        if linea.startswith("worktree "):
            ruta = linea[len("worktree "):].strip()
        elif linea.startswith("HEAD ") and ruta:
            fuera.append((os.path.abspath(ruta), linea[len("HEAD "):].strip()))
            ruta = None
    return fuera


RUIDO = ("__pycache__", ".git", ".venv", "node_modules", ".pytest_cache")


def _tiene_cambios(ruta):
    """Si esta rama tiene trabajo que mirar.

    No basta con el diff de lo trackeado: una rama cuyo trabajo entero son ficheros
    NUEVOS —lo mas comun cuando un agente añade un modulo y su test— tendria el diff
    vacio y desapareceria del informe. Y desaparecer es lo peor que puede hacer,
    porque justo esa rama es la que no viaja.

    Los `.py` sin trackear cuentan; el ruido de caches, no (misma lista que usa el
    watch del mapa).
    """
    rc, salida, _ = _git(ruta, "diff", "--name-only", "HEAD")
    if rc == 0 and _texto(salida):
        return True
    rc, salida, _ = _git(ruta, "status", "--porcelain")
    if rc != 0:
        return False
    for linea in _texto(salida).splitlines():
        if not linea.startswith("??"):
            continue
        rel = linea[3:].strip().strip('"')
        if rel.endswith(".py") and not any(p in rel for p in RUIDO):
            return True
    return False


def verifica(root, ficheros, staged=False, traza=None):
    """Corre `ficheros` de test sobre HEAD + el diff que se está midiendo.

    Devuelve un informe; no imprime nada por su cuenta (la salida de pytest sí va
    directa a la terminal, como en `tests --run`). `traza` es un callback opcional
    para que quien llama cuente lo que está pasando.

    El disco queda como se encontró aunque pytest falle o el parche no aplique.
    """
    decir = traza or (lambda _linea: None)
    # `exit_code` es lo que dijo pytest (None si no llego a correr). `veredicto` es
    # otra cosa: si se pudo verificar el cambio ENTERO. Se separan porque no coinciden
    # — con un fichero de test que no viaja, pytest puede decir 0 y la verificacion
    # seguir incompleta. Arrancan en 1: no haber podido comprobar nunca es un pase.
    informe = {
        "monto": False,
        "motivo": "",
        "base": "",
        "sin_trackear": [],
        "ausentes": [],
        "corridos": [],
        "exit_code": None,
        "veredicto": 1,
    }

    raiz = _raiz_git(root)
    if not raiz:
        informe["motivo"] = "no es un repositorio git: no hay base limpia contra la que medir"
        return informe

    rc, salida, _ = _git(raiz, "rev-parse", "HEAD")
    if rc != 0:
        informe["motivo"] = "el repositorio no tiene ningun commit todavia"
        return informe
    base = _texto(salida)
    informe["base"] = base[:7]

    # El diff que se mide: lo mismo que ya eligio quien llamo (--staged o no).
    rc, parche, err = _git(raiz, "diff", "--cached", base) if staged else _git(raiz, "diff", base)
    if rc != 0:
        informe["motivo"] = "no se pudo obtener el diff: %s" % _texto(err)
        return informe

    informe["sin_trackear"] = _sin_trackear(raiz)

    tmp = tempfile.mkdtemp(prefix="gb-aislado-")
    arbol = os.path.join(tmp, "arbol")
    try:
        rc, _, err = _git(raiz, "worktree", "add", "--detach", arbol, base)
        if rc != 0:
            informe["motivo"] = "no se pudo montar el arbol limpio: %s" % _texto(err)
            return informe
        informe["monto"] = True
        decir("arbol limpio en %s + tu diff" % informe["base"])

        if parche.strip():
            rc, _, err = _git(arbol, "apply", "--3way", "-", entrada=parche)
            if rc != 0:
                informe["monto"] = False
                informe["motivo"] = "el diff no aplica sobre %s: %s" % (informe["base"], _texto(err))
                return informe

        # Los tests salen relativos a `root`, que puede ser un subdirectorio.
        sub = os.path.relpath(os.path.abspath(root), raiz)
        cwd = os.path.normpath(os.path.join(arbol, sub)) if sub != "." else arbol

        presentes, ausentes = [], []
        for rel in ficheros:
            destino = os.path.join(cwd, rel.replace("/", os.sep))
            (presentes if os.path.isfile(destino) else ausentes).append(rel)
        informe["ausentes"] = ausentes
        informe["corridos"] = presentes

        if not presentes:
            # Que no quede ni un fichero no es un pase: es que el cambio no viaja.
            informe["veredicto"] = 1 if ausentes else 0
            return informe

        cmd = [sys.executable, "-m", "pytest"] + presentes
        decir("$ %s" % " ".join(cmd[1:]))
        try:
            informe["exit_code"] = subprocess.call(cmd, cwd=cwd)
        except OSError as error:
            informe["motivo"] = "no se pudo lanzar pytest: %s" % error
            informe["exit_code"] = 1

        # Un fichero de test que no viaja deja la verificacion incompleta, y una
        # verificacion incompleta NO se reporta como verde por mucho que lo que si
        # corrio pasara. Es exactamente el falso verde que este modo existe para matar.
        informe["veredicto"] = 1 if ausentes else informe["exit_code"]
        return informe
    finally:
        # Se limpia siempre. Un arnes que deja worktrees colgando en el repo del
        # usuario es peor que el problema que resuelve.
        _git(raiz, "worktree", "remove", "--force", arbol)
        shutil.rmtree(tmp, ignore_errors=True)
        _git(raiz, "worktree", "prune")


def converge(root, traza=None):
    """N líneas de trabajo en paralelo: cada una sola, y luego todas juntas.

    Verificar solo la unión esconde el fallo que se midió el 5-ago-2026: el diff de
    un agente estaba ROJO en solitario y la unión salía VERDE porque otro agente,
    sin saberlo, había arreglado un fichero compartido. Mirando solo el merge, ese
    trabajo se da por bueno y el rescate no se entera nadie.

    Por eso aquí se corren las dos cosas y **lo que se reporta es la diferencia**:
    quién no se sostiene solo. Ese es el dato que ninguna otra herramienta da.
    """
    from . import impacted

    decir = traza or (lambda _linea: None)
    informe = {
        "monto": False,
        "motivo": "",
        "base": "",
        "ramas": [],
        "union": None,
        "rescatados": [],
        "choque_semantico": False,
        "veredicto": 1,
    }

    raiz = _raiz_git(root)
    if not raiz:
        informe["motivo"] = "no es un repositorio git"
        return informe

    activos = [(ruta, head) for ruta, head in _worktrees(raiz) if _tiene_cambios(ruta)]
    if not activos:
        informe["motivo"] = "ningun worktree con cambios que verificar"
        informe["veredicto"] = 0
        return informe

    bases = {head for _ruta, head in activos}
    informe["base"] = sorted(bases)[0][:7] if len(bases) == 1 else ""
    informe["monto"] = True

    # 1) Cada uno solo, sobre su propia base limpia.
    for ruta, head in activos:
        nombre = os.path.basename(ruta)
        decir("--- %s (solo) ---" % nombre)
        ficheros = (impacted.analyze(ruta, None, worktree=True).get("tests") or [])
        sub = verifica(ruta, ficheros, traza=traza)
        informe["ramas"].append({
            "nombre": nombre,
            "ruta": ruta,
            "base": head[:7],
            "veredicto": sub["veredicto"],
            "exit_code": sub["exit_code"],
            "sin_trackear": sub["sin_trackear"],
            "ausentes": sub["ausentes"],
            "motivo": sub["motivo"],
        })

    # 2) La union. Solo tiene sentido si todos parten del mismo commit: superponer
    #    diffs de bases distintas produce un arbol que no existio nunca, y un
    #    veredicto sobre algo inventado es peor que no dar veredicto (regla 9).
    if len(bases) != 1:
        informe["motivo"] = ("los worktrees parten de bases distintas (%s): "
                             "no se calcula la union" % ", ".join(sorted(b[:7] for b in bases)))
        informe["veredicto"] = max(r["veredicto"] for r in informe["ramas"])
        return informe

    base = sorted(bases)[0]
    # Lo que no viaja en una rama tampoco viaja a la union: esa union esta tan
    # incompleta como la rama, aunque desde dentro no pueda verlo (calcula sus
    # tests del arbol compuesto, donde el fichero que falta sigue sin estar).
    incompletas = [r["nombre"] for r in informe["ramas"] if r["ausentes"]]
    informe["union"] = _union(raiz, base, activos, decir, impacted, incompletas)

    # Un rescate exige que la rama CORRIERA sus tests y fallaran, y que la union
    # pasara. Una rama roja por verificacion incompleta no esta rescatada: esta
    # sin comprobar, y la union tampoco la comprueba. Y con una sola rama no hay
    # rescate posible — no hay nadie mas que pudiera haberlo hecho.
    if informe["union"] and informe["union"]["veredicto"] == 0 and len(informe["ramas"]) > 1:
        informe["rescatados"] = sorted(
            r["nombre"] for r in informe["ramas"]
            if r["exit_code"] not in (None, 0)
        )

    # El caso INVERSO al rescate, y el que hay que gritar: todas verdes solas y
    # la union rota. No es que una rama este mal — es que dos cambios correctos
    # se contradicen al componerse, y ninguna de las dos lo puede ver desde
    # dentro. El sector lo nombra como la clase mas dificil y sin dueno
    # (ago-2026, tasa medida del 5-10%): «el CI en verde te dice que los tests
    # que ya tenias siguen pasando; no te dice que tres cambios son correctos
    # JUNTOS». Un merge tool no puede decidirlo porque mira TEXTO; aqui se corre
    # lo que el grafo dice que toca sobre el arbol compuesto.
    #
    # Se nombra en su propio campo por el mismo motivo que `rescatados`: deducirlo
    # cruzando "todas las ramas en 0" con "union != 0" es justo lo que nadie hace
    # al leer una salida.
    informe["choque_semantico"] = bool(
        informe["union"]
        and informe["union"]["veredicto"] != 0
        and not informe["union"]["conflictos"]
        and len(informe["ramas"]) > 1
        and all(r["veredicto"] == 0 for r in informe["ramas"])
    )

    veredictos = [r["veredicto"] for r in informe["ramas"]]
    if informe["union"]:
        veredictos.append(informe["union"]["veredicto"])
    informe["veredicto"] = max(veredictos) if veredictos else 1
    return informe


def _lleva_los_nuevos(activos, arbol):
    """Copia a la union los ficheros SIN TRACKEAR de cada rama. Devuelve colisiones.

    Dos ramas que crean la MISMA ruta con contenido distinto es una colision de
    verdad —igual que si tocaran las mismas lineas— y se reporta como tal en vez
    de que gane la ultima en copiarse. Con contenido identico no hay nada que
    decidir y pasa en silencio.
    """
    colisiones, puestos = [], {}
    for ruta, _head in activos:
        for rel in _sin_trackear(ruta):
            origen = os.path.join(ruta, rel.replace("/", os.sep))
            if not os.path.isfile(origen):
                continue                       # una carpeta sin trackear: no es un fichero
            try:
                with open(origen, "rb") as fh:
                    cuerpo = fh.read()
            except OSError:
                continue
            if rel in puestos:
                if puestos[rel] != cuerpo:
                    colisiones.append("%s (dos ramas crean %s distinto)"
                                      % (os.path.basename(ruta), rel))
                continue
            destino = os.path.join(arbol, rel.replace("/", os.sep))
            try:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, "wb") as fh:
                    fh.write(cuerpo)
            except OSError:
                continue
            puestos[rel] = cuerpo
    return colisiones


def _union(raiz, base, activos, decir, impacted, incompletas=()):
    """Los N diffs superpuestos sobre un arbol limpio, y la suite que toca encima."""
    salida = {"veredicto": 1, "exit_code": None, "conflictos": [], "motivo": ""}
    if incompletas:
        salida["motivo"] = ("hay tests que no viajan (%s): la union esta tan "
                            "incompleta como esas ramas" % ", ".join(sorted(incompletas)))
        return salida
    tmp = tempfile.mkdtemp(prefix="gb-union-")
    arbol = os.path.join(tmp, "arbol")
    try:
        rc, _, err = _git(raiz, "worktree", "add", "--detach", arbol, base)
        if rc != 0:
            salida["motivo"] = "no se pudo montar la union: %s" % _texto(err)
            return salida

        decir("--- union de %d rama(s) sobre %s ---" % (len(activos), base[:7]))
        for ruta, _head in activos:
            rc, parche, _ = _git(ruta, "diff", "HEAD")
            if rc != 0 or not parche.strip():
                continue
            rc, _, err = _git(arbol, "apply", "--3way", "-", entrada=parche)
            if rc != 0:
                # Colision textual de verdad: dos ramas tocan las mismas lineas.
                salida["conflictos"].append(os.path.basename(ruta))

        # Los ficheros NUEVOS no van en `git diff HEAD`, asi que sin esto no
        # viajan y la union se monta SIN el trabajo de quien creo modulos. Y no
        # se quedaba callada: daba VERDE sobre un arbol al que le faltaba una
        # rama entera — un falso verde en la capa que existe para cazarlos.
        #
        # Medido el 11-ago-2026 con `bancos/banco_convergencia.py`: rama A pasa
        # `precio` a centimos y adapta su consumidor; rama B anade un consumidor
        # NUEVO escrito contra euros. Cada una verde, los diffs mergean limpios
        # —tocan ficheros distintos— y la union tenia que estar rota. Salia verde
        # porque `informe.py` y su test no llegaban.
        #
        # El dato ya estaba (`sin_trackear` por rama): lo que faltaba era usarlo.
        # El guardia de la union miraba `ausentes`, que es otra cosa — lo que le
        # falto a la rama al verificarse EN SU PROPIO arbol.
        salida["conflictos"].extend(_lleva_los_nuevos(activos, arbol))

        if salida["conflictos"]:
            salida["motivo"] = "no se pudo componer la union: %s" % ", ".join(salida["conflictos"])
            return salida

        ficheros = (impacted.analyze(arbol, None, worktree=True).get("tests") or [])
        if not ficheros:
            salida["veredicto"] = 0
            return salida
        cmd = [sys.executable, "-m", "pytest"] + ficheros
        decir("$ %s" % " ".join(cmd[1:]))
        try:
            salida["exit_code"] = subprocess.call(cmd, cwd=arbol)
        except OSError as error:
            salida["motivo"] = "no se pudo lanzar pytest: %s" % error
            salida["exit_code"] = 1
        salida["veredicto"] = salida["exit_code"]
        return salida
    finally:
        _git(raiz, "worktree", "remove", "--force", arbol)
        shutil.rmtree(tmp, ignore_errors=True)
        _git(raiz, "worktree", "prune")
