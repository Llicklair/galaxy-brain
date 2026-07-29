"""Punto de entrada del arranque automatico.

Lo importa el fichero `galaxybrain.pth` que se deja en site-packages, asi que
corre en TODO proceso Python del entorno. De ahi las dos propiedades que tiene
que cumplir sin excepcion:

1. No romper nunca. Un error aqui seria un error en el arranque de cualquier
   programa del venv, y eso mata la herramienta el primer dia.
2. No pesar. Sin imports de nada que no sea `sys`/`os`.

Propiedad 2 de la plantilla (intercepta, no pregunta): no hay ningun momento en
el que alguien decida usar esto.
"""

try:
    from .hooks import install as _install

    _install()
except BaseException:  # noqa: BLE001
    pass
