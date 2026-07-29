# galaxy-brain v2 — Scope

Artefacto de la **Fase 1 (Restar)** de [galaxy-brain-v2-plan.md](galaxy-brain-v2-plan.md).
Diagnóstico de origen: [conclusiones-2026-07-29.md](conclusiones-2026-07-29.md).

Escrito el **29 julio 2026**. En español, como los dos documentos de los que deriva: esto es un
documento de decisión, no un doc de producto. El alcance de **v1** queda archivado y congelado en
[docs/v1/SCOPE.md](docs/v1/SCOPE.md) — histórico, no vigente.

---

## La frase

> **Cuando algo peta, v2 te dice dónde y con qué estado, sin que tengas que reproducirlo a mano.**

Una cosa. Determinista de arriba abajo. Devuelve algo en el mismo segundo.

### Alcance duro de v2

| | |
|---|---|
| **Lenguaje** | Python. Uno. |
| **Runtime** | Ejecución local. Uno. |
| **Fallo** | Excepciones no capturadas. Uno. |

Cualquier cuarto elemento en esa tabla es scope creep, no una mejora.

**Terminado (criterio comprobable, escrito antes de empezar):** ante un fallo real en un proyecto
tuyo, la consola te da el punto del fallo y el estado alrededor de él, y no has abierto el
depurador ni has vuelto a lanzar nada a mano.

---

## Lo que v2 NO hace

Explícito, con nombre y fichero. Nada de esto se borra — se aparta del camino de v2.

- **`/forja`** ([skills/forja](skills/forja), 368 líneas) — mete un modelo en el camino. Caro y lento
  por diseño; veredicto a los veinte minutos.
- **`/construye`** ([skills/construye](skills/construye), 188 líneas) + integración Spec Kit — igual,
  más ceremonia.
- **Los cuatro agentes del loop** ([agents/](agents/): finder, tester, fixer, evaluator, 163 líneas).
- **`/galaxy-brain:setup`** ([skills/setup](skills/setup), 97 líneas) — instalar companions no es el
  producto.
- **Los hooks de bloqueo** ([hooks/verify-invariants.js](hooks/verify-invariants.js),
  [scripts/external-gate.js](scripts/external-gate.js)) — blindan un camino (PR + no-auto-merge) por
  el que nunca ha pasado nadie. Ver inventario abajo.
- **El andamio de Spec Kit** ([scripts/constitution.js](scripts/constitution.js),
  [scripts/ears.js](scripts/ears.js), [scripts/evidence.js](scripts/evidence.js),
  [scripts/test-guard.js](scripts/test-guard.js)).
- **El rig de eval** ([eval/](eval/), 5.480 líneas, 271 ficheros) — no lo tira nadie, pero no es v2.
- **Las gates deterministas de acoplamiento y sobreingeniería** — son v3, ver abajo. Es la parte
  más difícil de dejar fuera y por eso está escrita aquí.
- **Multi-lenguaje, multi-runtime, integración con CI, UI.** No en v2. No "más adelante" tampoco:
  no antes de que la Fase 7 diga algo.

**Excepción a revisar, con honestidad:** [scripts/memory-global.js](scripts/memory-global.js) (memoria
cross-repo, inyectada en SessionStart) es la única pieza del repo que ya corre todos los días y
devuelve algo. No está en el camino de v2, pero tampoco estorba. Decisión: se queda funcionando, no
se desarrolla.

---

## Por qué esta lista y no otra

Inventario del repo, 29-jul-2026 (datos, no impresiones):

1. **40 commits en tres días de trabajo** (1 el 14-jul, 8 el 23, 31 el 24). Cinco días de silencio
   desde entonces. El filtro que pedía el plan — *¿la he usado en los últimos dos meses?* — no se
   puede aplicar: nada aquí tiene edad para responderlo.
2. **Cero PRs, cero ramas, cero worktrees.** Todo fue directo a `main`. El contrato entero de
   forja (*entrega un PR y para*) no se ha ejecutado ni una vez, ni sobre este repo.
   Las hard rules que lo protegen defienden un camino sin pisadas.
3. **El peso está invertido.** [CLAUDE.md](CLAUDE.md) dice *"the skills ARE the product"*:
   skills+agents+hooks = 930 líneas, el 5% de la masa. `scripts/` pesa el doble; `eval/`, seis veces
   más. El monstruo no es la forja, es el andamio.
4. **El único dato empírico no está en el repo.** El A/B de la báscula (t1/t2/t5/t6, rewards 8/8)
   vive en memoria; `eval/tasks/*` guarda prompt y verificador, ningún resultado.

Conclusión que se cae sola: por el criterio *¿me devolvió algo el mismo día?*, ninguna pieza de hoy
sobrevive. Cero PRs es cero entregas.

---

## v3 — las gates deterministas

No se construyen ahora. Se construyen **si y solo si** v2 pasa su prueba.

**Criterio de paso a v3 (los tres, no dos de tres):**

1. v2 lleva **catorce días** en uso sin que lo desactives ni una vez.
2. En esos catorce días te ha ahorrado reproducir un fallo a mano **al menos tres veces**.
3. La libreta de la Fase 0 existe y está escrita — es la que decide *qué* gate se construye primero.

**Fecha de revisión:** el día 14 contado desde el primer uso real de v2, no desde hoy. Se estampa
aquí cuando ocurra: `primer uso: ____-__-__` → `revisión: ____-__-__`.

Si el criterio no se cumple, no hay v3. No se renegocia el criterio: se acepta el resultado.

---

## Criterios de fracaso, escritos ahora que no duele

- **Si te descubres desactivando v2 o saltándotelo: no se blinda, se investiga por qué.** El abandono
  es el único termómetro honesto que ha dado este proyecto. Taparlo es perderlo.
- **Presupuesto de latencia, innegociable:** lo que corre en cada edición, < 1 s; lo que corre en cada
  commit, < 10 s. Lo que se salga de ahí muere en una semana. Ya pasó.
- **Si v2 no cabe en la frase de arriba al terminarlo, no está terminado: está creciendo.**

---

## Lo que este scope no resuelve

Que nadie lo necesite. v2 puede funcionar perfectamente y no producir un solo *"ahora no puedo vivir
sin esto"*. La única prueba de eso es la Fase 7 del plan, que no es técnica: ponerlo delante de una
persona que no seas tú, y aguantar lo que pase, incluido el silencio.
