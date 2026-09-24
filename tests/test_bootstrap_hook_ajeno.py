"""`gb on` nombra al hook que pisa el suyo, en vez de culpar a la instalacion.

Medido en CI el 24-sep-2026: en el Python del sistema de Ubuntu,
/usr/lib/python3.12/sitecustomize.py instala el excepthook de apport DESPUES
de los .pth, y `gb on` decia «¿esta el paquete instalado?» — que lo estaba.
Aqui se reproduce con un sitecustomize propio por PYTHONPATH.
"""

from galaxybrain import bootstrap


def test_un_sitecustomize_que_pisa_el_hook_se_nombra(tmp_path, monkeypatch):
    (tmp_path / "apport_falso.py").write_text(
        "def gancho(t, v, tb):\n    pass\n", encoding="utf-8")
    (tmp_path / "sitecustomize.py").write_text(
        "import sys, apport_falso\nsys.excepthook = apport_falso.gancho\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    ok, detalle = bootstrap.verify()
    assert not ok
    assert "apport_falso" in detalle and "venv" in detalle, detalle
