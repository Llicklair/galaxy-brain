"""El criterio ESTRICTO: la seleccion tiene que contener TODOS los tests que se ponen rojos.

El criterio que tenian los bancos era «si la suite entera se pone roja, la
seleccion tambien». Es el criterio de muerte de la familia y sigue siendo cierto,
pero **no es suficiente en un banco pequeno** — y eso no es teoria, se midio el
10-ago-2026 sobre Rust:

    la cascada estaba ROTA en `informe.linea -> factura.emitir` y el banco daba
    0/7 igualmente. Rompiendo `iva`, el test de `informe` fallaba de verdad y la
    seleccion no lo elegia; el veredicto salia verde porque OTROS tests ya
    estaban rojos y bastaba uno para que `rojo_sel` fuese True.

Con seis modulos encadenados casi cualquier rotura pone rojos varios tests, asi
que perder uno se tapa. El banco aprueba, la licencia se concede, y el dia que
alguien tenga UN solo test por camino el falso verde sale en produccion.

Lo que mide esto es la pregunta correcta:

    rojos   = los ficheros de test que se ponen rojos AL CORRERLOS UNO A UNO
    elegido = lo que `gb tests` selecciono (o todo, si cayo a todo)
    FUGA    = rojos - elegido      <- un test que falla y no se corre

Se corre fichero a fichero a proposito: parsear que test fallo de la salida de
cada runner seria un adaptador por lenguaje, frágil y distinto en cada uno,
cuando todos los bancos YA tienen la primitiva «corre estos ficheros y dime si
hay rojo». Cuesta N ejecuciones por rotura y son de sobra baratas al lado de
conceder una licencia que no toca.

**Techo declarado, y es un cambio de significado, no un detalle.** `rojo_full`
pasa a ser «alguno de los ficheros se pone rojo POR SI SOLO» en vez de «la suite
entera se pone roja». Para estos bancos es equivalente y mas preciso, porque sus
tests son independientes. Donde NO lo seria es en una suite con estado
compartido —un fixture global, un fichero que un test deja escrito para otro—:
ahi un test puede fallar solo en compania, y correrlo aislado lo daria verde. Un
banco con esa forma necesitaria otro instrumento, y este no lo detecta.
"""

import os


def _clave(ruta):
    """El nombre del fichero, que es lo unico que todas las partes comparten.

    `gb tests` devuelve `test/carrito.test.js` y el banco tiene la clave
    `carrito.test.js`; en Rust son `tests/carrito.rs` y `carrito.rs`. Comparar
    rutas completas haria que la fuga saliese siempre llena y el banco gritaria
    sin motivo, que es como se desactiva una comprobacion.
    """
    return os.path.basename(str(ruta).replace("\\", "/").rstrip("/"))


def rojos_uno_a_uno(ficheros, es_rojo):
    """Los ficheros que se ponen rojos POR SI SOLOS. `es_rojo(lista) -> bool`."""
    return {_clave(f) for f in ficheros if es_rojo([f])}


def fuga(seleccion, todo, ficheros_test, es_rojo):
    """(rojos, fugados). `fugados` no vacio = la cascada esta rota, aunque pase.

    `todo=True` significa que gb dijo «corre la suite entera»: entonces no puede
    fugarse nada por definicion, y decir lo contrario seria acusar a la caida
    segura de un fallo que no comete.
    """
    rojos = rojos_uno_a_uno(ficheros_test, es_rojo)
    if todo:
        return rojos, set()
    elegidos = {_clave(f) for f in (seleccion or ())}
    return rojos, rojos - elegidos


def linea_extra(rojos, fugados):
    """Lo que se imprime al lado del veredicto. Vacio cuando no hay nada que decir."""
    if fugados:
        return "  <<< CASCADA ROTA: %d rojo(s) sin elegir: %s" % (
            len(fugados), ", ".join(sorted(fugados)))
    return ""


def resumen(total_roturas, falsos, con_fuga, ahorro_pct, medidas=None):
    """El pie del banco. La fuga se dice SIEMPRE, tambien cuando es cero.

    Un banco que solo habla cuando falla no distingue «lo comprobe y esta bien»
    de «no lo comprobe», y esa diferencia es justo la que costo la licencia de
    Rust.

    `medidas` son las roturas en las que gb ESTRECHO de verdad. Sin licencia cae
    a la suite entera, no puede fugarse nada por definicion y el contador de fuga
    sale a cero — que se leeria «cascada exacta» cuando el hecho es «no he
    medido nada». Es el mismo cero mentiroso que el repo ya persigue en el gate,
    asi que se dice aparte en vez de contarse como aprobado.
    """
    if medidas == 0:
        estado = "cascada NO MEDIDA: cayo a la suite entera en las %d" % total_roturas
    elif con_fuga:
        estado = "CASCADA ROTA en %d rotura(s)" % con_fuga
    else:
        estado = "cascada exacta"
        if medidas is not None and medidas < total_roturas:
            estado += " en las %d medidas (%d cayeron a todo)" % (
                medidas, total_roturas - medidas)
    return "%d roturas - %d FALSOS VERDES - %s - ahorro medio %.0f%% de la suite" % (
        total_roturas, falsos, estado, ahorro_pct)
