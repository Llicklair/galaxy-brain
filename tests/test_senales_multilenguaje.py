"""Las señales de `check` en los lenguajes que no son py/js/go/rb.

Auditoria del 24-sep-2026: TEST_FILE, TEST_DEF, ASSERTION y SKIP_ADDED solo
conocian pytest, jest, go y rspec. Borrar un `@Test` de JUnit, quitar un
`assert_eq!` de Rust o saltarse un `[Fact]` de xUnit no daba ninguna señal.
"""

import pytest

from galaxybrain import changes


def _diff(ruta, quitadas=(), puestas=()):
    lineas = ["diff --git a/%s b/%s" % (ruta, ruta), "--- a/%s" % ruta, "+++ b/%s" % ruta,
              "@@ -1,%d +1,%d @@" % (len(quitadas) or 1, len(puestas) or 1)]
    lineas += ["-" + q for q in quitadas] + ["+" + p for p in puestas]
    return "\n".join(lineas) + "\n"


def _senales(diff):
    return {s["signal"] for s in changes.test_signals(changes.parse_diff(diff))}


@pytest.mark.parametrize("ruta,quitadas,senal", [
    ("src/test/java/app/SumaTest.java", ["    @Test", "    void suma() {"], "TEST_REMOVED"),
    ("tests/SumaTests.cs", ["    [Fact]", "    public void Suma() {"], "TEST_REMOVED"),
    ("tests/suma.rs", ["#[test]", "fn suma() {"], "TEST_REMOVED"),
    ("Tests/SumaTests.swift", ["    func testSuma() {"], "TEST_REMOVED"),
    ("tests/SumaTest.php", ["    public function testSuma() {"], "TEST_REMOVED"),
    ("test/suma_test.exs", ['  test "suma" do'], "TEST_REMOVED"),
    ("tests/suma.rs", ["    assert_eq!(suma(1, 2), 3);"], "ASSERT_REMOVED"),
    ("src/test/java/app/SumaTest.java", ["        assertThat(suma(1, 2)).isEqualTo(3);"], "ASSERT_REMOVED"),
    ("Tests/SumaTests.swift", ["        XCTAssertEqual(suma(1, 2), 3)"], "ASSERT_REMOVED"),
    ("tests/SumaTests.cs", ["        Assert.Equal(3, Suma(1, 2));"], "ASSERT_REMOVED"),
])
def test_quitar_un_test_o_una_asercion_da_senal(ruta, quitadas, senal):
    assert senal in _senales(_diff(ruta, quitadas=quitadas))


@pytest.mark.parametrize("ruta,puesta", [
    ("src/test/java/app/SumaTest.java", "    @Disabled"),
    ("tests/SumaTests.cs", '    [Fact(Skip = "luego")]'),
    ("tests/suma.rs", "#[ignore]"),
    ("suma_test.go", '    t.Skip("luego")'),
])
def test_saltarse_un_test_da_senal(ruta, puesta):
    assert "SKIP_ADDED" in _senales(_diff(ruta, puestas=[puesta]))


def test_un_fichero_de_produccion_no_es_de_test():
    """El sufijo de clase de test no puede atrapar produccion: `Testing.java`
    o `Contest.cs` no son tests."""
    for ruta in ("src/main/java/app/Testing.java", "src/Contest.cs", "lib/latest.rs"):
        assert not changes.TEST_FILE.search(ruta), ruta
