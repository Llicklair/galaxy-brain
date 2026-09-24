"""TSX: los componentes React como simbolos, `<X/>` como llamada y el barril raiz.

Medido sobre react-hot-toast el 24-sep-2026 (banco de repos reales): de los
componentes de src/components/*.tsx no salia NI UN simbolo, porque un
componente casi nunca es `export function X` — es `const X: React.FC<P> =`,
`React.memo(...)`, `forwardRef(...)` o una arrow con tipo de retorno. Y aunque
lo fuera, nadie lo "llamaba": la llamada de un componente es `<X/>`.
Tambien alli: `src/index.ts` se llamaba "" y el fichero desaparecia del grafo.
"""

import os

import pytest

from galaxybrain import lenguajes

pytestmark = pytest.mark.skipif(
    not lenguajes.binario(),
    reason="ast-grep no instalado; la capa multilenguaje es opcional (ADR 0009)",
)

# Una forma por linea: la matriz de variantes, no un ejemplar.
COMPONENTES = """import * as React from 'react';
import { forwardRef, memo } from 'react';
export function Plano(props: P) { return <div/>; }
export function Tipado(props: P): JSX.Element { return <div/>; }
export default function PorDefecto() { return <div/>; }
const Local = ({ a }: P) => { return <div/>; };
export const Tarjeta = (props: P) => <div/>;
export const ConTipo: React.FC<P> = ({ a }) => { return <div/>; };
const Estilo = (a: number): React.CSSProperties => { return {}; };
export const Memo = React.memo(({ a }: P) => { return <div/>; });
export const MemoTipado: React.FC<P> = React.memo((p) => <div/>);
export const Ref = React.forwardRef<HTMLDivElement, P>((props, ref) => <div ref={ref}/>);
const RefNombrada = forwardRef(function RefNombrada(props, ref) { return <div/>; });
const Ambos = memo(forwardRef((props, ref) => <div/>));
export function useCosa() { return 1; }
export class Clase extends React.Component<P> {
  render() { return <div/>; }
  private ayuda(): number { return 1; }
}
"""

ESPERADOS = {"Plano", "Tipado", "PorDefecto", "Local", "Tarjeta", "ConTipo", "Estilo",
             "Memo", "MemoTipado", "Ref", "RefNombrada", "Ambos", "useCosa", "Clase",
             "render", "ayuda"}


def _escribe(raiz, rel, fuente):
    ruta = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(fuente)


def test_cada_forma_de_componente_es_simbolo(tmp_path):
    _escribe(str(tmp_path), "ui/comp.tsx", COMPONENTES)
    nombres = {n["qual"].rsplit(".", 1)[-1] for n in lenguajes.analyze(str(tmp_path))["nodes"]
               if n["kind"] != "module"}
    assert ESPERADOS <= nombres, sorted(ESPERADOS - nombres)


def test_un_envoltorio_cualquiera_no_es_componente(tmp_path):
    # `create((set) => ...)` no es memo/forwardRef: la variable no es una funcion
    _escribe(str(tmp_path), "ui/tienda.tsx",
             "const tienda = create((set) => { return {}; });\n")
    nombres = {n["qual"] for n in lenguajes.analyze(str(tmp_path))["nodes"]}
    assert "ui.tienda.tienda" not in nombres


def test_jsx_es_llamada_y_el_dom_no(tmp_path):
    raiz = str(tmp_path)
    _escribe(raiz, "src/boton.tsx",
             "export const Boton = (p: P) => { return <button/>; };\n")
    _escribe(raiz, "src/panel.tsx",
             "import { Boton } from './boton';\n"
             "export const Panel = () => {\n"
             "  return (\n"
             "    <section>\n"
             "      <Boton a={1}/>\n"
             "    </section>\n"
             "  );\n"
             "};\n")
    informe = lenguajes.analyze(raiz)
    llamadas = {(o, d) for o, d, t in informe["edges"] if t == "CALLS"}
    assert ("panel.Panel", "boton.Boton") in llamadas
    # `<section>` y `<button>` son DOM: ni se cuentan como llamadas por resolver
    assert informe["unresolved"].get("nombre-desconocido", 0) == 0


def test_barril_raiz_de_src_es_un_modulo(tmp_path):
    # src/index.ts (ts) reexporta un componente .tsx; los tests importan '../src'
    raiz = str(tmp_path)
    _escribe(raiz, "src/index.ts", "export { Boton } from './boton';\n")
    _escribe(raiz, "src/boton.tsx", "export const Boton = () => { return <b/>; };\n")
    _escribe(raiz, "test/boton.test.tsx", "import { Boton } from '../src';\n")
    aristas = {(o, d) for o, d, t in lenguajes.analyze(raiz)["edges"] if t == "IMPORTS"}
    assert ("index", "boton") in aristas
    assert ("test.boton.test", "index") in aristas
