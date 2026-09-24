"""El banco de repos REALES: la conformidad medida contra codigo que no escribimos.

Por que existe. Las sondas de conformidad miden cada lenguaje contra fixtures
escritos aqui, y un fixture solo prueba la forma que a su autor se le ocurrio.
El 24-sep-2026, generando videos sobre repos ajenos, salieron en una tarde tres
fallos que llevaban meses con la suite en verde:

  - Rust (tach): `use globset::Glob` caia en `resolvers/glob.rs` y fabricaba un
    CICLO que el gate bloquearia — bloquear sobre algo que no es un hecho.
  - Go (google/uuid): `import "time"` caia en `time.go`; las 6 aristas del
    grafo eran inventadas.
  - JS (express): `app.use = function use(...)` y los metodos de clase no eran
    simbolos; gb no veia ni un metodo de la libreria.

Criterio de terminado (escrito antes del codigo):
  1. Un repo real por lenguaje, clavado a un commit: reproducible.
  2. Por repo, comprobaciones CURADAS leyendo su codigo: simbolos que deben
     verse, aristas que deben existir y aristas que NO deben (los falsos de
     arriba quedan como regresion), llamadas resueltas y ciclos esperados.
  3. Las metricas (modulos, aristas, ciclos, simbolos, llamadas) contra una
     linea base: un cambio del motor que mueva numeros se ve en cada pasada.
  4. Una comprobacion curada que falla -> exit 1.

No entra en la suite: clona de la red (una vez; luego cachea). Se corre a mano,
como los demas bancos:

    python bancos/repos_reales.py            # comprueba y enseña deltas
    python bancos/repos_reales.py --base     # reescribe la linea base

Añadir un lenguaje es una entrada en REPOS con sus comprobaciones leidas del
codigo real — no copiadas de la salida de gb, que seria certificar lo que hay.
"""

import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(AQUI, "repos_reales.base.json")
CACHE = os.environ.get("GB_REPOS_REALES") or os.path.join(tempfile.gettempdir(), "gb-repos-reales")

REPOS = [
    {
        "nombre": "import-linter", "lenguaje": "python",
        "url": "https://github.com/seddonym/import-linter",
        "sha": "31927f1457e3df673912cb5efb0afa6dbc37585f",
        "simbolos": ["importlinter.domain.contract.ContractCheck",
                     "importlinter.application.use_cases.create_report",
                     "importlinter.contracts.forbidden.ForbiddenContract.check"],
        "aristas": [["importlinter.cli", "importlinter.application.use_cases"]],
        "llamadas": [["importlinter.application.use_cases.create_report",
                      "importlinter.application.use_cases._build_graph"]],
        "ciclos": 0,
    },
    {
        "nombre": "tach", "lenguaje": "rust+python",
        "url": "https://github.com/gauge-sh/tach",
        "sha": "65df67ac51a8d0e8f9e0398ea72c924fea34fd25",
        "simbolos": ["filesystem.file_to_module_path"],
        "aristas": [["filesystem", "config"]],
        # crates externos que casaban con modulos propios por sufijo
        "no_aristas": [["filesystem", "resolvers.glob"], ["interrupt", "commands.sync"],
                       ["processors.ignore_directive", "commands.sync"]],
        "ciclos": 0,
    },
    {
        "nombre": "express", "lenguaje": "js",
        "url": "https://github.com/expressjs/express",
        "sha": "9a34acf03cb818ff3f8bc40e44176e277a25cbb9",
        "simbolos": ["lib.application.use", "lib.response.send", "lib.express.createApplication"],
        "aristas": [["lib.express", "lib.application"]],
        # this.x() por ambito: dentro de `app.x = function` y de `res.x = function`
        "llamadas": [["lib.application.defaultConfiguration", "lib.application.set"],
                     ["lib.response.send", "lib.response.get"]],
        "ciclos": 0,
    },
    {
        "nombre": "ky", "lenguaje": "ts",
        "url": "https://github.com/sindresorhus/ky",
        "sha": "0d59458a0a58e1c3d7c6db0ab17ed5c7cd671e47",
        "simbolos": ["source.core.Ky.Ky"],
        "aristas": [["source.core.Ky", "source.core.constants"]],
        # REAL, y a sabiendas: types/hooks.ts hace `import type ... from
        # '../index.js'`, que cierra el ciclo con el barril. Es solo de tipos (se
        # borra al compilar); si eso debe contar es una decision abierta, no un
        # fallo del motor. Si cambia, este numero lo dice.
        "ciclos": 1,
    },
    {
        "nombre": "uuid", "lenguaje": "go",
        "url": "https://github.com/google/uuid",
        "sha": "2d3c2a9cc518326daf99a383f07c4d3c44317e4d",
        "simbolos": ["uuid.Parse", "version4.NewRandom"],
        # un solo paquete: sus ficheros no se importan entre si. Estas caian
        # de `import "database/sql/driver"` y `import "time"` (stdlib).
        "no_aristas": [["null", "sql"], ["version6", "time"]],
        "llamadas": [["version4.New", "version4.NewRandom"]],
        "ciclos": 0,
    },
    {
        "nombre": "busted", "lenguaje": "lua",
        "url": "https://github.com/lunarmodules/busted",
        "sha": "22f8089f461a563fb9553ab56f926c6805850833",
        "simbolos": ["busted.core.getTrace", "busted.block.execute", "busted.status.get_status",
                     "busted.utils.shuffle", "busted.outputHandlers.base.getFullName"],
        "aristas": [["busted.runner", "busted.core"], ["busted.modules.cli", "busted.utils"],
                    ["busted.outputHandlers.junit", "busted.outputHandlers.base"]],
        # `pl.utils` / `cliargs.core` caian en utils/core propios por sufijo;
        # `require('busted.x.' .. v)` caia en `busted`
        "no_aristas": [["busted.compatibility", "busted.utils"], ["busted.fixtures", "busted.utils"],
                       ["busted.modules.cli", "busted.core"],
                       ["busted.modules.test_file_loader", "busted"],
                       ["busted.modules.output_handler_loader", "busted"]],
        "llamadas": [["busted.block.setup", "busted.block.execAll"],
                     ["busted.execute.suite_reset", "busted.utils.urandom"]],
        "ciclos": 0,
    },
    {
        "nombre": "MediatR", "lenguaje": "csharp",
        "url": "https://github.com/jbogard/MediatR",
        "sha": "916ef1b3d68ccdc96db8f914eaf1b32fc7db52c5",
        "simbolos": ["MediatR.Mediator.Mediator", "MediatR.Mediator.Send", "MediatR.Mediator.Publish",
                     "MediatR.Registration.ServiceRegistrar.ServiceRegistrar",
                     "MediatR.IMediator.IMediator", "MediatR.Contracts.Unit.Unit"],
        "aristas": [["MediatR.MicrosoftExtensionsDI.MediatRServiceCollectionExtensions",
                     "MediatR.Registration.ServiceRegistrar"],
                    ["test.MediatR.DependencyInjectionTests.Usings",
                     "test.MediatR.DependencyInjectionTests.Contracts.Responses.Pong"],
                    ["test.MediatR.Tests.Licensing.LicenseValidatorTests", "MediatR.Licensing.License"]],
        # `global using ...Contracts.Requests` (6 ficheros) caia en el Requests.cs de samples
        "no_aristas": [["test.MediatR.DependencyInjectionTests.Usings",
                        "samples.MediatR.Examples.ExceptionHandler.Requests"]],
        "llamadas": [["MediatR.Mediator.Publish", "MediatR.Mediator.PublishNotification"],
                     ["MediatR.MicrosoftExtensionsDI.MediatRServiceCollectionExtensions.AddMediatR",
                      "MediatR.Registration.ServiceRegistrar.AddRequiredServices"]],
        "ciclos": 0,
    },
    {
        "nombre": "addressable", "lenguaje": "ruby",
        "url": "https://github.com/sporkmonger/addressable",
        "sha": "d298c9f551fa9748d16dbfb6273b70f60b3d61bc",
        "simbolos": ["lib.addressable.uri.parse", "lib.addressable.uri.port_mapping",
                     "lib.addressable.idna.pure.to_ascii", "lib.addressable.template.expand",
                     "lib.addressable.uri.URI"],
        # `require "addressable/uri"` va por $LOAD_PATH (lib/), no es relativo
        "aristas": [["lib.addressable", "lib.addressable.uri"],
                    ["lib.addressable.uri", "lib.addressable.idna"],
                    ["lib.addressable.template", "lib.addressable.version"]],
        # `require "idn"` es una gema, no idna.rb
        "no_aristas": [["lib.addressable.idna.native", "lib.addressable.idna"]],
        "llamadas": [["lib.addressable.idna.pure.to_ascii", "lib.addressable.idna.pure.punycode_encode"],
                     ["lib.addressable.template.expand", "lib.addressable.template.normalize_keys"]],
        "ciclos": 0,
    },
    {
        "nombre": "container", "lenguaje": "php",
        "url": "https://github.com/thephpleague/container",
        "sha": "4fee6c75b3368dba3682a67439b57f8e24ab3eb7",
        "simbolos": ["Container.Container", "Container.add", "Exception.NotFoundException.forAlias",
                     "Definition.Definition.normaliseAlias",
                     "DefinitionContainerInterface.DefinitionContainerInterface"],
        "aristas": [["Container", "Definition.DefinitionAggregate"],
                    ["Exception.NotFoundException", "Definition.Definition"]],
        # `use Psr\Container\...` / `Psr\EventDispatcher\...` contra modulos propios homonimos
        "no_aristas": [["Exception.NotFoundException", "Container"],
                       ["DefinitionContainerInterface", "Container"],
                       ["Event.ContainerEvent", "Event.EventDispatcher"]],
        "llamadas": [["Container.get", "Container.resolve"],
                     ["Exception.NotFoundException.forAlias", "Definition.Definition.normaliseAlias"]],
        # REAL: ReflectionContainer <-> Argument\ArgumentReflectorTrait (use en los dos sentidos)
        "ciclos": 1,
    },
    {
        "nombre": "jsoup", "lenguaje": "java",
        "url": "https://github.com/jhy/jsoup",
        "sha": "093e2f58492c531667e551e8793513a41b22443e",
        "simbolos": ["main.java.org.jsoup.Jsoup.parse",
                     "main.java.org.jsoup.helper.HttpConnection.execute",
                     "main.java.org.jsoup.nodes.Document.OutputSettings",
                     "main.java.org.jsoup.select.NodeVisitor.NodeVisitor",
                     "main.java.org.jsoup.parser.HtmlTreeBuilderState.HtmlTreeBuilderState"],
        "aristas": [["main.java.org.jsoup.Jsoup", "main.java.org.jsoup.parser.Parser"],
                    # solo por `import static` (HtmlTreeBuilder.java:25-27)
                    ["main.java.org.jsoup.parser.HtmlTreeBuilder",
                     "main.java.org.jsoup.parser.HtmlTreeBuilderState"]],
        # org.w3c.dom.Element, java.util.stream.Collector, java.util.regex.Pattern
        "no_aristas": [["main.java.org.jsoup.helper.W3CDom", "main.java.org.jsoup.nodes.Element"],
                       ["main.java.org.jsoup.internal.StringUtil", "main.java.org.jsoup.select.Collector"],
                       ["main.java.org.jsoup.helper.DataUtil", "main.java.org.jsoup.helper.Regex"]],
        "llamadas": [["main.java.org.jsoup.Jsoup.parse", "main.java.org.jsoup.parser.Parser.parse"],
                     ["main.java.org.jsoup.select.Selector.select",
                      "main.java.org.jsoup.select.Collector.collect"]],
        # REALES: Java admite ciclos de import. Un SCC de 28 modulos, TestServer<->netty
        # y HtmlTreeBuilder<->HtmlTreeBuilderState (static imports en los dos sentidos)
        "ciclos": 3,
    },
    {
        "nombre": "javapoet", "lenguaje": "java",
        "url": "https://github.com/square/javapoet",
        "sha": "b9017a9503b76e11b4ad4c1a9f050e2d29112cb0",
        "simbolos": ["main.java.com.squareup.javapoet.JavaFile.writeTo",
                     "main.java.com.squareup.javapoet.Util.checkNotNull",
                     "main.java.com.squareup.javapoet.TypeSpec.Kind"],
        "aristas": [["main.java.com.squareup.javapoet.LineWrapper", "main.java.com.squareup.javapoet.Util"]],
        # `import java.util.List` caia en Util.java
        "no_aristas": [["test.java.com.squareup.javapoet.TestUtil", "main.java.com.squareup.javapoet.Util"],
                       ["test.java.com.squareup.javapoet.TypesTest", "main.java.com.squareup.javapoet.Util"]],
        "llamadas": [["main.java.com.squareup.javapoet.JavaFile.writeTo",
                      "main.java.com.squareup.javapoet.JavaFile.writeToPath"]],
        "ciclos": 0,
    },
]


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def clon(repo):
    """El repo en su commit exacto, clonado una vez y cacheado."""
    ruta = os.path.join(CACHE, repo["nombre"])
    if os.path.isdir(ruta) and _git("rev-parse", "HEAD", cwd=ruta).stdout.strip() == repo["sha"]:
        return ruta
    os.makedirs(ruta, exist_ok=True)
    _git("init", "-q", cwd=ruta)
    _git("fetch", "-q", "--depth", "1", repo["url"], repo["sha"], cwd=ruta)
    r = _git("checkout", "-q", "FETCH_HEAD", cwd=ruta)
    if r.returncode != 0:
        raise SystemExit("no pude clonar %s@%s: %s" % (repo["url"], repo["sha"][:8], r.stderr))
    return ruta


def _gb(*args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run([sys.executable, "-m", "galaxybrain.cli", *args, "--json"],
                       capture_output=True, env=env, timeout=900)
    return json.loads(p.stdout.decode("utf-8", "replace") or "{}")


def mide(repo):
    ruta = clon(repo)
    g, s = _gb("graph", ruta), _gb("symbols", ruta)
    aristas = {tuple(e) for e in g.get("edge_list") or []}
    llamadas = {(o, d) for o, d, t in s.get("edges") or [] if t == "CALLS"}
    quals = {n["qual"] for n in s.get("nodes") or []}
    fallos = []
    for q in repo.get("simbolos", []):
        if q not in quals:
            fallos.append("falta el simbolo %s" % q)
    for o, d in repo.get("aristas", []):
        if (o, d) not in aristas:
            fallos.append("falta la arista %s -> %s" % (o, d))
    for o, d in repo.get("no_aristas", []):
        if (o, d) in aristas:
            fallos.append("arista INVENTADA %s -> %s" % (o, d))
    for o, d in repo.get("llamadas", []):
        if (o, d) not in llamadas:
            fallos.append("falta la llamada %s -> %s" % (o, d))
    ciclos = len(g.get("cycles") or [])
    if "ciclos" in repo and ciclos != repo["ciclos"]:
        fallos.append("%d ciclo(s), se esperaban %d" % (ciclos, repo["ciclos"]))
    metricas = {
        "modulos": g.get("modules", 0), "aristas": len(aristas), "ciclos": ciclos,
        "simbolos": len([n for n in s.get("nodes") or [] if n.get("kind") != "module"]),
        "llamadas": s.get("calls_resolved") or 0,
    }
    return metricas, fallos


def main(argv):
    base = {}
    if os.path.isfile(BASE):
        with open(BASE, encoding="utf-8") as fh:
            base = json.load(fh)
    nueva, rotos = {}, 0
    print("%-14s %-12s %s" % ("repo", "lenguaje", "modulos aristas ciclos simbolos llamadas"))
    for repo in REPOS:
        metricas, fallos = mide(repo)
        nueva[repo["nombre"]] = metricas
        antes = base.get(repo["nombre"], {})
        celdas = []
        for k in ("modulos", "aristas", "ciclos", "simbolos", "llamadas"):
            v, a = metricas[k], antes.get(k)
            celdas.append("%d%s" % (v, "" if a in (None, v) else " (%+d)" % (v - a)))
        print("%-14s %-12s %s" % (repo["nombre"], repo["lenguaje"], "  ".join(celdas)))
        for f in fallos:
            print("    ROTO: %s" % f)
        rotos += len(fallos)
    if "--base" in argv:
        with open(BASE, "w", encoding="utf-8") as fh:
            json.dump(nueva, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("linea base reescrita: %s" % BASE)
    print("%d repo(s) - %d comprobacion(es) rota(s)" % (len(REPOS), rotos))
    return 1 if rotos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
