# Conclusiones — 29 julio 2026

Notas de una conversación larga. No es un plan de trabajo, es un diagnóstico.
Escrito para que dentro de tres meses puedas comprobar si seguía siendo cierto.

---

## 1. El punto de partida

Llevas meses con la sensación de que ningún proyecto cuaja. Proyecto tras proyecto,
maratones largos, y la impresión de estar rozando algo sin llegar nunca.

La panacea, cuando la nombraste, resultó ser muy concreta:

> "Que alguien me diga: ahora no puedo vivir sin esto." Independientemente del dinero.

Eso importa porque es un criterio con dos propiedades:

- **Requiere a otra persona.** No lo puede producir construir mejor ni construir más.
- **Es más fácil que el dinero.** El dinero necesita un mercado. El wow necesita un usuario.

---

## 2. Los dos problemas que se sienten como uno

- **Problema A — se rompe.** El código no aguanta: fallos por todos lados, cosas
  a medio cerrar, nada suficientemente pulido.
- **Problema B — nadie lo necesita.** Aunque funcionara perfecto, falta el wow.

Desde dentro los dos salen por el mismo sitio ("mis proyectos no cuajan"), pero son
independientes. **Galaxy-brain solo ataca A.** El día que A esté resuelto del todo,
tendrás proyectos que no se rompen y la pregunta de siempre seguirá intacta.

Esto no es motivo para abandonar A. Es motivo para no esperar que A pague B.

---

## 3. El bucle meta

El patrón que apareció al mirarlo de frente:

> Tus proyectos se rompían → construiste un proyecto para que dejaran de romperse →
> ese proyecto también se rompe.

Galaxy-brain es un arnés de verificación sin verificar. La forja es un bucle que
arregla código y que nadie ha arreglado.

Cada vez que aparece la parte aburrida, el instinto dice *"construyo algo que se
encargue por mí"*. Y eso es otro proyecto, con su parte divertida y su parte aburrida.

**La salida es hacia abajo, no hacia arriba.** En vez de una herramienta que haga
fiables tus proyectos: un proyecto fiable, a mano, pequeño, aburrido.

---

## 4. Sobre el tamaño

Palabra tuya: *monstruo*.

Vigilar el scope de lo que añades y el tamaño de lo que ya tienes son cosas distintas.
El coste de pulir no crece con el tamaño, crece peor: cada parte roza con todas las demás.
"No ha sido suficiente para pulirlo" probablemente no significa que hayas pulido poco,
sino que **eso ya no se puede pulir a una mano.**

Y encaja con la panacea: nadie dice "no puedo vivir sin esto" de algo que no entiende
en cinco minutos. Un sistema de 900 commits hecho por una persona no puede recibir ese
wow por bien pulido que esté. El problema no es la calidad: es que no cabe en la cabeza
de quien lo mira.

**Palanca: restar, no pulir.** Sacar fuera la pieza que de verdad le quita una molestia
a alguien y dejar el resto donde está.

---

## 5. La idea buena de la conversación

Tuya, y aguanta el escrutinio:

> **Ecosistema determinista abajo. La IA como cereza, no como motor.**

Por qué es correcta:

- Lo que hacía cara y lenta a la forja no era el tamaño, era que **cada comprobación
  pasaba por un modelo**. Determinista = milisegundos y cero euros = puede estar
  siempre puesto. Que era justo lo que faltaba.
- Es adonde ha llegado la industria por su cuenta: tipos, tests, linters, CI abajo;
  la IA escribiendo código que tiene que satisfacerlos.
- Tenías el montaje del revés: IA de motor, determinismo de adorno.

### El techo, que existe

Una gate solo comprueba propiedades que sepas **enunciar**. Para algo nuevo, enunciarlas
con precisión *es* el diseño. Así que el arnés no elimina la parte difícil: la muda de
escribir código a escribir la especificación.

Los errores que sobreviven a un arnés perfecto son los de **"he construido correctamente
la cosa equivocada"**. No hay verificación que salve de querer lo que no era.

### La trampa

Lo determinista es barato de **usar**, no de **escribir**. Está hecho de aserciones,
invariantes, esquemas y tests aburridos — exactamente la materia que sueles saltarte.
La idea es correcta y su materia prima es el punto ciego histórico. Ahí es donde se cae,
no en el diseño.

---

## 6. Por qué falló la forja (y por qué "ecosistema" no lo arregla solo)

La forja está diseñada contra el **error**: generador ≠ evaluador, otro modelo, adversarial.
Buena defensa contra equivocarse.

Pero lo que te duele no son equivocaciones:

- La sobreingeniería **pasa** todas las gates.
- Los ficheros acoplados **pasan** todas las gates.
- Los tests los escribe el mismo proceso que escribió el código: comparten el malentendido.
  El verde no es prueba cuando examinando y corrector piensan igual.

Construiste el arnés en el eje que no te dolía. Es correcto y es malo: dos ejes distintos.

**Lo bueno:** varias de esas cosas sí son deterministas. El acoplamiento se mide (grafo de
imports, módulos tocados por cambio, fronteras cruzadas). La sobreingeniería tiene proxies
medibles (ficheros nuevos por feature, capas de indirección por camino de llamada). A un
modelo no le puedes preguntar de forma fiable "¿esto está sobrediseñado?", pero al grafo
sí le puedes contar aristas.

**Corolario sobre "hacerlo ineludible":** el único dato honesto que has tenido nunca sobre
galaxy-brain es que dejaste de usarlo. Blindarlo para que no se pueda esquivar no arregla
el motivo, lo tapa — y te deja sin el único termómetro que tenías.

---

## 7. La plantilla que ya funciona: context-mode

Es la única herramienta tuya que ha pasado la prueba del uso diario. Cinco propiedades:

1. **Determinista.** Hook + índice + sandbox. Ni una llamada a modelo en el camino.
2. **Intercepta, no pregunta.** No hay momento en el que alguien decida usarlo.
3. **Devuelve en el mismo segundo.** No dice "no": hace el trabajo y entrega algo más
   pequeño. La forja cobra veinte minutos y dinero para dar un veredicto después.
4. **Hace una sola cosa**, decible en una frase.
5. **Sus falsos positivos son inofensivos.** Coste de equivocarse asimétrico — eso decide
   la supervivencia a los meses.

Regla general derivada: **lo que solo dice que no es un impuesto; lo que devuelve algo se
usa solo.** Diseña para que se use por interés y deja los hooks para los días flojos.
Al revés no funciona.

Y: **si tienes que obligarte a usar tu propia herramienta, eso es un dato sobre la
herramienta, no sobre tu disciplina.**

---

## 8. El candidato: consola de errores sofisticada

Tu idea. Cumple las cinco propiedades y además:

- **Ataca tu propio dolor.** Dijiste que tus proyectos se rompen por todos lados, y al
  preguntarte dónde exactamente la respuesta era una sensación, no una lista. Esto es la
  máquina que convierte la sensación en lista.
- **Es honestamente determinista.** Un stack trace es un hecho. El estado en el momento
  del fallo es un hecho. El modelo solo entra después, a interpretar.
- **Tiene la forma que provoca el wow:** pequeño, inmediato, quita una molestia diaria.
  Las herramientas de depuración sí reciben "no puedo vivir sin esto".

**Dónde se muere esto:** mostrar lo que el runtime ya escupe es fácil (eso hace VS Code).
Lo sofisticado es capturar el estado alrededor del fallo — instrumentación, coste en
rendimiento, cuánto contexto guardar, y la tentación de soportar todos los lenguajes.
Esa tentación es la que fabrica monstruos.

**Un lenguaje. Un runtime. Un tipo de fallo.**

---

## 9. Sobre contexto y codificación

- El ahorro **nunca** viene del encoding, viene de no traer lo que no hacía falta.
  Lo que llega, llega como tokens, venga de donde venga.
- Comprimir a jerigonza suele **empeorar** el consumo: los tokenizadores están entrenados
  sobre lenguaje natural; el texto raro tokeniza peor. Y obliga a gastar razonamiento en
  descifrar, que es un coste que nadie mide.
- El "idioma eficiente" ya existe y se llama **vocabulario técnico preciso**. "Idempotente"
  cuesta un token y ahorra una frase.
- Lo más denso que existe es un **puntero** (`parser.py:412`): cinco tokens que sustituyen
  a quinientos, si hay cómo resolverlo. Eso es context-mode: no comprime, difiere.
- Lo que sí cambia todo es que el almacén tenga **forma**. Un grafo responde "¿quién llama
  a parse?" con ocho aristas; la prosa responde con cuatro ficheros enteros.
- Problema real, y no es el cifrado: **para pedir algo hay que saber que existe.** Hace
  falta un esqueleto barato siempre cargado — un mapa. Ese mapa es lo único que merece
  diseño cuidadoso.
- Bonus para un arnés: decodificador determinista ⇒ misma consulta, mismo resultado ⇒
  ejecuciones reproducibles. Vale más que el ahorro.
- **Y lo mejor:** un invariante sostenido por una gate determinista no necesita ir en
  contexto. No lo comprimes, lo haces innecesario.

---

## 10. Qué haría a un Claude notablemente mejor

Ordenado por impacto real, no por lo que mola:

1. **Un bucle de feedback rápido.** Con diferencia el primero. Si puedo ejecutar y ver el
   resultado en dos segundos, convergo. Si tarda diez minutos, adivino.
2. **Gates deterministas en un comando y en segundos.** Convierten suposiciones en hechos
   al instante.
3. **Un mapa, no una lectura.** Qué existe, para qué sirve, qué depende de qué.
4. **Los invariantes escritos.** Lo que más rompo es una regla que nadie me dijo. Si está
   en tu cabeza, te la voy a romper — no es falta de capacidad, es que no existe para mí.
5. **El porqué de lo ya decidido**, para no "arreglar" lo deliberado.
6. **Un entorno donde equivocarse salga barato** (worktrees, contenedores).
7. **Un criterio de terminado comprobable.** La causa número uno de sobreingeniería es no
   saber cuándo parar. Si "hecho" es difuso, sigo añadiendo porque añadir *parece* trabajo.
   Cura gratis: una frase escrita antes de empezar.

Nada de esto es más contexto, más herramientas ni más modelos.

---

## 11. Lo que queda por hacer, en orden

1. Durante dos semanas, cada vez que algo se rompa: **apuntarlo y seguir**, sin arreglarlo
   sobre la marcha. Esa libreta es la lista real, no la teoría.
2. No arrancar nada nuevo mientras tanto.
3. Elegir **una** pieza pequeña — la consola de errores es la candidata — y hacerla con las
   cinco propiedades de context-mode.
4. Ponerla delante de **una** persona que no seas tú. Aguantar el silencio si llega:
   ese silencio también es información, y es la que llevas meses sin recibir.

---

## Nota aparte — el registro forward de INVEST LL

Una semana es **un dato**, no un resultado. El bot decide una vez por semana; con una
observación no se distingue "funciona" de "esta semana subió bitcoin".

El riesgo real no es aburrirse: es **toquetear**. Cambias un parámetro y el reloj vuelve a
cero, porque las semanas anteriores ya no miden el sistema que tienes ahora.

Tres cosas legítimas que sí acortan el reloj:

- Más observaciones por semana (varias monedas), sabiendo que en cripto están correlacionadas
  y diez monedas no son diez datos independientes.
- Bajar el horizonte a diario: multiplica observaciones, pero es **otra estrategia**, no la
  misma más rápido. Más comisiones y más ruido.
- **Escribir hoy, por escrito, qué te haría parar.** Un tope de pérdida, un número de semanas
  malas seguidas. Escrito mientras no duele, para no inventarlo el día que duela.

Y los primeros meses el forward no mide la estrategia: mide la fontanería. Que la tarea
dispare, que Binance dé datos, que Hyperliquid ejecute, que el registro se escriba entero.
Eso sí es verificable en pocos ciclos.
