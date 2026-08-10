"""Criterio 6 en varios lenguajes a la vez, con una sola tabla.

Cinco scripts casi identicos serian el mismo error que la tabla `LENGUAJES` evita:
lo que cambia entre lenguajes es la SINTAXIS y el comando del runner, no el
protocolo. Aqui el protocolo se escribe una vez.

Cadena de 4 modulos —`iva <- carrito <- factura`, mas `texto` aislado como
control— y 4 ficheros de test. Romper el mas profundo debe seleccionar 3; el
siguiente 2; los dos ultimos 1. Cualquier otra cosa es sub-seleccion.

Ninguno usa gestor de paquetes: minitest viene con Ruby, y PHP, Lua y Java corren
scripts que salen con codigo distinto de cero. Un banco que exige `composer` o
`gradle` no se puede correr, y uno que no se corre no mide nada.

    python bancos/bench_multi.py            # todos los que tengan runtime
    python bancos/bench_multi.py ruby java  # solo esos
"""

import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import estricto  # noqa: E402  (el banco es un script, no un paquete)

BASE = os.path.dirname(os.path.abspath(__file__))
GB = [sys.executable, "-m", "galaxybrain.cli"]

#: Los cuatro modulos de la cadena, por lenguaje. `texto` no depende de nadie:
#: es el control que demuestra que la seleccion no esta cogiendo todo.
FUENTES = {
    "ruby": {
        "dir": "lib", "ext": ".rb",
        "mod": {
            "iva": "def iva\n  0.21\nend\n",
            "carrito": "require_relative 'iva'\n\ndef total(xs)\n  xs.sum * (1 + iva)\nend\n",
            "factura": "require_relative 'carrito'\n\ndef emitir(xs)\n  total(xs) * 0.9\nend\n",
            "texto": "def mayus(s)\n  s.upcase\nend\n",
        },
        "tdir": "test", "text": "_test.rb",
        "test": {
            "iva": "require_relative '../lib/iva'\nraise 'mal' unless iva > 0\n",
            "carrito": "require_relative '../lib/carrito'\nraise 'mal' unless total([10]) > 0\n",
            "factura": "require_relative '../lib/factura'\nraise 'mal' unless emitir([10]) > 0\n",
            "texto": "require_relative '../lib/texto'\nraise 'mal' unless mayus('a') == 'A'\n",
        },
        "bin": "ruby", "cmd": lambda f: ["ruby", f],
        "romper": lambda s, n: s.replace("def %s" % n, "def %s\n  raise 'ESTRES'" % n, 1),
    },
    "php": {
        "dir": "lib", "ext": ".php",
        "mod": {
            "iva": "<?php\nfunction iva() { return 0.21; }\n",
            "carrito": "<?php\nrequire_once 'iva.php';\n"
                       "function total($xs) { return array_sum($xs) * (1 + iva()); }\n",
            "factura": "<?php\nrequire_once 'carrito.php';\n"
                       "function emitir($xs) { return total($xs) * 0.9; }\n",
            "texto": "<?php\nfunction mayus($s) { return strtoupper($s); }\n",
        },
        "tdir": "test", "text": "_test.php",
        "test": {
            "iva": "<?php\nrequire_once __DIR__.'/../lib/iva.php';\n"
                   "if (iva() <= 0) { exit(1); }\n",
            "carrito": "<?php\nrequire_once __DIR__.'/../lib/carrito.php';\n"
                       "if (total([10]) <= 0) { exit(1); }\n",
            "factura": "<?php\nrequire_once __DIR__.'/../lib/factura.php';\n"
                       "if (emitir([10]) <= 0) { exit(1); }\n",
            "texto": "<?php\nrequire_once __DIR__.'/../lib/texto.php';\n"
                     "if (mayus('a') !== 'A') { exit(1); }\n",
        },
        "bin": "php", "cmd": lambda f: ["php", f],
        "romper": lambda s, n: s.replace("function %s(" % n,
                                         "function %s(" % n, 1).replace(
            "{ return", "{ throw new Exception('ESTRES'); return", 1),
    },
    "lua": {
        "dir": "lib", "ext": ".lua",
        "mod": {
            # multilinea A PROPOSITO: con la funcion en una sola linea, la rotura
            # se inserta DESPUES de esa linea, o sea fuera del cuerpo — no cae
            # dentro de ningun simbolo, no hay semilla y la seleccion cae a todo.
            # El banco daba 4-2-4-4 por eso, y parecia fallo del motor.
            "iva": "function iva()\n  return 0.21\nend\n",
            "carrito": "function total(xs)\n  local t = 0\n  for _, x in ipairs(xs) do t = t + x end\n"
                       "  return t * (1 + iva())\nend\n",
            "factura": "function emitir(xs)\n  return total(xs) * 0.9\nend\n",
            "texto": "function mayus(s)\n  return string.upper(s)\nend\n",
        },
        "tdir": "test", "text": "_test.lua",
        "test": {
            "iva": "dofile('lib/iva.lua')\nassert(iva() > 0)\n",
            "carrito": "dofile('lib/iva.lua')\ndofile('lib/carrito.lua')\nassert(total({10}) > 0)\n",
            "factura": "dofile('lib/iva.lua')\ndofile('lib/carrito.lua')\ndofile('lib/factura.lua')\n"
                       "assert(emitir({10}) > 0)\n",
            "texto": "dofile('lib/texto.lua')\nassert(mayus('a') == 'A')\n",
        },
        "bin": "lua", "cmd": lambda f: ["lua", f],
        "romper": lambda s, n: s.replace("function %s(" % n,
                                         "function %s(" % n, 1).replace(
            "return", "error('ESTRES') return", 1),
    },
    "java": {
        "dir": "src", "ext": ".java", "clase": True,
        "mod": {
            "Iva": "public class Iva {\n    public static double get() { return 0.21; }\n}\n",
            "Carrito": "public class Carrito {\n    public static double total(double[] xs) {\n"
                       "        double t = 0; for (double x : xs) { t += x; }\n"
                       "        return t * (1 + Iva.get());\n    }\n}\n",
            "Factura": "public class Factura {\n    public static double emitir(double[] xs) {\n"
                       "        return Carrito.total(xs) * 0.9;\n    }\n}\n",
            "Texto": "public class Texto {\n    public static String mayus(String s) {\n"
                     "        return s.toUpperCase();\n    }\n}\n",
        },
        "tdir": "test", "text": "Test.java",
        "test": {
            "Iva": "public class IvaTest {\n    public static void main(String[] a) {\n"
                   "        if (Iva.get() <= 0) { throw new RuntimeException(\"mal\"); }\n    }\n}\n",
            "Carrito": "public class CarritoTest {\n    public static void main(String[] a) {\n"
                       "        if (Carrito.total(new double[]{10}) <= 0) { throw new RuntimeException(\"mal\"); }\n    }\n}\n",
            "Factura": "public class FacturaTest {\n    public static void main(String[] a) {\n"
                       "        if (Factura.emitir(new double[]{10}) <= 0) { throw new RuntimeException(\"mal\"); }\n    }\n}\n",
            "Texto": "public class TextoTest {\n    public static void main(String[] a) {\n"
                     "        if (!Texto.mayus(\"a\").equals(\"A\")) { throw new RuntimeException(\"mal\"); }\n    }\n}\n",
        },
        "bin": "java", "compila": True,
        "romper": lambda s, n: s.replace("{\n        double t = 0;",
                                         "{\n        if (true) throw new RuntimeException(\"ESTRES\");\n        double t = 0;", 1)
        .replace("{ return 0.21; }", "{ throw new RuntimeException(\"ESTRES\"); }", 1)
        .replace("        return Carrito.total(xs) * 0.9;",
                 "        if (true) throw new RuntimeException(\"ESTRES\");\n        return Carrito.total(xs) * 0.9;", 1)
        .replace("        return s.toUpperCase();",
                 "        if (true) throw new RuntimeException(\"ESTRES\");\n        return s.toUpperCase();", 1),
    },
}

#: (modulo, FUNCION) — no coinciden: `carrito` define `total`. Buscar la funcion
#: por el nombre del modulo dejaba tres de cuatro roturas sin aplicar, y el banco
#: lo dijo ("patron no encontrado") en vez de dar un verde silencioso.
ORDEN = {
    "ruby": [("iva", "iva"), ("carrito", "total"), ("factura", "emitir"), ("texto", "mayus")],
    "php": [("iva", "iva"), ("carrito", "total"), ("factura", "emitir"), ("texto", "mayus")],
    "lua": [("iva", "iva"), ("carrito", "total"), ("factura", "emitir"), ("texto", "mayus")],
    "java": [("Iva", "get"), ("Carrito", "total"), ("Factura", "emitir"), ("Texto", "mayus")],
}

#: como se rompe una funcion en cada lenguaje: la sentencia que lanza y si el
#: cuerpo abre con llave (ahi se inserta justo despues) o con salto de linea.
ROTURA = {
    "ruby": ("raise 'ESTRES'", None),
    "php": ("throw new Exception('ESTRES');", "{"),
    "lua": ("error('ESTRES')", None),
    "java": ('if (true) throw new RuntimeException("ESTRES");', "{"),
}


def rompe_funcion(s, funcion, sentencia, abre):
    """Inserta la sentencia al principio del cuerpo. Devuelve None si no encuentra
    la funcion — que se dice, en vez de seguir con un fichero intacto."""
    # el nombre seguido de `(` o de fin de linea: en Ruby `def iva` no lleva
    # parentesis, y buscar `iva(` dejaba la rotura sin aplicar
    m = re.search(r"\b%s\s*[(\r\n]" % re.escape(funcion), s)
    if m is None:
        return None
    i = m.start()
    if abre:
        j = s.find(abre, i)
        if j < 0:
            return None
        j += 1
    else:
        j = s.find("\n", i)
        if j < 0:
            return None
        j += 1
    return s[:j] + "\n  " + sentencia + "\n" + s[j:]


def _corre(cmd, cwd, timeout=600):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return p.returncode, p.stdout.decode("utf-8", "replace")


def genera(lang):
    cfg = FUENTES[lang]
    raiz = os.path.join(BASE, "bench-" + lang)
    shutil.rmtree(raiz, ignore_errors=True)
    os.makedirs(os.path.join(raiz, cfg["dir"]), exist_ok=True)
    os.makedirs(os.path.join(raiz, cfg["tdir"]), exist_ok=True)
    open(os.path.join(raiz, ".gitignore"), "w", encoding="utf-8").write("*.class\nout/\n")
    for nombre, cuerpo in cfg["mod"].items():
        open(os.path.join(raiz, cfg["dir"], nombre + cfg["ext"]), "w",
             encoding="utf-8").write(cuerpo)
    for nombre, cuerpo in cfg["test"].items():
        sufijo = cfg["text"]
        fichero = (nombre + sufijo) if cfg.get("clase") else (nombre + sufijo)
        open(os.path.join(raiz, cfg["tdir"], fichero), "w", encoding="utf-8").write(cuerpo)
    subprocess.run(["git", "init", "-q"], cwd=raiz, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=raiz, capture_output=True)
    subprocess.run(["git", "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-qm", "init"],
                   cwd=raiz, capture_output=True)
    return raiz


def ficheros_de(lang, raiz):
    """Los ficheros de test tal como los nombra el runner de ese lenguaje."""
    cfg = FUENTES[lang]
    return sorted(os.path.join(cfg["tdir"], f)
                  for f in os.listdir(os.path.join(raiz, cfg["tdir"])))


def corre_tests(lang, raiz, ficheros=None):
    """True si algo se pone ROJO. Sin `ficheros`, la suite entera."""
    cfg = FUENTES[lang]
    objetivo = ficheros if ficheros else ficheros_de(lang, raiz)
    if cfg.get("compila"):
        rc, _ = _corre(["javac", "-d", "out", "-cp", cfg["dir"]]
                       + [os.path.join(cfg["dir"], f) for f in os.listdir(os.path.join(raiz, cfg["dir"]))]
                       + [os.path.join(cfg["tdir"], f) for f in os.listdir(os.path.join(raiz, cfg["tdir"]))],
                       raiz)
        if rc != 0:
            return True
        for f in objetivo:
            clase = os.path.splitext(os.path.basename(f))[0]
            if _corre(["java", "-cp", "out", clase], raiz)[0] != 0:
                return True
        return False
    for f in objetivo:
        if _corre(cfg["cmd"](f.replace("\\", "/")), raiz)[0] != 0:
            return True
    return False


def seleccion(raiz):
    rc, out = _corre(GB + ["tests", "--worktree", "--json"], raiz)
    if not out.strip().startswith("{"):
        return None, False, "gb tests no devolvio json"
    d = json.loads(out)
    if d.get("range_error"):
        return None, False, d["range_error"]
    return list(d.get("tests") or []), bool(d.get("todo")), None


#: Lo que la seleccion DEBE traer en cada rotura, por la forma de la cadena:
#: `iva <- carrito <- factura`, mas `texto` aislado. Estaba escrito en prosa en
#: la cabecera de este fichero desde el principio y no lo comprobaba nadie.
CASCADA_ESPERADA = (3, 2, 1, 1)


def cascada(lang):
    """La mitad del banco que NO necesita runtime: cuantos tests elige gb.

    Que un test se ponga rojo lo dice el interprete y sin el no hay banco. Pero
    la CASCADA —a cuantos tests llega gb desde lo que se rompio— sale del grafo
    y se puede comprobar en cualquier maquina. Y es justo la mitad que fallo en
    Rust: alli el rojo/verde salia bien y lo que estaba roto era el alcance.

    Sirve para vigilar las licencias concedidas ANTES del criterio estricto
    (java, php, lua: 9-ago-2026) en una maquina que no tiene sus interpretes. No
    es una licencia —para eso hacen falta rojos reales— pero un fallo aqui SI es
    prueba de que la cascada esta rota.
    """
    raiz = genera(lang)
    sentencia, abre = ROTURA[lang]
    filas, mal = [], 0
    for (nombre, funcion), esperado in zip(ORDEN[lang], CASCADA_ESPERADA):
        subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=raiz, capture_output=True)
        ruta = os.path.join(raiz, cfg_de(lang, "dir"), nombre + cfg_de(lang, "ext"))
        roto = rompe_funcion(open(ruta, encoding="utf-8").read(), funcion, sentencia, abre)
        if roto is None:
            filas.append((nombre, None, esperado, "no se pudo romper"))
            mal += 1
            continue
        open(ruta, "w", encoding="utf-8", newline="").write(roto)
        sel, todo, error = seleccion(raiz)
        n = len(FUENTES[lang]["test"]) if todo else len(sel or ())
        nota = "" if error is None else error[:40]
        if todo and not con_licencia(lang):
            # Sin licencia, caer a la suite entera es lo CORRECTO, no un fallo:
            # es la caida segura funcionando. Contarlo como cascada rota seria
            # acusar al comportamiento que protege del verde falso.
            nota = "cae a todo (sin licencia: es lo correcto)"
        elif error or todo or n != esperado:
            mal += 1
            nota = nota or ("cayo a todo" if todo else "esperaba %d" % esperado)
        filas.append((nombre, n, esperado, nota))
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=raiz, capture_output=True)
    return filas, mal


def con_licencia(lang):
    """Si gb puede estrechar en ese lenguaje. Se lee de la tabla, no se copia."""
    sys.path.insert(0, os.path.join(os.path.dirname(BASE), "src"))
    from galaxybrain import lenguajes as tabla

    return bool(tabla.LENGUAJES.get(lang, {}).get("tia"))


def cfg_de(lang, clave):
    return FUENTES[lang][clave]


def banco(lang):
    cfg = FUENTES[lang]
    if not shutil.which(cfg["bin"]) or (cfg.get("compila") and not shutil.which("javac")):
        # Sin interprete no hay rojos, pero la CASCADA si se puede mirar — y es
        # la mitad que fallo en Rust. Callarse aqui seria dar por bueno lo que no
        # se ha comprobado, que es el error que este repo persigue todo el dia.
        filas, mal = cascada(lang)
        print("== %s ==  SIN RUNTIME (%s no esta): no hay rojos reales, pero la "
              "CASCADA si se mide" % (lang, cfg["bin"]))
        for nombre, n, esperado, nota in filas:
            print("   %-10s sel=%-4s esperado=%d  %s"
                  % (nombre, "?" if n is None else n, esperado,
                     "<<< %s" % nota if nota else "ok"))
        if not con_licencia(lang):
            print("   -> sin licencia: cae a la suite entera por diseño, asi que "
                  "aqui no hay cascada que medir.\n")
        else:
            print("   -> cascada %s (%d de %d roturas mal). NO es una licencia: "
                  "para eso hacen falta rojos reales, y sin %s no los hay.\n"
                  % ("EXACTA" if not mal else "ROTA", mal, len(filas), cfg["bin"]))
        return
    raiz = genera(lang)
    if corre_tests(lang, raiz):
        print("== %s ==  la suite base NO esta verde; el banco no mide nada\n" % lang)
        return
    n = len(cfg["test"])
    print("== %s ==  %d modulos, %d tests" % (lang, len(cfg["mod"]), n))
    falsos = ahorro = con_fuga = medidas = 0
    sentencia, abre = ROTURA[lang]
    for nombre, funcion in ORDEN[lang]:
        subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=raiz, capture_output=True)
        ruta = os.path.join(raiz, cfg["dir"], nombre + cfg["ext"])
        s = open(ruta, encoding="utf-8").read()
        roto = rompe_funcion(s, funcion, sentencia, abre)
        if roto is None:
            print("   %-10s (no se pudo romper: '%s(' no aparece)" % (nombre, funcion))
            continue
        open(ruta, "w", encoding="utf-8", newline="").write(roto)
        sel, todo, error = seleccion(raiz)
        if error:
            print("   %-10s ERROR: %s" % (nombre, error[:46]))
            continue
        rojo_sel = corre_tests(lang, raiz, sel) if sel and not todo else corre_tests(lang, raiz)
        # Criterio ESTRICTO: no basta con que la seleccion se ponga roja, tiene
        # que CONTENER todos los rojos. Con pocos tests encadenados, perder uno
        # impactado se tapa con que otro caiga (ver bancos/estricto.py).
        rojos, fugados = estricto.fuga(
            sel, todo, ficheros_de(lang, raiz),
            lambda fs: corre_tests(lang, raiz, list(fs)))
        rojo_full = bool(rojos)
        if rojo_full and not rojo_sel:
            v, falsos = "*** FALSO VERDE ***", falsos + 1
        elif rojo_full:
            v = "ok%s" % (" [cayo a todo]" if todo else "")
            ahorro += n - (len(sel) if sel and not todo else n)
        else:
            v = "sin cobertura"
        if not todo:
            medidas += 1
        if fugados:
            con_fuga += 1
        print("   %-10s sel=%d rojo_sel=%-5s rojo_full=%-5s %s%s"
              % (nombre, len(sel), rojo_sel, rojo_full, v,
                 estricto.linea_extra(rojos, fugados)))
    subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=raiz, capture_output=True)
    print("   -> " + estricto.resumen(len(ORDEN[lang]), falsos, con_fuga,
                                      100.0 * ahorro / (len(ORDEN[lang]) * n), medidas) + "\n")


for lang in (sys.argv[1:] or sorted(FUENTES)):
    banco(lang)
