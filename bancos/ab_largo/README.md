# A/B L: largo recorrido — ¿con gb el codigo se enreda menos a la larga?

**La hipotesis** (de Marcos, por experiencia de uso, 1-oct-2026): con gb el codigo "se
espaguetifica menos": añade coherencia entre pasos. Ningun A/B anterior podia verlo: tenian de 1
a 4 pasos y median correccion, y el espagueti no rompe tests — encarece el paso siguiente.

**Aviso escrito antes.** Mirando la v2 (4 fases) parecio haber señal (aristas 10→18 sin gb, 10→14
con gb), y era de los TESTS: en el codigo de produccion fue 8→8 en los dos. Por eso aqui las
metricas de forma excluyen los modulos de test desde el principio.

## Diseño

**Proyecto.** `almacen` desde cero, con su encargo y las fases 2-4 de la v2, y despues **10
peticiones de cambio mas** (14 pasos), pensadas como la vida real de un producto: cada una
pequeña, varias que cruzan modulos, ninguna que pida reorganizar nada. Lista en `spec/`.

**Brazos.** Como la F: CON = `floor --init` + gb (gate, hooks, consola); SIN = repo vacio, sin gb.
Mismo modelo; cada paso, un `claude -p` aparte (sesion nueva: como un agente que llega otro dia).

## Metricas (por paso; se compara la PENDIENTE, no el final)

| metrica | que captura |
|---|---|
| aristas de produccion por modulo | acoplamiento: el espagueti en si |
| ciclos de imports | el nudo |
| ficheros de produccion tocados por paso | amplificacion del cambio: cuanto se extiende cada peticion |
| **coste del paso** ($, turnos) | el sintoma que importa: si se enreda, cada paso cuesta mas |
| funcion mas larga, lineas por funcion | la otra cara del espagueti |
| smoke de cada peticion + suite de la v2 | que el trabajo se hizo y no se rompio lo anterior |

**Tamaño.** 2 pares (14 pasos cada construccion). Coste estimado: 14 pasos x ~1 $ x 4 = ~55 $.
Se mide el primer par y se para a preguntar.

**Lo que puede decir.** Con 2 pares, solo una diferencia de pendiente clara y en los dos pares.
