"""Tests del banco del enrutador. Desechables, como el banco."""

from experimento.capa import procesa


def test_procesa_suma_pares():
    assert procesa([(1, 2), (3, 4)]) == 12 + 34
