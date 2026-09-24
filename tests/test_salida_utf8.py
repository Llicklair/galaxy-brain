"""Por tuberia, gb habla UTF-8.

En Windows la salida redirigida iba en cp1252: el `—` salia como 0x97 y quien
lee UTF-8 —el hook SessionStart, un `| python`— veia `�` o reventaba
(auditoria del 24-sep-2026). Fuera de Windows este test pasa de oficio.
"""

import os
import subprocess
import sys


def test_la_salida_por_tuberia_es_utf8():
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    salida = subprocess.run(
        [sys.executable, "-m", "galaxybrain.cli", "graph", "src", "--color", "never"],
        cwd=raiz, env=env, capture_output=True, timeout=120,
    )
    texto = salida.stdout.decode("utf-8")  # revienta si no es UTF-8
    assert "—" in texto
