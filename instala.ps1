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

gb on
if ($LASTEXITCODE -ne 0) { Write-Error "gb on fallo (codigo $LASTEXITCODE)"; exit 1 }
gb status

Write-Host ""
Write-Host "Listo. Todo proceso Python de este entorno queda cubierto."
Write-Host "La gate v3 viene en el mismo paquete, no necesita nada mas:"
Write-Host "  gb graph <src> --smells    (mapa advisory, funciona ya)"
Write-Host "  gb graph <src> --gate      (bloqueante; pide un .gb-boundaries propio del repo)"
