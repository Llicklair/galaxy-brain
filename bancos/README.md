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

## Los bancos

| Script | Qué mide | Necesita | Último resultado |
|---|---|---|---|
| `bench_js.py` | selección de tests en JS | `node` | **0/7 falsos verdes**, 52 % ahorro, cascada exacta |
| `bench_go.py` | ídem en Go, **multipaquete** (llamadas cualificadas) | `go` | **0/7**, 52 %, cascada exacta |
| `bench_rust.py` | ídem en Rust | `cargo` | **0/7**, pero cascada **incompleta** → sin licencia |
| `estres_tia.py` | roturas duras sobre un repo REAL | el runner de ese repo | 22/22 sin falsos verdes |
| `estres_mutacion.py` | roturas **sutiles** (mutación semántica) | ídem | 0/20 falsos verdes |

Los tres primeros generan su propio proyecto y no dependen de nada externo. Los dos últimos reciben
la ruta de un repo:

```bash
python bancos/bench_js.py                      # se genera solo
python bancos/bench_go.py
python bancos/bench_rust.py
python bancos/estres_tia.py       <ruta-worktree> [vistos|invisibles] [tope]
python bancos/estres_mutacion.py  <ruta-worktree> [tope]
```

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
