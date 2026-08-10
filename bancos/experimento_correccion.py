"""¿El grafo mejora la CORRECCION de un agente, o solo su gasto?

Es la pregunta que este proyecto no ha respondido nunca. Todo lo medido hasta hoy
—ahorro de tests, recall y precision del grafo, falsos verdes— es gasto y
seguridad. Que `gb calls` haga que un agente escriba codigo mas CORRECTO se da por
supuesto porque suena obvio, y en este repo lo que suena obvio se mide.

    A (control)     : el agente con sus herramientas de siempre
    B (tratamiento) : lo mismo + los hechos del grafo (`gb calls`)
    CORRECCION      : una suite OCULTA que el agente no ve nunca

La suite oculta es el punto entero. Un agente que edita el test hasta que pasa
"aprueba" sin ser correcto — medido fuera: los commits de agentes tocan tests un
23% frente al 13% de los humanos, y anaden mocks un 36% frente al 26%. Si el
oraculo es visible, mide obediencia; si esta oculto, mide correccion.

LA TAREA: cambiar el contrato de `precio()`, que devolvia euros y pasa a devolver
centimos. Todos los llamantes tienen que adaptarse. Hay tres, y ahi esta el
diseno:

  1. `carrito.total`      — llamada normal: `grep precio` lo encuentra
  2. `informe.linea`      — importa con ALIAS (`from tienda.precio import precio as p`),
                            asi que `grep "precio("` NO lo encuentra
  3. `descuentos.aplicar` — lo recibe como VALOR en una tabla de despacho, asi que
                            no hay ninguna llamada escrita que grepear

Los tres son patrones normales de codigo real, no rarezas fabricadas para que gane
el tratamiento: el alias y el despacho por tabla estan en el propio `src/` de este
repo. Pero conviene decirlo claro — **la tarea se elige con casos donde el grafo
tiene algo que aportar**. Si el resultado sale a favor de B, mide eso y no "los
agentes son mejores con gb" en general.

    python bancos/experimento_correccion.py --dry   # control: valida el oraculo
    python bancos/experimento_correccion.py --prompts
"""

import argparse
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(RAIZ, "bancos", "bench-correccion")

MODULOS = {
    "tienda/__init__.py": "",
    "tienda/precio.py": (
        '"""El contrato que cambia."""\n\n\n'
        "def precio(articulo):\n"
        '    """Devuelve el precio EN EUROS."""\n'
        "    return {'pan': 2, 'leche': 1}.get(articulo, 0)\n"
    ),
    # 1. llamada normal: grep la encuentra
    "tienda/carrito.py": (
        "from tienda.precio import precio\n\n\n"
        "def total(articulos):\n"
        "    return sum(precio(a) for a in articulos)\n"
    ),
    # 2. import con ALIAS: `grep 'precio('` no la encuentra
    "tienda/informe.py": (
        "from tienda.precio import precio as p\n\n\n"
        "def linea(articulo):\n"
        '    return "%s: %s" % (articulo, p(articulo))\n'
    ),
    # 3. pasado como VALOR a una tabla: no hay llamada escrita que grepear
    "tienda/descuentos.py": (
        "from tienda.precio import precio\n\n"
        "TARIFAS = {'normal': precio}\n\n\n"
        "def aplicar(articulo, tarifa='normal'):\n"
        "    return TARIFAS[tarifa](articulo) * 0.9\n"
    ),
}

#: La suite que el agente NO ve. Vive fuera del proyecto y se copia al evaluar.
#: Comprueba el contrato NUEVO en los tres llamantes: si el agente se dejo uno,
#: aqui se ve, y no hay forma de "arreglarlo" tocando lo que no conoce.
OCULTOS = (
    '"""Suite OCULTA: el agente nunca la ve. Contrato nuevo = CENTIMOS."""\n'
    "from tienda.carrito import total\n"
    "from tienda.descuentos import aplicar\n"
    "from tienda.informe import linea\n"
    "from tienda.precio import precio\n\n\n"
    "def test_precio_en_centimos():\n"
    "    assert precio('pan') == 200\n\n\n"
    "def test_total_sigue_en_euros():\n"
    "    assert total(['pan', 'leche']) == 3\n\n\n"
    "def test_linea_sigue_en_euros():\n"
    "    # El VALOR en euros, no su FORMATO: '2' y '2.0' cumplen igual el\n"
    "    # contrato que pedia la tarea. La primera version comparaba la cadena\n"
    "    # entera y suspendia a un agente que habia adaptado bien los tres\n"
    "    # llamantes, por elegir division real en vez de entera. Un oraculo que\n"
    "    # mide formato no mide correccion, y los 0/3 de los DOS brazos venian\n"
    "    # de aqui: parecian 'el grafo no sirve' y eran 'la medida no vale'.\n"
    "    assert float(linea('pan').split(': ')[1]) == 2\n\n\n"
    "def test_descuento_sigue_en_euros():\n"
    "    assert abs(aplicar('pan') - 1.8) < 1e-9\n"
)

TAREA = (
    "En el paquete `tienda`, `precio()` devuelve EUROS y tiene que pasar a devolver "
    "CENTIMOS (multiplicar por 100). El resto del programa debe seguir comportandose "
    "EXACTAMENTE igual que antes desde fuera: los totales, las lineas de informe y "
    "los descuentos siguen expresados en euros. Adapta lo que haga falta."
)


def genera():
    """El proyecto que ve el agente. Sin la suite oculta, obviamente."""
    shutil.rmtree(BASE, ignore_errors=True)
    for rel, cuerpo in MODULOS.items():
        ruta = os.path.join(BASE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8", newline="") as fh:
            fh.write(cuerpo)
    # Un test VISIBLE, para que el agente tenga con que trabajar y para que la
    # tarea sea realista. Cubre solo el llamante facil: si el agente se conforma
    # con ponerlo verde, se deja los otros dos y la suite oculta lo dice.
    ruta = os.path.join(BASE, "tests", "test_visible.py")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        fh.write('"""Lo unico que el agente ve."""\n'
                 "from tienda.carrito import total\n\n\n"
                 "def test_total():\n"
                 "    assert total(['pan', 'leche']) == 3\n")
    subprocess.run(["git", "init", "-q"], cwd=BASE, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=BASE, capture_output=True)
    subprocess.run(["git", "-c", "user.email=b@b", "-c", "user.name=b",
                    "commit", "-qm", "base"], cwd=BASE, capture_output=True)
    return BASE


def evalua(proyecto):
    """La suite OCULTA sobre el arbol que dejo el agente. (ok, salida)."""
    ruta = os.path.join(proyecto, "tests", "test_oculto.py")
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        fh.write(OCULTOS)
    try:
        entorno = dict(os.environ, PYTHONPATH=proyecto)
        r = subprocess.run([sys.executable, "-m", "pytest", ruta, "-q"],
                           cwd=proyecto, capture_output=True, text=True,
                           timeout=300, env=entorno)
        return r.returncode == 0, (r.stdout or "")[-600:]
    finally:
        os.remove(ruta)      # que no quede en el arbol que se inspecciona luego


def _parche(proyecto, completo):
    """Simula a un agente. `completo=False` arregla SOLO lo que grep encuentra."""
    def escribe(rel, texto):
        with open(os.path.join(proyecto, rel.replace("/", os.sep)),
                  "w", encoding="utf-8", newline="") as fh:
            fh.write(texto)

    escribe("tienda/precio.py",
            '"""El contrato que cambia."""\n\n\n'
            "def precio(articulo):\n"
            '    """Devuelve el precio EN CENTIMOS."""\n'
            "    return {'pan': 200, 'leche': 100}.get(articulo, 0)\n")
    escribe("tienda/carrito.py",
            "from tienda.precio import precio\n\n\n"
            "def total(articulos):\n"
            "    return sum(precio(a) for a in articulos) / 100\n")
    if not completo:
        return
    escribe("tienda/informe.py",
            "from tienda.precio import precio as p\n\n\n"
            "def linea(articulo):\n"
            '    return "%s: %s" % (articulo, p(articulo) // 100)\n')
    escribe("tienda/descuentos.py",
            "from tienda.precio import precio\n\n"
            "TARIFAS = {'normal': precio}\n\n\n"
            "def aplicar(articulo, tarifa='normal'):\n"
            "    return TARIFAS[tarifa](articulo) / 100 * 0.9\n")


def dry():
    """Control positivo y negativo del ORACULO, sin gastar un solo agente.

    Un oraculo que no puede fallar no mide nada, y aqui eso significaria gastar
    cuota para nada. Asi que primero se comprueba que la suite oculta:

      - se pone ROJA con el agente perezoso (arregla solo lo que grep encuentra)
      - se pone VERDE con el agente completo

    Si el perezoso pasara, la tarea no discrimina y no hay experimento.
    """
    fallos = 0
    for nombre, completo, esperado in (("perezoso (solo lo grepeable)", False, False),
                                       ("completo (los tres llamantes)", True, True)):
        proyecto = genera()
        _parche(proyecto, completo)
        ok, salida = evalua(proyecto)
        veredicto = "OK" if ok == esperado else "*** EL ORACULO NO DISCRIMINA ***"
        if ok != esperado:
            fallos += 1
        print("  %-32s suite oculta: %-5s  esperado: %-5s  %s"
              % (nombre, "verde" if ok else "ROJA", "verde" if esperado else "ROJA",
                 veredicto))
        if not ok and esperado:
            print(salida)
    print("\n%s" % ("el oraculo discrimina: la tarea vale" if not fallos
                    else "ARREGLAR EL BANCO ANTES DE GASTAR AGENTES"))
    return 1 if fallos else 0


def prompts():
    """Los dos prompts, para leerlos antes de gastar. La unica diferencia es B."""
    proyecto = genera()
    comun = (TAREA + "\n\nProyecto: %s\nNo toques `tests/`. No commitees.\n" % proyecto)
    print("=== BRAZO A (control) ===\n" + comun)
    rc, salida = 0, ""
    try:
        r = subprocess.run([sys.executable, "-m", "galaxybrain.cli", "calls",
                            "tienda.precio.precio", "--depth", "2"],
                           cwd=proyecto, capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, PYTHONPATH=proyecto))
        rc, salida = r.returncode, r.stdout
    except OSError as error:
        salida = "(no se pudo consultar el grafo: %s)" % error
    print("\n=== BRAZO B (tratamiento) ===\n" + comun)
    print("Hechos del grafo (gb calls tienda.precio.precio --depth 2):\n")
    print(salida if salida.strip() else "(vacio, rc=%s)" % rc)


def _copia_limpia(destino):
    """Un proyecto recien generado en su propia carpeta, por tirada."""
    genera()
    shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(BASE, destino, ignore=shutil.ignore_patterns(".git"))
    return destino


def _prompt(proyecto, brazo):
    """Lo MISMO en los dos brazos salvo los hechos del grafo. Esa es la variable."""
    texto = (TAREA + "\n\nEstas en la raiz del proyecto. No toques `tests/`. "
             "No commitees. Cuando termines, di que ficheros cambiaste.\n")
    if brazo != "B":
        return texto
    r = subprocess.run([sys.executable, "-m", "galaxybrain.cli", "calls",
                        "tienda.precio.precio", "--depth", "2"],
                       cwd=proyecto, capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, PYTHONPATH=proyecto))
    return texto + ("\nHechos del grafo (`gb calls tienda.precio.precio`):\n\n%s\n"
                    % (r.stdout or "(sin salida)"))


def _corre_agente(proyecto, prompt, timeout_seg):
    """`claude -p` headless, Opus. Devuelve (ok_arranco, motivo)."""
    exe = shutil.which("claude")
    if not exe:
        return False, "claude CLI no esta en PATH"
    # Fuera las GIT_* del proceso padre: el commit del banco heredaba fechas y
    # rutas del repo de gb. Mismo motivo que en bucle.py, no se reinventa.
    entorno = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        r = subprocess.run([exe, "-p", prompt, "--model", "opus",
                            "--permission-mode", "acceptEdits"],
                           cwd=proyecto, capture_output=True, text=True,
                           timeout=timeout_seg, env=entorno)
    except subprocess.TimeoutExpired:
        return False, "timeout de %ds" % timeout_seg
    except OSError as error:
        return False, "no arranco: %s" % error
    return r.returncode == 0, "rc=%d" % r.returncode


def tirada(n_por_brazo, timeout_seg):
    """El experimento. El presupuesto se escribe ANTES y se imprime al empezar.

    Este repo ya se comio 40 min y 150 llamadas por no escribir uno.
    """
    salon = os.path.join(RAIZ, "bancos", "bench-correccion-tiradas")
    shutil.rmtree(salon, ignore_errors=True)
    os.makedirs(salon, exist_ok=True)
    resultados = {"A": [], "B": []}
    print("presupuesto: %d tiradas (%d por brazo), tope %ds cada una\n"
          % (2 * n_por_brazo, n_por_brazo, timeout_seg), flush=True)
    for brazo in ("A", "B"):
        for i in range(n_por_brazo):
            proyecto = _copia_limpia(os.path.join(salon, "%s%d" % (brazo, i + 1)))
            prompt = _prompt(proyecto, brazo)
            arranco, motivo = _corre_agente(proyecto, prompt, timeout_seg)
            if not arranco:
                resultados[brazo].append(None)
                print("  %s%d  NO SE PUDO CORRER (%s)" % (brazo, i + 1, motivo), flush=True)
                continue
            ok, _salida = evalua(proyecto)
            resultados[brazo].append(ok)
            print("  %s%d  suite oculta: %s" % (brazo, i + 1, "verde" if ok else "ROJA"),
                  flush=True)
    print("\n=== CORRECCION (suite oculta, que el agente nunca vio) ===")
    for brazo, etiqueta in (("A", "control (sin grafo)"), ("B", "con `gb calls`")):
        hechas = [x for x in resultados[brazo] if x is not None]
        print("  %-22s %d de %d correctas" % (etiqueta, sum(1 for x in hechas if x),
                                              len(hechas)))
    a = [x for x in resultados["A"] if x is not None]
    b = [x for x in resultados["B"] if x is not None]
    if len(a) < n_por_brazo or len(b) < n_por_brazo:
        print("\n  OJO: faltan tiradas; con menos muestra de la fijada no se concluye.")
    elif sum(a) == sum(b):
        print("\n  EMPATE: con esta muestra el grafo no cambia la correccion.")
    return resultados


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry", action="store_true",
                   help="valida el oraculo con dos agentes simulados, sin gastar cuota")
    p.add_argument("--prompts", action="store_true", help="enseñar los dos prompts")
    p.add_argument("--tirada", action="store_true",
                   help="EL EXPERIMENTO: gasta cuota (claude -p, Opus)")
    p.add_argument("--n", type=int, default=3, help="tiradas por brazo (por defecto 3)")
    p.add_argument("--timeout", type=int, default=300,
                   help="tope por tirada en segundos (por defecto 300)")
    args = p.parse_args()
    if args.prompts:
        prompts()
        raise SystemExit(0)
    if args.tirada:
        tirada(args.n, args.timeout)
        raise SystemExit(0)
    raise SystemExit(dry())
