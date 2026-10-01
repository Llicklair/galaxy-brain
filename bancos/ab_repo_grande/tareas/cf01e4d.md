# Panel de operador HTML de solo lectura (`guardia informe`)

## Problema

No hay frontend. Para saber si la capa de IA está congelada, qué decisiones se han tomado y si
el log de auditoría sigue íntegro, el operador tiene que leer JSONL a pelo y correr varios
comandos. Necesitamos una página HTML estática que lo muestre todo de un vistazo.

Ojo: el log contiene texto que escribió el atacante (cmdlines, etiquetas con inyecciones). Si
se pinta tal cual en HTML, una etiqueta con `<script>` se ejecutaría en el navegador del
operador.

## Comportamiento esperado

- Una función de renderizado **pura** recibe el estado del interruptor, las entradas del log y
  el veredicto de integridad ya leídos, más la marca de "generado en", y devuelve el HTML
  completo como `str`. No lee disco ni reloj.
- La página muestra:
  - El estado de la capa: si está congelada, el texto `CONGELADA` y una nota que contenga
    `T0/T1 siguen protegiendo`; si no, el texto `operativa` (y en ese caso la palabra
    `CONGELADA` no debe aparecer en ningún sitio de la página). También el motivo, desde y actor.
  - La integridad de la cadena: si está intacta, `intacta` y el número de entradas; si está
    rota, `CADENA ROTA`, la posición de ruptura como `#<n>` y un aviso que contenga
    `NO es de fiar`.
  - Una línea de tiempo con las entradas (seq, ts, actor, evento y sus datos), **lo más nuevo
    arriba**. Cada actor (`humano`, `ia`, `automata`, `sistema`) con su distintivo visual.
  - Con el log vacío, en vez de una tabla en blanco, un texto que contenga `Sin entradas`.
- **Todo** valor dinámico (motivo, evento, actor, datos, ts...) se escapa para HTML: el payload
  crudo `<script>...` nunca aparece; aparece como `&lt;script&gt;`.
- La CLI gana el subcomando `informe`: lee el estado y el log del directorio de control, escribe
  el HTML y devuelve 0. Imprime ruta, número de entradas y estado de la cadena; si está rota,
  avisa por stderr (sigue devolviendo 0). No modifica nada del plano de control.

## Interfaz que debe existir

- Módulo nuevo `guardia.informe` con
  `render(estado, entradas, veredicto, generado: str) -> str`, donde `estado` es un
  `guardia.kill_switch.Estado`, `entradas` una lista de `guardia.auditoria.Entrada` y
  `veredicto` un `guardia.auditoria.Veredicto` (todos existentes; el renderizado solo usa sus
  atributos públicos).
- El HTML empieza por `<!doctype html>` (en minúsculas).
- CLI: `main(["--control", <dir>, "informe"])` y
  `main(["--control", <dir>, "informe", "--salida", <fichero.html>])`, ambos devuelven `0`.
- Sin `--salida`, el fichero por defecto es `<control>/informe.html` (crear directorios si hace
  falta).

## Fuera de alcance

- Servidor web, JavaScript, refresco automático o cualquier acción desde el panel (congelar,
  confirmar siguen en la CLI).
- Dependencias externas.
