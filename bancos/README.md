# Bancos — lo que decide si una capa vale

Estos cinco scripts han encontrado más fallos que la suite entera. No son tests: **necesitan un
runner externo instalado**, tardan minutos y se corren a mano, cuando hay algo que decidir.

La diferencia con `tests/` importa. Un test comprueba una propiedad contra el mismo grafo que se está
juzgando, lo cual es circular para la pregunta que importa aquí: *¿la selección de tests deja pasar
un árbol roto?* Eso solo lo contesta **un rojo de verdad**, y por eso cada banco usa el runner nativo
del lenguaje —`node --test`, `go test`, `cargo test`, `pytest`— y ninguno necesita instalar
dependencias del ecosistema.

## El protocolo, igual en los cinco

1. romper un símbolo a propósito
2. preguntar a `gb tests` qué correr
3. correr **solo** su selección
4. correr la suite entera
5. si la entera se pone roja y la selección no → **FALSO VERDE**, y la capa no vale

Un falso verde no es "menos ahorro": es la gate aprobando con el árbol roto. Es el único criterio de
muerte de esta familia ([SCOPE.md](../SCOPE.md)).

**Y ese criterio es necesario pero NO suficiente en un banco pequeño.** Medido con Rust el
10-ago-2026: con seis módulos encadenados, perder un test que sí estaba impactado se tapa con que
otro caiga rojo — el veredicto sale verde y la cascada está rota igualmente.

Por eso los bancos ya no comparan booleanos. [`estricto.py`](estricto.py) corre **cada fichero de
test por separado** para saber cuáles se ponen rojos de verdad, y exige que la selección los
**contenga todos**:

```
rojos   = los tests que se ponen rojos al correrlos uno a uno
elegido = lo que `gb tests` seleccionó
FUGA    = rojos - elegido      <- un test que falla y no se corre
```

Se corre fichero a fichero a propósito: parsear qué test falló de la salida de cada runner sería un
adaptador por lenguaje, frágil y distinto en cada uno, cuando todos los bancos ya tienen la primitiva
*«corre estos ficheros y dime si hay rojo»*.

**Control positivo, porque un detector sin él es decoración:** con la licencia puesta y ANTES del
arreglo, Rust daba `0 FALSOS VERDES` y el criterio estricto marcó `CASCADA ROTA en 5 rotura(s)`,
señalando `informe.rs` — exactamente la arista que faltaba.

**Y el cero que no se cuenta como aprobado:** un lenguaje sin licencia cae a la suite entera, no puede
fugarse nada y el contador sale a cero. Eso se lee «cascada exacta» cuando el hecho es «no he medido
nada», así que el pie lo dice aparte: `cascada NO MEDIDA: cayó a la suite entera`.

**La mitad que se puede medir sin intérprete.** El rojo/verde lo da el runtime y sin él no hay banco;
la **cascada** —a cuántos tests llega gb desde lo que se rompió— sale del grafo y se mide en
cualquier máquina. Y es justo la mitad que falló en Rust. Por eso `bench_multi.py` ya no se calla
cuando falta el binario: comprueba la cascada contra la esperada (`3-2-1-1`) y lo dice. **No es una
licencia** y la salida lo repite — para eso hacen falta rojos reales.

Un lenguaje **sin licencia** cae a la suite entera *por diseño*: ahí no hay cascada que medir y
marcarlo como roto sería acusar a la caída segura. La licencia se lee de `LENGUAJES`, no se copia.

Los oráculos de abajo existen porque un banco escrito por quien lo mide no puede cerrar esta pregunta.

**Antes de escribir un banco nuevo:** [docs/como-se-rompe-un-instrumento.md](../docs/como-se-rompe-un-instrumento.md).
De catorce fallos en la sesión del 10–11 de agosto, **once eran del instrumento y tres del producto** —
y los del instrumento salen todos en verde.

## Los bancos

| Script | Qué mide | Necesita | Último resultado |
|---|---|---|---|
| `bench_js.py` | selección de tests en JS | `node` | **0/7 falsos verdes**, 52 %, cascada exacta |
| `bench_go.py` | ídem en Go, **multipaquete** (llamadas cualificadas) | `go` | **0/7**, 52 %, cascada exacta |
| `bench_csharp.py` | ídem en C#, **métodos + llamadas cualificadas por clase** | `dotnet` + NuGet en caché | **0/7**, 52 %, cascada exacta |
| `bench_rust.py` | ídem en Rust | `cargo` | **0/7**, 52 %, cascada exacta → **licencia ganada** el 10-ago |
| `bench_multi.py` | java, php, lua y ruby con una sola tabla | su intérprete | cascada **exacta 4/4** en java/php/lua **sin runtime** (ver abajo) |
| `experimento_correccion.py` | si el grafo mejora la **corrección** de un agente (A/B, suite oculta) | `claude` CLI · **gasta cuota** | 3/3 y 3/3 — **sin efecto** en una tarea que cabe en contexto |
| `estres_tia.py` | roturas duras sobre un repo REAL | el runner de ese repo | 22/22 sin falsos verdes |
| `estres_mutacion.py` | roturas **sutiles** (mutación semántica) | ídem | 0/20 falsos verdes |
| `oraculo_cobertura.py` | la **selección** contra la verdad de ejecución, sobre ESTE repo | `coverage` | **0 falsos verdes** de 332 símbolos, 27 % ahorro |
| `oraculo_aristas.py` | las **aristas** contra las llamadas que ocurren de verdad | nada (stdlib) | recall 96 %, **0 huecos sin puerta**, precisión ≥ 97 % |

Los dos oráculos son la misma pregunta a dos alturas. El de cobertura dice **qué** se pierde (ficheros
de test); el de aristas dice **por qué** (la llamada que el AST no vio). El primero dejó 91 falsos
verdes cuyas dos causas hubo que encontrar leyendo a mano; el segundo automatiza esa lectura.

Ninguno de los dos sale del grafo que juzga, que es la única razón por la que valen: los cinco bancos
de arriba fabrican la rotura en un repo escrito por quien escribe el banco, y los cinco daban 0/7
mientras el oráculo encontraba 118 fallos reales.

Los tres primeros generan su propio proyecto y no dependen de nada externo. Los dos últimos reciben
la ruta de un repo:

```bash
python bancos/bench_js.py                      # se genera solo
python bancos/bench_go.py
python bancos/bench_rust.py
python bancos/estres_tia.py       <ruta-worktree> [vistos|invisibles] [tope]
python bancos/estres_mutacion.py  <ruta-worktree> [tope]
python bancos/oraculo_cobertura.py --correr    # 1) la suite bajo coverage; 2) el contraste
```

El oráculo es distinto de los demás y por eso está el último: los otros cinco **fabrican** una
rotura y comprueban que la selección la atrapa, sobre un repo pequeño y con la verdad escrita por
quien escribió el banco. El oráculo no fabrica nada. Corre la suite real de este repo con
`coverage` y contextos dinámicos, que registra **qué test ejecutó de verdad cada línea**, y usa eso
como verdad para todos los símbolos a la vez. Es la única medida de la selección que no sale del
grafo que se está juzgando.

## Lo que han encontrado, que es el argumento para conservarlos

- Las aristas `CALLS` salían del **módulo** y no de la función que llama, así que la cadena
  transitiva se cortaba: romper el símbolo más profundo seleccionaba 1 test de los 5 que dependían de
  él. No daba falso verde **de puro azar**, porque la rotura era dura.
- Los nodos no-Python salían con `end: None`, así que ningún hunk caía dentro de un símbolo y **todas**
  las roturas caían a "corre la suite entera": seguro y con 0 % de ahorro.
- En Rust, las llamadas dentro de un macro son invisibles (`format!("...", emitir(xs))`), lo que
  producía **sub-selección** — y de ahí salió la licencia `tia`, que exige banco medido antes de
  dejar que un lenguaje estreche.
- En Go, las llamadas cualificadas (`paquete.Funcion()`) se descartaban: su grafo salía con **cero
  aristas entre paquetes**.

Ninguno de los cuatro lo encontró la suite.

## Cómo se lee un banco sin engañarse

- **Un cero no se reporta sin control positivo.** Un instrumento mudo y un repo limpio dan la misma
  cifra. Los cinco scripts empezaron dando resultados falsos por leer mal su propia salida —
  `d["signals"]` en vez de `d["flags"]`, o interpretar `tests: []` con `todo: True` como "no corras
  nada" cuando significa **córrelo todo**.
- **`[cayo a todo]` en la columna de veredicto es seguro, no bueno.** Significa 0 % de ahorro.
- **Más ahorro no es mejor.** Rust dio 64 % frente al 52 % de JS y Go, y precisamente por eso se miró
  de cerca: el ahorro extra venía de perder tests que sí estaban impactados.
