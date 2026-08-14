# galaxy-brain — Architecture

> La ley de diseño. El *qué* y sus límites están en [SCOPE.md](SCOPE.md); la evidencia medida, en
> [docs/research-report.md](docs/research-report.md); la libreta de uso, negativos incluidos, en
> [docs/pruebas-de-uso.md](docs/pruebas-de-uso.md).

---

## Tesis

Lo que mueve la aguja es **verificación determinista**. Meter un modelo en el camino que siempre
corre lo hace caro, lento y opcional — y lo opcional se abandona. Por eso galaxy-brain invierte la
colocación habitual:

> **Ecosistema determinista abajo. La IA como cereza, no como motor.**

No juzga: **reporta hechos.** Una excepción es un hecho. El estado en el momento del fallo es un
hecho. La forma del grafo de imports es un hecho. Lo que un diff le hizo a los tests es un hecho.
Reportar hechos no necesita juicio, y por eso puede ser instantáneo y no equivocarse de forma cara.

Y los hechos necesitan un sitio donde aterrizar: **el grafo**, símbolos y módulos derivados del
código en cada mirada, nunca declarados ni mantenidos a mano. Una captura se ancla a su nodo y
enseña a sus llamantes; un diff es una onda sobre las aristas; el gate del pre-commit y la
selección de tests salen de sus aristas; el cruce de firmas del rechazo también. El grafo es el
**motor**; la columna del producto es la **verificación del trabajo de agentes** — cada rama sola,
la unión y su choque semántico, la selección que decide qué correr, el estado del proceso que
murió. (Refocalizado el 13-ago-2026 con respaldo medido: `converge` 10/10 con agentes reales y dos
falsos verdes estructurales cazados por sus controles; el rechazo con llamadas exactas corrige 4/4
y la señal que solo informa, 0/6; el canvas midió empate dos veces y se retiró — y el 14-ago volvió
SOLO su renderer como salida de `who --html`, porque el uso diario del mapa era el dato que el A/B
no miraba; la maquinaria sigue retirada. Sentencia por capa en SCOPE.md; los datos, en la libreta,
13/14-ago.)

---

## La plantilla (validada por el uso)

context-mode es la herramienta que sobrevivió al uso diario. Sus cinco propiedades son la ley, no
una inspiración:

| # | Propiedad | Consecuencia de diseño |
|---|-----------|------------------------|
| 1 | **Determinista** | Cero llamadas a modelo en el camino caliente. Ni una. |
| 2 | **Intercepta, no pregunta** | No existe el momento en que alguien decide usarlo. |
| 3 | **Devuelve en el mismo segundo** | No emite veredictos: entrega material. |
| 4 | **Hace una sola cosa** | Cada comando es decible en una frase, o no entra. |
| 5 | **Sus falsos positivos son inofensivos** | El coste de equivocarse debe ser asimétrico. |

Regla derivada, y es la que decide la supervivencia a los meses:
**lo que solo dice que no es un impuesto; lo que devuelve algo se usa solo.**

---

## Las familias

Una sola herramienta, `gb`, con una sola filosofía. Los comandos caen en familias; un comando nuevo
tiene que caer en una de ellas o no entra:

- **Qué forma tiene** — `graph · symbols · calls`. **El motor.** El mapa de acoplamiento
  (imports, ciclos, hotspots), el grafo de símbolos (quién llama a quién, con su cobertura) y la
  consulta puntual (`calls`: llamantes y llamados de un símbolo con fichero:línea, también como hook
  de búsqueda). Las demás familias aterrizan sus hechos sobre estos nodos.
- **Dónde petó y con qué estado** — `last · list · show · on · off · status`. La consola de errores:
  captura excepciones no capturadas y el estado alrededor, para no reproducir el fallo a mano. Cada
  captura se ancla a su nodo del grafo y `show` enseña sus llamantes.
- **Qué le hizo cada cambio** — `check · tests`. Qué tocó un diff en los tests y en el acoplamiento
  (`check`), y qué tests hay que correr por lo que cambió (`tests`: el cierre de llamantes desde los
  símbolos del diff, con la suite entera como respuesta ante cualquier duda). `tests --run` es la
  única parte de gb que ejecuta algo del proyecto observado, y por eso es opt-in explícito.
- **Qué le falta de base** — `floor`. El andamiaje mínimo que un proyecto necesita antes de construir.
- **Qué se aprendió, cross-repo** — `memory`. La memoria durable entre repos y sesiones.

Todo determinista, cero modelos, cero dependencias más allá de la librería estándar de Python.

---

## Reglas de diseño (la ley)

1. **Cero modelos en el camino caliente.** Capturar, guardar, mostrar y analizar no consultan a nadie.
   Si una función necesita un modelo para funcionar, no es del camino caliente por definición.
2. **Devolver, no dictaminar.** Cada ejecución termina entregando algo que el usuario quería tener.
   Una salida cuyo único contenido es "no" viola esta regla.
3. **Presupuesto de latencia, innegociable.** < 1 s en el camino de cada edición; < 10 s en el de cada
   commit. Sobrepasarlo no es un bug de rendimiento: es una violación de arquitectura.
4. **Presupuesto de overhead sobre el proceso observado, medido no estimado.** La instrumentación tiene
   un techo escrito. Una consola que ralentiza el programa se apaga el primer día. (Medido: 6,4 ms de
   arranque, cero mientras el programa corre — ver [README.md](README.md).)
5. **Un runtime, un tipo de fallo — y dos motores de grafo, no uno genérico.** Ejecución local, y la
   consola captura **un solo tipo de fallo**: excepciones no capturadas, en Python, porque
   `sys.excepthook` no tiene equivalente portable. El **grafo** sí lee más: Python con `ast` de la
   stdlib, y otros 16 lenguajes con `ast-grep` **por referencia** — binario externo detectado y
   verificado, cero dependencias nuevas ([ADR 0009](docs/adr/0009-multilenguaje-por-referencia.md)).
   Dos motores que conviven; añadir un lenguaje es una entrada en una tabla de datos, y si hiciera
   falta tocar el motor, la tabla estaría mal diseñada. Cualquier otro eje nuevo es un cambio de
   scope, no una mejora, y va a [SCOPE.md](SCOPE.md) antes que al código.

   Dos guardas hacen que esto no degrade en «soportamos N lenguajes»: cada uno tiene su **sonda de
   conformidad** en la suite —que cazó 5 promesas falsas el día que se abrió el catálogo— y
   estrechar la selección de tests exige una **licencia medida con rojos reales**, que hoy solo
   tienen `js`, `ts`, `go`, `csharp`, `java`, `php` y `lua` — ocho contando Python. Un grafo de llamadas incompleto no cuesta ahorro: cuesta un verde falso.
6. **Los hechos se guardan crudos.** Excepción, traza y estado se persisten tal cual se capturan.
   Interpretar es un paso posterior, separado y descartable.
7. **Histórico local y append-only, fuera del repo observado.** El arnés nunca ensucia el proyecto que
   observa.
8. **La IA solo después del hecho, explícita y opcional.** Interpretar un fallo capturado o proponer un
   arreglo es una pregunta cara que el usuario lanza a mano; nunca está en el camino que siempre corre.
   Regla de colocación: si la respuesta se comprueba con una regla, es una gate; si no, es una pregunta
   al modelo, y entonces es cara, ocasional y visible. Cuando la IA entra, sigue valiendo
   **generador ≠ evaluador** (H2, 54/56 experimentos) — pero eso es la cereza, no el motor.
9. **Fallar en silencio hacia el lado seguro.** Si la captura falla, el programa observado sigue como si
   la consola no existiera. Nunca al revés (propiedad 5).
10. **El abandono es dato, no un bug a blindar.** Si dejas de usarlo, se investiga por qué; no se añade
    un hook que lo haga inevitable. Blindarlo tapa el motivo y destruye el único termómetro honesto que
    ha dado este proyecto.
11. **Los proxies informan, no bloquean.** Una señal sobre los tests (`check`) o sobre la
    sobreingeniería (`graph --smells`) es un **proxy**: un refactor legítimo la levanta. Gatear proxies
    fabrica falsos positivos, y una gate que chilla sin motivo acaba en `--no-verify`. Solo se **bloquea**
    sobre hechos —un ciclo de imports nuevo, un cruce de frontera declarado en `.gb-boundaries`—, nunca
    sobre proxies. Lo que hace inevitable una señal-proxy no es que bloquee: es que salga SIEMPRE,
    delante de quien decide, sin que haya que acordarse de pedirla.

---

## Otros principios (heredados, sin caducar)

- **Evidence over folklore.** Una decisión cita un hecho medido (H1–H11) o trae evidencia nueva a
  `docs/`. "Otros lo hacen" no es una razón.
- **No vendoring.** Lo externo se integra por referencia: detección + instalador oficial + verificación.
- **Nada project-specific.** Ni rutas ni stacks cableados; todo se detecta en ejecución.
- **Memoria en ficheros, sin vectores** (H5). Markdown durable y editable a mano, no un índice opaco.
- **El repo es la fuente canónica.** Se edita aquí, nunca en copias de `~/.claude/`.
