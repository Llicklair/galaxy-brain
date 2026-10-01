# A/B F: el mismo encargo vago, con `gb floor --init` y sin el

**La pregunta.** Los tres A/B anteriores (1-oct-2026, `docs/pruebas-de-uso.md`) dieron empate,
y lo que sostuvo la ley en los dos brazos fue que **estaba escrita** — en la spec o en
`.gb-boundaries`. Pero siempre se la dimos hecha a los dos. En un proyecto real nadie la da
hecha: o alguien la escribe, o no existe. `floor --init` es justo eso: un andamio que pide
alcance, criterio de terminado, ley de arquitectura y comandos que se ejecutan. ¿Cambia lo que
construye el agente?

## Diseño (decidido antes de construir nada)

**Encargo.** El contrato de `almacen` (formato CSV, los tres comandos, el JSON, los errores, el
rendimiento) — lo que la suite oculta necesita para juzgar — **sin** las secciones que ya son
"suelo": ni arquitectura, ni "lo que NO entra", ni criterio de terminado. Y luego las fases 2, 3
y 4 de `bancos/ab_dos_repos/spec`, igual que la v2.

**Brazos.** Mismo modelo, mismo prompt.
- CON: repo vacio + `gb floor --init` (AGENTS.md, SCOPE/ARCHITECTURE con sus marcas, pre-commit,
  hook de sesion, consola) antes de que llegue el agente. Nada mas: si rellena el andamio o no,
  es parte de lo que se mide.
- SIN: repo vacio. `gb` no existe (el mismo `gb` falso en el PATH que en la v3).

## Metricas

| metrica | como | por que |
|---|---|---|
| correccion por fase | suite oculta de la v2 (62 tests) en la foto de cada fase | la de siempre |
| regresiones | tests que pasaron en una fase y caen despues | lo que un buen suelo deberia evitar |
| **fuerza de SUS tests** | mutantes automaticos de SU codigo (`<`↔`<=`, `==`↔`!=`, `+`↔`-`, ...) que SU suite mata | la diferencia mas probable: `floor` empuja a criterio y tests antes del codigo |
| ley escrita | reglas en `.gb-boundaries`, reglas numeradas en ARCHITECTURE.md, marcas `gb:pendiente` que quedan | ¿el andamio se rellena o se ignora? |
| forma | ciclos de imports, fan-out maximo, numero de modulos (con gb como instrumento en los dos) | la deuda que nadie pidio evitar |
| coste | $ y minutos | — |

**Tamaño.** 2 pares para empezar (unos 15 $). Si hay señal, 4.

**Amenaza conocida.** El brazo CON recibe ~100 lineas mas de contexto: parte del efecto puede
ser "mas texto", no "gb". Es lo que `floor --init` ES, asi que se acepta y se dice.
