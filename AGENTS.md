# galaxy-brain — contexto para agentes

Una sola herramienta, `gb`: deriva del código un grafo de símbolos y módulos y hace
aterrizar sobre sus nodos todo hecho determinista que haga mejor al agente — dónde
petó (con su estado), qué tocó cada cambio, qué falta de base. El grafo es la columna
vertebral; la consola de errores fue la primera capa encima. Python puro, stdlib,
cero modelos en el camino caliente.
Las reglas de verdad viven en [CLAUDE.md](CLAUDE.md) (reglas duras y workflow),
[ARCHITECTURE.md](ARCHITECTURE.md) (ley de diseño) y [SCOPE.md](SCOPE.md) (qué
queda fuera). Esto es el arranque ejecutable; ante conflicto, mandan aquellos.

## Comandos

```
python -m pytest tests/ -q        # la suite (verde antes de commitear)
gb graph src --gate               # gate de ciclos de imports (exit != 0 = para)
git config core.hooksPath .githooks   # engancha el pre-commit (una vez)
```

El pre-commit corre suite + gate + `gb check --staged`. No se commitea en rojo.

## Trabajar con gb (dogfood)

- Falla un script/CLI: `gb show <id>` o `gb last --since 5m` ANTES de re-ejecutar
  con prints. El estado ya está capturado; usarlo es lo que se mide.
- Falla un test: `pytest -l` primero. pytest atrapa la excepción y gb NO la ve.
- ¿Quién llama a un símbolo?: `gb calls <símbolo> --depth 2` antes de grepear.
- Cola de errores: `gb list --pendientes` (las firmas en-silencio son testigos
  de regresión: se quedan en la libreta, no se repasan).
- Mapa vivo: `gb symbols --html --watch --refresco 3` — sin fichero escribe LA
  referencia: `mapa.html` en la carpeta principal, desde donde se trabaja. Un
  solo lienzo, un solo sitio; las dos puertas (`graph`/`symbols --html`)
  escriben el mismo mapa y delatan copias.

## Estructura

- `src/galaxybrain/` — un paquete. Núcleo: `cli` (entrada), `store` (capturas),
  `graph`/`symbols` (el grafo se DERIVA, nunca se declara), `changes` (ciclo del
  error), `viz` (el mapa HTML autocontenido), `floor` (el suelo), `capture` (el
  excepthook). Fronteras declaradas en `src/.gb-boundaries`.
- `tests/` — pytest plano, un fichero por tema, sobre repos git de verdad.
- `docs/` — evidencia (research-report, pruebas-de-uso). Español a propósito.

## Lo que rompe una revisión (resumen; la lista completa en CLAUDE.md)

- Consultar un modelo en capturar/guardar/mostrar/analizar.
- Pasarse del presupuesto: < 1 s por edición, < 10 s por commit.
- Cablear rutas/stacks del proyecto: todo se detecta en ejecución.
- Bloquear sobre proxies: solo un ciclo de imports nuevo o un cruce de frontera
  detiene un commit; lo demás informa.
- Vendorear: lo externo se integra por referencia (detección + instalador
  oficial + verificación).

## Trampas de esta máquina (Windows)

- PowerShell `Set-Content -Encoding utf8` escribe BOM y corrompe lo que otros
  leen; usar `[System.IO.File]::WriteAllText` o herramientas que escriban LF.
- Los ficheros del repo van en LF (`.editorconfig` manda); git avisa si tocas
  CRLF.

## Commits

`type: descripción` (`feat`/`fix`/`refactor`/`docs`/`chore`), un cambio lógico
por commit, y el porqué medido en el cuerpo del mensaje — los mensajes largos de
este repo son a propósito: son la libreta de decisiones.
