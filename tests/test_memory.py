"""gb memory — la memoria cross-repo portada de scripts/memory-global.js.

Se prueba lo que tiene que seguir siendo idéntico al JS: el formato del vault (las
notas ya escritas siguen valiendo) y que `context` es magro por diseño — índice de
TODO, texto completo solo de las notas always/proyecto. El scoring de recall diverge
del JS a propósito: también mira el cuerpo, con el índice pesando doble.
"""

import pytest

from galaxybrain import memory


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("GALAXY_BRAIN_MEMORY_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    return tmp_path


def write_note(vault, name, body="cuerpo", **meta):
    """Escribe una nota en el formato exacto que produce el JS."""
    lines = ["---", "name: " + name]
    for key, value in meta.items():
        lines.append("%s: %s" % (key, value))
    lines += ["---", "", body, ""]
    (vault / (name + ".md")).write_text("\n".join(lines), encoding="utf-8")


def test_parse_note_reads_js_frontmatter(vault):
    write_note(
        vault,
        "una-nota",
        body="el cuerpo\ncon [[link]]",
        description="desc",
        type="feedback",
        scope="always",
        tags="[a, b]",
    )
    (note,) = memory.all_notes()
    assert note.name == "una-nota"
    assert note.description == "desc"
    assert note.type == "feedback"
    assert note.scope == "always"
    assert note.tags == ["a", "b"]  # los corchetes se quitan, se separa por coma
    assert note.body == "el cuerpo\ncon [[link]]"


def test_defaults_when_frontmatter_missing_fields(vault):
    (vault / "pelada.md").write_text("solo cuerpo, sin frontmatter", encoding="utf-8")
    (note,) = memory.all_notes()
    assert note.name == "pelada"  # del nombre de fichero
    assert note.type == "reference"
    assert note.scope == "general"
    assert note.tags == []


def test_frontmatter_sin_cierre_degrada_a_cuerpo_entero(vault):
    """Un `---` de apertura sin su `---` de cierre no es frontmatter: es texto.

    Se prefiere degradar (la nota sigue siendo legible y recall la encuentra) a
    petar leyendo el vault. El precio va escrito aqui a proposito: los campos que
    el autor creia declarados NO se aplican — `scope: always` incluido — asi que
    la nota se queda en `general` y nunca se inyecta en SessionStart.
    """
    (vault / "rota.md").write_text(
        "---\nname: otro-nombre\nscope: always\n\ncuerpo suelto\n", encoding="utf-8"
    )
    (note,) = memory.all_notes()
    assert note.name == "rota"  # del fichero, no del `name:` de dentro
    assert note.scope == "general"  # el `scope: always` declarado se pierde
    assert "name: otro-nombre" in note.body  # el bloque entero cae al cuerpo
    assert "cuerpo suelto" in note.body
    assert "otro-nombre" not in memory.context()  # y por eso no va en full


def test_nombres_de_nota_con_caracteres_raros(vault):
    """El nombre sale del stem tal cual: espacios, acentos y puntos valen.

    Lo que NO entra queda fijado igual de explicito: sin extension y `.MD` en
    mayusculas se ignoran, porque el filtro es `p.suffix == ".md"` y distingue caja.
    """
    for filename in ["con espacios.md", "acentué-ñ.md", "v1.2.3.md", "UPPER.MD", "sin-extension"]:
        (vault / filename).write_text("cuerpo x\n", encoding="utf-8")
    assert [n.name for n in memory.all_notes()] == ["acentué-ñ", "con espacios", "v1.2.3"]


def test_index_md_is_skipped(vault):
    write_note(vault, "real", description="x")
    (vault / "MEMORY.md").write_text("# index\n", encoding="utf-8")
    assert [n.name for n in memory.all_notes()] == ["real"]


def test_add_writes_note_and_regenerates_index(vault):
    path = memory.add("nueva", "una descripcion", type="user", scope="always", tags="x,y", body="hola")
    content = path.read_text(encoding="utf-8")
    assert "name: nueva" in content
    assert "scope: always" in content
    assert "tags: [x,y]" in content
    assert content.rstrip().endswith("hola")
    index = (vault / "MEMORY.md").read_text(encoding="utf-8")
    assert "- [nueva](nueva.md) [always] — una descripcion" in index


def test_empty_vault(vault):
    assert memory.all_notes() == []
    assert memory.context() is None
    assert "empty" in memory.index_lines()[0]


def test_vault_inexistente_se_comporta_como_vacio_y_add_lo_crea(vault, monkeypatch):
    """Que la carpeta no exista todavia es el estado del dia 1, no un error.

    `test_empty_vault` cubre la carpeta creada y sin notas; esto cubre el caso de
    antes: leer no debe petar con FileNotFoundError, y la primera escritura crea
    el vault entero (nota + indice) sin pedir un `mkdir` previo.
    """
    nuevo = vault / "todavia-no-existe"
    monkeypatch.setenv("GALAXY_BRAIN_MEMORY_DIR", str(nuevo))
    assert not nuevo.exists()

    assert memory.all_notes() == []
    assert memory.context() is None
    assert "empty" in memory.index_lines()[0]
    assert "VACIA" in memory.recall("lo que sea")[0]  # y no un stacktrace

    path = memory.add("primera", "la que crea el vault")
    assert path.is_file()
    assert (nuevo / "MEMORY.md").is_file()


def test_recall_corta_en_top_k(vault):
    """Recordar sin inflar el contexto es la mitad del diseño: el tope es duro.

    Con mas notas que casan que huecos, recall devuelve TOP_K y punto — si no,
    una query generica volcaria el vault entero, que es justo lo que el modulo
    existe para evitar.
    """
    for i in range(memory.TOP_K + 3):
        write_note(vault, "nota-%d" % i, description="harbor")
    cabeceras = [line for line in memory.recall("harbor") if line.startswith("###")]
    assert len(cabeceras) == memory.TOP_K


def test_recall_multipalabra_ordena_por_terminos_que_casan(vault):
    """Una query de varias palabras suma por termino, no exige todos.

    Casar 3 de 3 va antes que casar 1 de 3, y 0 de 3 se cae. Es un OR ponderado,
    no un AND: pedir todos los terminos convertiria cada query larga en cero
    resultados.
    """
    write_note(vault, "tres", description="harbor wsl docker")
    write_note(vault, "uno", description="harbor solo")
    write_note(vault, "cero", description="nada que ver")
    cabeceras = [line for line in memory.recall("harbor wsl docker") if line.startswith("###")]
    assert len(cabeceras) == 2
    assert "tres" in cabeceras[0]
    assert "uno" in cabeceras[1]


def test_recall_ranks_by_term_hits(vault):
    write_note(vault, "gemini", description="evaluador cross-vendor", tags="tooling")
    write_note(vault, "harbor", description="wsl docker")
    write_note(vault, "otra", description="nada que ver")
    out = "\n".join(memory.recall("evaluador tooling"))
    assert "### gemini" in out
    assert "### otra" not in out  # cero hits -> excluida


def test_recall_matches_body_terms(vault):
    write_note(vault, "proveedor-nd", description="nota de prueba", body="el proveedor manda N/D sin precio")
    out = "\n".join(memory.recall("proveedor precio"))
    assert "### proveedor-nd" in out


def test_recall_metadata_outranks_body(vault):
    write_note(vault, "solo-cuerpo", description="nada", body="harbor harbor harbor")
    write_note(vault, "en-descripcion", description="harbor en wsl", body="cuerpo")
    out = memory.recall("harbor")
    first_header = next(line for line in out if line.startswith("###"))
    assert "en-descripcion" in first_header


def test_recall_empty_query_returns_empty(vault):
    write_note(vault, "x", description="y")
    assert memory.recall("   ") == []


def test_recall_no_match_is_a_message_not_a_crash(vault):
    write_note(vault, "x", description="y")
    out = memory.recall("zzzzz")
    assert len(out) == 1 and "casa" in out[0]


def test_recall_distingue_vault_vacio_de_sin_coincidencias(vault):
    """"No he encontrado" y "no tenia donde buscar" no son la misma respuesta.

    Paso de verdad: una sesion recomendo `gb memory recall <proyecto>` sin haber
    escrito nunca una nota. El "no match" se leyo como que la memoria habia
    fallado, cuando el vault estaba vacio — el mismo patron que el gate mudo:
    un silencio que se lee como veredicto.
    """
    vacio = memory.recall("guardia")
    assert "VACIA" in vacio[0]
    assert "gb memory add" in vacio[0]  # y como arreglarlo

    write_note(vault, "otra-cosa", description="nada que ver")
    con_notas = memory.recall("guardia")
    assert "VACIA" not in con_notas[0]
    assert "1 nota" in con_notas[0]  # cuantas se han mirado de verdad


def test_context_is_lean(vault):
    write_note(vault, "core", body="IDENTIDAD", description="quien", scope="always")
    write_note(vault, "delproyecto", body="DEL-PROYECTO", description="p", scope="project:demo")
    write_note(vault, "general", body="SOLO-INDICE", description="g", scope="general")
    payload = memory.context(project="demo")
    # el indice lista las tres
    assert "core [always]" in payload
    assert "delproyecto [project:demo]" in payload
    assert "general [general]" in payload
    # el texto completo solo de always + proyecto
    assert "IDENTIDAD" in payload
    assert "DEL-PROYECTO" in payload
    assert "SOLO-INDICE" not in payload


def test_context_matches_project_by_tag(vault):
    write_note(vault, "taggeada", body="POR-TAG", description="t", scope="general", tags="demo")
    payload = memory.context(project="demo")
    assert "POR-TAG" in payload


def test_context_project_derived_from_env(vault, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/home/x/c--foo-bar")
    write_note(vault, "n", body="AQUI", description="d", scope="project:foo-bar")
    payload = memory.context()  # sin --project: se deriva y se quita el prefijo c--
    assert "AQUI" in payload
