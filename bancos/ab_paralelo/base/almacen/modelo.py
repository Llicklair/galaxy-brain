"""Los tipos. No importa nada del paquete."""

from dataclasses import dataclass
from decimal import Decimal

TIPOS = ("entrada", "salida", "baja", "traspaso", "devolucion")


@dataclass(frozen=True)
class Movimiento:
    linea: int
    fecha: str
    sku: str
    tipo: str
    cantidad: int
    precio: Decimal
    almacen: str = "central"
    destino: str = ""
    ref: int = 0


class EntradaInvalida(Exception):
    """El fichero no cumple el contrato. Exit 2."""


class StockInsuficiente(Exception):
    """Una salida, baja o traspaso pide mas de lo que hay. Exit 3."""
