# Pruebas de uso — la libreta del arnés

Registro de cada prueba de uso real: qué se probó, qué salió y qué cambió por ello.
Existe porque [SCOPE.md](../SCOPE.md) arrastra una deuda concreta — el único dato empírico del
proyecto (el A/B de la báscula) vive en memoria y no en el repo. Un proyecto sobre evidencia no puede
tener la suya fuera, así que aquí se queda, incluida la que va en contra.

Formato: fecha, qué se probó, resultado, consecuencia. Los resultados negativos se escriben con el
mismo detalle que los positivos, o más.

---

## 2026-07-30 · Fase A (correlación) — **NEGATIVO en el caso principal**

**Qué se probó.** Si el estado capturado sirve para resolver un fallo sin volver a ejecutar el
programa. Montaje realista: agregación de facturas para un cierre mensual, con una línea malformada
(sin `cantidad`) escondida en la factura `F-2026-0042` entre cinco facturas correctas. El traceback
dice *dónde*; lo que hace falta saber es *en qué factura*.

### Resultado 1 — con pytest, no hay captura ninguna

```
$ python -m pytest -q          # el test falla con KeyError: 'cantidad'
$ gb last --since 120s
(sin capturas en los ultimos 120s para este proyecto)
exit=1
```

**Causa:** pytest **atrapa** la excepción del test. Nunca llega a `sys.excepthook`, así que el hook de
galaxy-brain no se ejecuta y no hay nada que guardar. **El fallo más común del bucle de trabajo de un
agente — un test que falla — está fuera de cobertura**, y eso no estaba escrito en ninguna parte
cuando se justificó la Fase A.

### Resultado 2 — y aunque capturara, `pytest -l` ya da más

Salida de `pytest -q -l`, de serie, sin instalar nada:

```
facturas.py:11: in <dictcomp>
    f       = {'id': 'F-2026-0042', 'lineas': [{'cantidad': 1, 'precio': 250.0}, {'precio': 40.0}, ...]}
facturas.py:7:  in total_factura
    factura = {'id': 'F-2026-0042', ...}
facturas.py:4:  in linea_total
    linea   = {'precio': 40.0}
```

Con eso el bug queda identificado entero: factura `F-2026-0042`, segunda línea, falta `cantidad`.

### Resultado 3 — como script sí captura, pero la vista por defecto rinde menos

El mismo bug lanzado como script (sin pytest) sí se captura: el aviso sale con su
`gb show <id>` y `gb last --since 60s` devuelve exit 0. Pero la vista por defecto muestra **solo el
frame más interno**:

```
      linea = {'precio': 40.0}
```

**No dice qué factura.** Ese dato está uno o dos frames más afuera, detrás de `--full`. Sobre
exactamente los mismos datos, `pytest -l` entregó más respuesta útil que `gb last`.

El supuesto de diseño *"se conservan los frames más internos: ahí está el fallo"* acierta en el
**dónde** y falla en el **con qué**: el estado que identifica el caso concreto suele vivir más arriba.

### Consecuencias

1. **La Fase A se estrecha** a lo que de verdad cubre: excepciones no capturadas (scripts, CLIs,
   servidores, procesos largos). No tests. Escrito en [PLANTEAMIENTO.md](../PLANTEAMIENTO.md).
2. **Para tests se adopta `pytest -l` por referencia**, no se construye nada. Es la regla 7 de
   [CLAUDE.md](../CLAUDE.md) aplicada al pie de la letra: lo externo se integra por referencia. Coste:
   una línea. Construir una captura para pytest habría sido reimplementar un flag que ya existe — la
   sobreingeniería exacta que este proyecto dice combatir.
3. **Queda abierto, sin tocar:** si `gb last` debería mostrar por defecto también los locales del
   frame más externo que sea del usuario. Es un cambio sugerido por evidencia, pero antes de pulir
   toca preguntar qué se resta.

**Coste de la prueba:** cinco minutos. **Lo que ahorró:** cinco sesiones midiendo un criterio que
medía el caso equivocado.
