# Cómo se rompe un instrumento

Este repo mide más de lo que construye: cinco bancos, dos oráculos, sondas de conformidad, escalera.
El 10 y 11 de agosto de 2026 salieron **catorce fallos en una sola sesión**, y el reparto es el dato:

> **Once eran del instrumento. Tres eran del producto.**

Un fallo del producto se ve: algo no funciona. Un fallo del instrumento **sale en verde** y encima da
un número, así que se archiva como conocimiento. Por eso van aquí clasificados por mecanismo — no
como anécdotas, sino como las formas concretas en que una medida miente.

Cada uno trae el caso real y **la comprobación que lo habría cazado**, que es lo único accionable.

---

## 1. Media conexión: la regla gobierna una de las dos cosas que debía

La más frecuente: **seis de los catorce**. Una regla correcta, implementada sobre una de sus dos
mitades. Siempre se lee como verde, porque la mitad cubierta funciona.

| caso | la mitad que faltaba |
|---|---|
| `vigorOnda` apagaba la **onda** de las aristas, no el **aro** del nodo | un mapa estático de hace horas pintaba «hay alguien aquí ahora» |
| la puerta de opacos cubría *«cambió el símbolo opaco»*, no *«el camino PASA por uno»* | 93 falsos verdes, todos por ahí |
| la huella de datos rancios hasheaba `src`, no `tests` | los dos extremos de una arista son nodos |
| el gate bloqueaba por `call_violations` y la escalera no lo leía | la máquina aceptaba lo que el humano no podía commitear |
| el filtro previo de agentes miraba dos de las tres fuentes de presencia | un árbol limpio con commit reciente no llegaba a mirarse |
| la opacidad grepeaba el fichero de test, no a **quien el test llama** | 60 falsos verdes al mirar dentro de los subprocesos |

**La comprobación:** al escribir una regla, enumerar en voz alta **todo lo que debería gobernar** y
buscar cada sitio. Si la regla vive en un `if`, ¿hay otro `if` que decide lo mismo en otro lado?

---

## 2. El instrumento copia la conducta que juzga

Entonces **no puede detectar que cambie**. No da un número falso: **congela el veredicto**.

El oráculo de cobertura llevaba dentro `if qual in por_valor: ahorros.append(0.0); continue` —
replicando el «corre todo» de la selección. Cuando la selección dejó de caer, el oráculo siguió
saltándose esos símbolos y dio **27% y 34 símbolos, idéntico a antes del cambio**. Se leía como «no
ha servido de nada».

**La comprobación:** un número *idéntico* antes y después es más sospechoso que uno malo. Dos
mediciones reales rara vez coinciden al punto; cuando coinciden, normalmente una no se hizo.

---

## 3. El instrumento acusa al producto de sus propios puntos ciegos

La primera medida de precisión del grafo dio **≤35% de aristas sospechosas**. Dos confusores, los
dos del instrumento:

- **Dobles de test.** La primera acusada era una llamada incondicional en la primera línea de una
  función. La arista es cierta; el test hacía `monkeypatch.setattr` del llamado.
- **El punto ciego del perfilador.** Solo miraba llamados bajo `src/galaxybrain`, así que toda arista
  hacia `bucle.*` o `bancos.*` era **inobservable por construcción**.

Descontados los dos: **≤3%**.

**La comprobación, y es la regla más útil que salió:** los dos confusores hacían el número *peor*
cuanto **mejor** estaban el test y el reparto del código.

> **Si una medida empeora al mejorar lo medido, el defecto está en la medida.**

---

## 4. La comprobación que no puede fallar

Verificar el arreglo con un sabotaje es la buena práctica de este repo. Pero el sabotaje se aplicaba
con un `replace()` cuyo patrón **no casaba** (una continuación de línea), y el `print` de éxito era
incondicional. El sabotaje nunca ocurrió y el test «sobrevivió»: habría concluido que el test no
servía.

Y tres veces seguidas: un detector de procesos que buscaba `--watch` en la línea de comandos **casaba
con su propio proceso**, porque el texto del filtro contenía la palabra. Reporté dos veces «el watch
sigue vivo» cuando había muerto.

**La comprobación:** un sabotaje tiene que **fallar el test**. Si no falla, lo primero que se mira no
es el test: es si el sabotaje llegó a aplicarse. Y todo detector se prueba contra un caso donde debe
dar **cero**.

---

## 5. El cero que significa «no he mirado»

Se lee igual que «está limpio», y es el modo de fallo peor de una gate.

- Un lenguaje **sin licencia** cae a la suite entera: no puede fugarse nada, el contador sale a cero,
  y el pie decía «cascada exacta» cuando el hecho era «no he medido nada».
- La primera versión del criterio estricto marcó a Ruby con **cascada ROTA 4/4** — Ruby cae a todo
  *por diseño*: acusaba a la caída segura de un fallo que no comete.
- `bench_multi` se callaba entero si faltaba el intérprete, cuando **la mitad medible** (la cascada,
  que es la que falló en Rust) no necesita runtime.

**La comprobación:** distinguir siempre en la salida «lo comprobé y está bien» de «no lo comprobé».
Son la misma cifra y significados opuestos.

---

## 6. Datos rancios: la medida sobrevive al árbol que midió

Los pares se anotan por `(fichero, línea)`. Si el árbol cambia entre la captura y el contraste, cada
par apunta a otro símbolo: **el informe sale lleno de hallazgos inventados**, con pinta de trabajo
pendiente.

Costó tres tiradas acertar el alcance, y las dos primeras fallaron por lados opuestos: hashear solo
`src` dejaba fuera `tests`; hashear el árbol entero invalidaba los datos al editar un banco que nadie
ejecuta.

**La comprobación:** un instrumento que puede mentir en silencio tiene que **negarse a hablar**. Y el
alcance de esa negativa es *exactamente lo que los datos nombran*, ni más ni menos.

---

## Lo que queda

Los tres fallos del **producto** de esos días —el aro que no envejecía, la puerta de opacos a medias,
la opacidad indirecta— se encontraron **todos** con instrumentos nuevos, no leyendo código. Y los
once del instrumento se encontraron porque el número no cuadraba con lo que se esperaba.

De ahí la única conclusión que vale para el próximo:

> **Cuando un instrumento nuevo acusa, el primer sospechoso es el instrumento.** No por prudencia:
> porque en esta muestra acertó el producto 3 veces de 14.
