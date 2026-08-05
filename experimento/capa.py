"""El llamante intermedio: la arista que el grafo ve."""

from experimento.nucleo import calcula


def procesa(valores):
    """Suma calcula() sobre una lista de pares."""
    total = 0
    for a, b in valores:
        total += calcula(a, b)
    return total
