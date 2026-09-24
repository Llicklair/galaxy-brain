#!/bin/sh
# instala.sh - lleva galaxy-brain al Python activo (macOS y Linux; el gemelo de instala.ps1).
#
# Uso, desde el otro proyecto:
#   con su venv activado     -> sh <ruta-a-galaxy-brain>/instala.sh     (local: ese entorno)
#   sin venv                 -> sh <ruta-a-galaxy-brain>/instala.sh     (global: el python3 del PATH)
#   otro interprete          -> PYTHON=/ruta/a/python sh .../instala.sh
#
# Sin rutas cableadas: el repo es la carpeta donde vive este script. Idempotente.
#
# Dos cosas que en Windows no muerden y aqui si (24-sep-2026):
# - PEP 668: el python3 de Homebrew y el de Ubuntu 23.04+ rechazan `pip install`
#   global ("externally-managed-environment"). Ahi se instala en el user-site,
#   que ese mismo interprete carga al arrancar, y se dice.
# - `gb` puede quedar fuera del PATH (~/Library/Python/3.x/bin, ~/.local/bin):
#   por eso todo va por `python -m galaxybrain.cli`, y al final se avisa.

set -e

REPO=$(cd "$(dirname "$0")" && pwd)

if [ -n "$PYTHON" ]; then
    PY=$PYTHON
elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PY=$VIRTUAL_ENV/bin/python
elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/Scripts/python.exe" ]; then
    PY=$VIRTUAL_ENV/Scripts/python.exe   # Git Bash en Windows
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

DONDE=$("$PY" -c 'import sys; print(sys.executable)')
echo "Instalando galaxy-brain desde $REPO en $DONDE..."

ERR=$(mktemp)
if ! "$PY" -m pip install -e "$REPO" --quiet 2>"$ERR"; then
    if grep -q "externally-managed-environment" "$ERR"; then
        echo "Python gestionado por el sistema (PEP 668): instalo en tu user-site."
        "$PY" -m pip install --user --break-system-packages -e "$REPO" --quiet
        USUARIO=1
    else
        cat "$ERR" >&2
        rm -f "$ERR"
        echo "pip install fallo" >&2
        exit 1
    fi
fi
rm -f "$ERR"

"$PY" -m galaxybrain.cli on
"$PY" -m galaxybrain.cli status

echo ""
echo "Listo. Todo proceso Python de este entorno queda cubierto."
if ! command -v gb >/dev/null 2>&1; then
    # El esquema de usuario de macOS no es posix_user (osx_framework_user en el
    # Python de python.org): se le pregunta al interprete, no se supone.
    BIN=$("$PY" -c 'import sysconfig, os, sys
if not sys.argv[1]:
    print(sysconfig.get_path("scripts")); raise SystemExit
try:
    s = sysconfig.get_preferred_scheme("user")
except AttributeError:
    s = "osx_framework_user" if sys.platform == "darwin" and sys._framework else os.name + "_user"
print(sysconfig.get_path("scripts", s))' "${USUARIO:-}" 2>/dev/null || echo "?")
    echo "OJO: el comando 'gb' no esta en tu PATH (quedo en $BIN)."
    echo "  anade esa carpeta al PATH, o usa: alias gb='$PY -m galaxybrain.cli'"
fi
