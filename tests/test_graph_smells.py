"""Proxies de sobreingeniería (increment 4): abstracciones abc.ABC con <=1
implementación. Es ADVISORY a propósito — estos proxies son opiniones y gatearlos
sería el error de la forja. Estos tests fijan (a) qué se detecta y (b) que la gate
NUNCA bloquea por ellos."""

import os

from galaxybrain import graph

ABC_STORE = "from abc import ABC, abstractmethod\nclass Store(ABC):\n    @abstractmethod\n    def get(self): ...\n"


def _write(root, rel, content):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def test_abc_con_una_sola_impl_se_reporta(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/base.py", ABC_STORE)
    _write(root, "app/impl.py", "from app.base import Store\nclass FileStore(Store):\n    def get(self): return 1\n")

    reported = graph.overengineering(root)
    assert any(a["class"] == "Store" and a["impls"] == 1 for a in reported)


def test_abc_sin_impl_se_reporta(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/base.py", ABC_STORE)

    reported = graph.overengineering(root)
    assert any(a["class"] == "Store" and a["impls"] == 0 for a in reported)


def test_abc_con_dos_impls_no_se_reporta(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/base.py", ABC_STORE)
    _write(root, "app/a.py", "from app.base import Store\nclass A(Store):\n    def get(self): return 1\n")
    _write(root, "app/b.py", "from app.base import Store\nclass B(Store):\n    def get(self): return 2\n")

    assert not any(a["class"] == "Store" for a in graph.overengineering(root))


def test_protocol_se_excluye(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/proto.py", "from typing import Protocol\nclass Reader(Protocol):\n    def read(self) -> str: ...\n")

    # Un Protocol con 0 subclases explícitas es NORMAL (tipado estructural): no es smell.
    assert not any(a["class"] == "Reader" for a in graph.overengineering(root))


def test_abstractmethod_sin_base_abc_se_detecta(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/x.py", "from abc import abstractmethod\nclass Thing:\n    @abstractmethod\n    def go(self): ...\n")

    assert any(a["class"] == "Thing" for a in graph.overengineering(root))


def test_gate_no_bloquea_por_sobreingenieria(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/base.py", ABC_STORE)  # abstracción con 0 impls

    from galaxybrain import cli

    # --smells la muestra, pero --gate NO falla por ella: es advisory, no un veredicto.
    assert cli.main(["graph", root, "--smells", "--gate", "--color", "never"]) == 0


def test_smells_off_no_computa_abstracciones(tmp_path):
    root = str(tmp_path)
    _write(root, "app/__init__.py", "")
    _write(root, "app/base.py", ABC_STORE)

    report = graph.analyze(root)  # sin --smells
    assert report["abstractions"] == []
    assert report["smells"] is False
