# instala.ps1 - lleva galaxy-brain entero (consola v2 + gate v3) al entorno Python activo.
#
# Uso: desde el otro proyecto, con su venv activado (o sin venv, para el Python global):
#   powershell -ExecutionPolicy Bypass -File <ruta-a-galaxy-brain>\instala.ps1
#
# No lleva rutas cableadas: el repo es la carpeta donde vive este script.
# Idempotente: repetirlo sobre un entorno ya cubierto no rompe nada.
#
# -ConVisor instala ademas la extension que renderiza el mapa dentro del editor.
# Va con bandera y NO por defecto: un instalador de un paquete Python que te toca
# el editor sin preguntar es exactamente la instalacion silenciosa que las reglas
# de trabajo prohiben. Sin la bandera se detecta y se dice, que es el patron de la
# regla 7 - deteccion, instalador oficial, verificacion.

param([switch]$ConVisor)

$ErrorActionPreference = 'Stop'

Write-Host "Instalando galaxy-brain desde $PSScriptRoot en el Python activo..."
python -m pip install -e $PSScriptRoot --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install fallo (codigo $LASTEXITCODE)"; exit 1 }

gb on
if ($LASTEXITCODE -ne 0) { Write-Error "gb on fallo (codigo $LASTEXITCODE)"; exit 1 }
gb status

# --- El mapa dentro del editor (opcional) -----------------------------------
# Ni VS Code ni Cursor renderizan HTML de serie: `code fichero.html` ensena el
# codigo, no el mapa. La extension oficial lo arregla, pero SOLO expone comandos
# del editor - no hay entrada por linea de ordenes, asi que GB_OPEN_CMD no puede
# lanzarla y el flujo queda manual (clic derecho -> Show Preview). Se dice aqui
# para que nadie espere una integracion que no existe.
$editor = Get-Command code -ErrorAction SilentlyContinue
if ($editor) {
    # SIN 2>$null a proposito: en PowerShell 5.1 redirigir el stderr de un
    # ejecutable nativo convierte cada linea en un ErrorRecord, y `code` escupe un
    # aviso de deprecacion por ahi. Con $ErrorActionPreference='Stop' eso lanzaba,
    # el catch se lo comia y la deteccion devolvia "no instalada" estando puesta -
    # un falso negativo silencioso, justo lo que este proyecto persigue.
    $instalada = $false
    try {
        $lista = & code --list-extensions
        $instalada = $lista -contains 'ms-vscode.live-server'
    } catch {
        Write-Host "  (no pude consultar las extensiones del editor: $_)"
    }
    if ($instalada) {
        Write-Host ""
        Write-Host "Visor del mapa en el editor: ya instalado (ms-vscode.live-server)."
        Write-Host "  Uso: genera el HTML sin --open y clic derecho -> Show Preview."
    } elseif ($ConVisor) {
        Write-Host ""
        Write-Host "Instalando el visor del mapa en el editor..."
        & code --install-extension ms-vscode.live-server
        if ($LASTEXITCODE -ne 0) { Write-Warning "no se pudo instalar el visor; el mapa sigue abriendose en el navegador" }
    } else {
        Write-Host ""
        Write-Host "Opcional - ver el mapa DENTRO del editor (hoy se abre en el navegador):"
        Write-Host "  code --install-extension ms-vscode.live-server"
        Write-Host "  o repite esto con -ConVisor. Ojo: no se integra con --open, es clic derecho."
    }
}

Write-Host ""
Write-Host "Listo. Todo proceso Python de este entorno queda cubierto."
Write-Host "La gate v3 viene en el mismo paquete, no necesita nada mas:"
Write-Host "  gb graph <src> --smells    (mapa advisory, funciona ya)"
Write-Host "  gb graph <src> --gate      (bloqueante; pide un .gb-boundaries propio del repo)"
