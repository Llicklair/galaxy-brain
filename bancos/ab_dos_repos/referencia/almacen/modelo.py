"""Los tipos. No importa nada del paquete."""

from dataclasses import dataclass
from decimal import Decimal

TIPOS = ("entrada", "salida", "baja")


@dataclass(frozen=True)
class Movimiento:
    linea: int
    fecha: str
    sku: str
    tipo: str
    cantidad: int
    precio: Decimal


class EntradaInvalida(Exception):
    """El fichero no cumple el contrato. Exit 2."""


class StockInsuficiente(Exception):
    """Una salida o baja pide mas de lo que hay. Exit 3."""
