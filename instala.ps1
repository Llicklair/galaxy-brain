# instala.ps1 - lleva galaxy-brain entero (consola v2 + gate v3) al entorno Python activo.
#
# Uso: desde el otro proyecto, con su venv activado (o sin venv, para el Python global):
#   powershell -ExecutionPolicy Bypass -File <ruta-a-galaxy-brain>\instala.ps1
#
# No lleva rutas cableadas: el repo es la carpeta donde vive este script.
# Idempotente: repetirlo sobre un entorno ya cubierto no rompe nada.

$ErrorActionPreference = 'Stop'

Write-Host "Instalando galaxy-brain desde $PSScriptRoot en el Python activo..."
python -m pip install -e $PSScriptRoot --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install fallo (codigo $LASTEXITCODE)"; exit 1 }

# Por `python -m` y no por `gb`: con un Python global sin permisos, pip instala
# en el user-site ("Defaulting to user installation") y gb.exe cae en una
# carpeta Scripts que no esta en el PATH. Aqui eso no puede romper nada.
python -m galaxybrain.cli on
if ($LASTEXITCODE -ne 0) { Write-Error "gb on fallo (codigo $LASTEXITCODE)"; exit 1 }
python -m galaxybrain.cli status

Write-Host ""
Write-Host "Listo. Todo proceso Python de este entorno queda cubierto."
Write-Host "La gate v3 viene en el mismo paquete, no necesita nada mas:"
Write-Host "  gb graph <src> --smells    (mapa advisory, funciona ya)"
Write-Host "  gb graph <src> --gate      (bloqueante; pide un .gb-boundaries propio del repo)"
if (-not (Get-Command gb -ErrorAction SilentlyContinue)) {
    $bin = python -c "import sysconfig, os; print(sysconfig.get_path('scripts', os.name + '_user'))"
    Write-Host ""
    Write-Host "OJO: el comando 'gb' no esta en tu PATH (quedo en $bin o en la carpeta Scripts de tu Python)."
    Write-Host "  anade esa carpeta al PATH, o usa: python -m galaxybrain.cli <comando>"
}
