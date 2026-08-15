# ADR 0010 — Repos mixtos: los dos motores conviven (enmienda al 0009)

Fecha: 2026-08-15
Estado: aceptado
Enmienda: [ADR 0009](0009-multilenguaje-por-referencia.md), que sigue vigente en todo lo demás

## Contexto

El 0009 estableció dos motores —`symbols` (stdlib `ast`, Python) y `lenguajes`
(`ast-grep` por referencia, 16 lenguajes más)— y una regla de elección: **Python manda
cuando hay Python**. La implementación la leyó como exclusión:

```python
if informe.get("nodes") or not lenguajes.hay_codigo(root):
    return informe          # el otro motor no llega a correr
```

Consecuencia, medida sobre un banco de 2 `.py` + 2 `.ts` el 15-ago-2026:

```
$ gb graph <repo mixto>
2 modulos, 1 aristas internas, 0 ciclo(s)

Sin ciclos de imports.
```

Cuatro módulos en disco, dos en el informe, y **ni una línea diciéndolo**. El mismo
TypeScript analizado solo (`gb graph <repo>/web`) daba sus 2 módulos sin problema: no
era que no se pudiera leer, era que la presencia de un solo `.py` lo borraba.

Eso no es una limitación documentable: es un **falso verde**, exactamente lo que la
regla 9 persigue. Quien tenga backend Python y frontend TypeScript —la forma más común
de repo que existe— recibía un gate en verde sobre media casa. Y `not_covered`, el
mecanismo que este proyecto usa para declarar techos, estaba ahí al lado sin usar.

Lo agravaba que la exclusión vivía **duplicada** en dos sitios: `_analiza_simbolos` (el
mapa, `calls`, `who`) y `_constructor_de_grafo` (el gate). Arreglar uno solo habría
dejado el pre-commit ciego con el mapa ya corregido, que es peor que el fallo entero.

## Decisión

Los dos motores **conviven en un solo informe** cuando hay código de ambos. "Python
manda" pasa de significar *excluye* a significar *gana los empates*:

1. **Ambos conjuntos de nodos entran.** El grafo de un repo mixto tiene los módulos
   Python y los del resto de lenguajes.
2. **Ninguna arista entre familias.** Un `fetch("/users")` en TS no se ata a una vista
   de Flask: nadie puede derivarlo sin resolver el runtime, y fabricarlo sería el grafo
   *declarado* que el 0009 rechaza. Se dice en `not_covered`; no se finge.
3. **Los choques de nombre los gana Python.** `module_name` es idéntico en los dos
   motores, así que `web/app.py` y `web/app.ts` aterrizan ambos en `web.app`. El de
   Python conserva el nombre; el otro lleva su extensión pegada (`web.app:ts`). Dos
   nodos distinguibles: que uno se comiera al otro sería mentir en silencio.
4. **El gate va sobre hechos en cualquier lenguaje.** Un ciclo de imports entre ficheros
   TypeScript bloquea igual que uno de Python. Un ciclo es un hecho, no una opinión, y
   no depende del parser que lo encontró.
5. **`ast-grep` sigue siendo opcional.** Si falta, el informe de Python sale entero y su
   ausencia se declara en `not_covered`. Nunca tumba un análisis bueno.
6. **Quien no tenga otro lenguaje no paga nada.** `hay_codigo` es un `os.walk` sin
   invocar el binario; un repo Python puro no ejecuta `ast-grep` ni una vez. Medido:
   0.44 s sobre `src/` de este repo, dentro del presupuesto de la regla 2.

## Consecuencias

- `gb graph .` sobre **este** repo ahora incluye los 81 ficheros de `bancos/` (datos de
  conformidad de 17 lenguajes). Es factualmente correcto y ruidoso; el gate del proyecto
  corre sobre `src`, que es Python puro, así que la disciplina no cambia.
- Los contadores `calls_total`/`calls_resolved` se suman entre motores: sin eso, la
  cabecera del mapa daba un porcentaje que describía solo la mitad del grafo dibujado.
- `errors` no tiene la misma forma en los dos motores (dict por fichero en Python, lista
  de texto en el otro). Forzar una sobre la otra rompía a sus consumidores, así que los
  del motor no-Python se declaran en `not_covered` en vez de fusionarse.
- `gb tests` **no** cambia: sigue seleccionando tests de pytest. Un cambio en un fichero
  no-Python no encuentra tests que lo alcancen, y eso ya lo dice hoy sin maquillarlo
  ("la suite ENTERA... ningún test alcanza lo que cambiaste — eso es el dato, no un
  ahorro"). Correr suites de otros lenguajes está fuera de alcance y lo sigue estando.

## Criterio de muerte

Si la fusión produce nodos que nadie consulta, o si el ruido de mezclar familias hace
que alguien deje de mirar el grafo de su repo mixto, se revierte a un motor por raíz y
se declara la exclusión en la salida —nunca en silencio, que es el estado del que
venimos—.

## Evidencia

- Banco antes/después: 2 de 4 módulos → 4 de 4.
- Ciclo solo-TypeScript en repo mixto: gate `exit 0` → `exit 1`.
- [tests/test_fusion_multilenguaje.py](../../tests/test_fusion_multilenguaje.py): 7
  tests, 5 en rojo sin el cambio. Los otros 2 son guardianes de invariantes (latencia y
  "no inventar aristas") y por diseño pasan en ambos lados.
- Suite completa: 846 en verde. `gb graph src --gate`: exit 0.
