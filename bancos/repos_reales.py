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
        # pyo3: python/tach/check_external.py:3 importa la #[pyfunction] de src/lib.rs:210
        "llamadas": [["python.tach.check_external", "lib.check_external_dependencies"]],
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
        "herencias": [["source.errors.ResponseSizeError.ResponseSizeError", "source.errors.KyError.KyError"]],
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
        "herencias": [["test.MediatR.DependencyInjectionTests.Providers.LightInjectServiceProviderFixture.LightInjectServiceProviderFixture", "test.MediatR.DependencyInjectionTests.Abstractions.BaseServiceProviderFixture.BaseServiceProviderFixture"]],
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
        # `CustomURIClass < Addressable::URI` caia en el `Fake::URI` del spec al
        # preferir la clase local: una base cualificada no es la local
        "no_herencias": [["spec.addressable.uri_spec.CustomURIClass", "spec.addressable.uri_spec.URI"]],
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
        "herencias": [["Argument.LiteralArgument.LiteralArgument", "Argument.LiteralArgumentInterface.LiteralArgumentInterface"]],
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
        "herencias": [["main.java.org.jsoup.nodes.Element.Element", "main.java.org.jsoup.nodes.Node.Node"]],
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
        "herencias": [["main.java.com.squareup.javapoet.WildcardTypeName.WildcardTypeName", "main.java.com.squareup.javapoet.TypeName.TypeName"]],
        "ciclos": 0,
    },
    {'nombre': 'colormath',
     'lenguaje': 'kotlin',
     'url': 'https://github.com/ajalt/colormath',
     'sha': '2d650498a975452fcd002d7352dd36c79e32061a',
     'simbolos': ['colormath.src.commonMain.kotlin.com.github.ajalt.colormath.calculate.Contrast.wcagLuminance',
                  'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.model.LAB.LABColorSpaces',
                  'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.model.LAB.LAB',
                  'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.model.LAB.LABColorSpace',
                  'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.internal.ColorSpaceUtils.doCreate'],
     'aristas': [['colormath.src.commonMain.kotlin.com.github.ajalt.colormath.model.JzAzBz',
                  'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.calculate.Difference'],
                 ['scripts.benchmarks.src.jmh.kotlin.com.github.ajalt.colormath.benchmark.ColorBenchmarks',
                  'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.transform.Interpolate']],
     'no_aristas': [['extensions.colormath-ext-android-color.src.androidMain.kotlin.com.github.ajalt.colormath.extensions.android.color.ColorExtensions',
                     'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.ColorSpace'],
                    ['extensions.colormath-ext-jetpack-compose.src.commonMain.kotlin.com.github.ajalt.colormath.extensions.android.composecolor.ComposeColorExtensions',
                     'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.ColorSpace'],
                    ['scripts.benchmarks.src.jmh.kotlin.com.github.ajalt.colormath.benchmark.ColorBenchmarks',
                     'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.transform.Transform']],
     'llamadas': [['colormath.src.commonMain.kotlin.com.github.ajalt.colormath.calculate.Contrast.wcagContrastRatio',
                   'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.calculate.Contrast.wcagLuminance'],
                  ['colormath.src.commonMain.kotlin.com.github.ajalt.colormath.model.LAB.create',
                   'colormath.src.commonMain.kotlin.com.github.ajalt.colormath.internal.ColorSpaceUtils.doCreate']],
     "herencias": [["colormath.src.commonMain.kotlin.com.github.ajalt.colormath.model.RGB.LinearTransferFunctions", "colormath.src.commonMain.kotlin.com.github.ajalt.colormath.model.RGB.TransferFunctions"]],
        'ciclos': 0},
    {
        "nombre": "scala-xml", "lenguaje": "scala",
        "url": "https://github.com/scala/scala-xml",
        "sha": "8329863472f6a2f04939974d88d1540c357d5062",
        # trait, case class anidada con extends, `final def ...: Unit = {` en
        # varias lineas, `private def` y trait generico: ninguno se veia
        "simbolos": ["shared.src.main.scala.scala.xml.parsing.MarkupParser.MarkupParser",
                     "shared.src.main.scala.scala.xml.dtd.ContentModel.ElemName",
                     "shared.src.main.scala.scala.xml.XML.write",
                     "shared.src.main.scala.scala.xml.Utility.combineAdjacentTextNodes",
                     "shared.src.main.scala.scala.xml.factory.XMLLoader.XMLLoader"],
        # absoluto (XMLTest.scala:9), agrupado `dtd.{DocType, PublicID}` (:8) y
        # relativo por `package scala / xml / parsing` apilados
        # (NoBindingFactoryAdapter.scala:13-18, `import factory.NodeFactory`)
        "aristas": [["jvm.src.test.scala.scala.xml.XMLTest",
                     "shared.src.main.scala.scala.xml.parsing.ConstructingParser"],
                    ["jvm.src.test.scala.scala.xml.XMLTest",
                     "shared.src.main.scala.scala.xml.dtd.DocType"],
                    ["shared.src.main.scala.scala.xml.parsing.NoBindingFactoryAdapter",
                     "shared.src.main.scala.scala.xml.factory.NodeFactory"]],
        # por sufijo sin mayusculas: `org.xml.sax.*` caia en XML.scala,
        # `util.Properties` en el Properties.scala de test y `scala.xml.dtd._`
        # (paquete de 7 ficheros) en dtd/DTD.scala
        "no_aristas": [["shared.src.main.scala.scala.xml.include.sax.XIncludeFilter",
                        "shared.src.main.scala.scala.xml.XML"],
                       ["jvm.src.test.scala-2.x.scala.xml.CompilerErrors",
                        "shared.src.test.scala.scala.xml.Properties"],
                       ["shared.src.main.scala.scala.xml.parsing.MarkupParser",
                        "shared.src.main.scala.scala.xml.dtd.DTD"]],
        # XML.scala:130 `Utility.serialize(...)`, Utility.scala:213
        "llamadas": [["shared.src.main.scala.scala.xml.XML.write",
                      "shared.src.main.scala.scala.xml.Utility.serialize"],
                     ["shared.src.main.scala.scala.xml.Utility.serialize",
                      "shared.src.main.scala.scala.xml.Utility.serializeImpl"]],
        # sin ciclos de import: los acoples reales van por el mismo paquete
        # (`scala.xml`), que no deja arista (MISMO_PAQUETE)
        "herencias": [["shared.src.main.scala.scala.xml.include.UnavailableResourceException.UnavailableResourceException", "shared.src.main.scala.scala.xml.include.XIncludeException.XIncludeException"]],
        "ciclos": 0,
    },
    {
        "nombre": "swift-argument-parser", "lenguaje": "swift",
        "url": "https://github.com/apple/swift-argument-parser",
        "sha": "cdc5f0c6e836de848699ae11f6480f2d99ac5ef1",
        # protocolo, struct generica con `: Protocolo`, `func` generica, `static func`
        "simbolos": ["Sources.ArgumentParser.Parsable Types.ParsableCommand.ParsableCommand",
                     "Sources.ArgumentParser.Parsable Types.ParsableCommand.main",
                     "Sources.ArgumentParser.Parsable Properties.Argument.Argument",
                     "Sources.ArgumentParser.Parsing.ArgumentDecoder.container",
                     "Sources.ArgumentParserToolInfo.ToolInfo.ToolInfoV0"],
        # `ArgumentParserToolInfo` es un target de UN fichero: `internal import` y
        # `import` dejan arista. Los de varios ficheros (ArgumentParser) no: MISMO_PAQUETE
        "aristas": [["Sources.ArgumentParser.Usage.DumpHelpGenerator",
                     "Sources.ArgumentParserToolInfo.ToolInfo"],
                    ["Tools.generate-manual.GenerateManual", "Sources.ArgumentParserToolInfo.ToolInfo"]],
        # `import Foundation` caia en Utilities/Foundation.swift (las 22 aristas del grafo)
        "no_aristas": [["Tests.ArgumentParserUnitTests.ExitCodeTests",
                        "Sources.ArgumentParser.Utilities.Foundation"],
                       ["Tools.generate-manual.GenerateManual",
                        "Sources.ArgumentParser.Utilities.Foundation"]],
        "llamadas": [["Sources.ArgumentParser.Parsable Types.ParsableCommand.main",
                      "Sources.ArgumentParser.Parsable Types.ParsableCommand.parseAsRoot"],
                     ["Sources.ArgumentParser.Parsable Types.ParsableCommand.parseAsRoot",
                      "Sources.ArgumentParser.Parsing.CommandParser.CommandParser"]],
        # SwiftPM prohibe ciclos entre targets, y dentro de un target no hay import
        "herencias": [["Tests.ArgumentParserUnitTests.UsageGenerationTests.J", "Sources.ArgumentParser.Parsable Types.ParsableArguments.ParsableArguments"]],
        "ciclos": 0,
    },
    {
        "nombre": "jason", "lenguaje": "elixir",
        "url": "https://github.com/michalmuskala/jason",
        "sha": "4ede42858eb19f80ec9e863aab52df466eab8608",
        # `defmodule Jason.Decoder` (con punto), el anidado `Unescape`, `def` con
        # guarda (decoder.ex:48) y `defmacro` (codegen.ex:21, helpers.ex:32)
        "simbolos": ["lib.decoder.Decoder", "lib.decoder.Unescape", "lib.decoder.parse",
                     "lib.codegen.bytecase", "lib.helpers.json_map"],
        # `DecodeError` se declara en decoder.ex, no en un fichero con su nombre
        "aristas": [["lib.jason", "lib.decoder"], ["lib.decoder", "lib.codegen"],
                    ["test.decode_test", "lib.decoder"]],
        # `alias Jason.{DecodeError, Codegen}` caia, quitando un segmento, en jason.ex
        "no_aristas": [["lib.decoder", "lib.jason"], ["lib.codegen", "lib.jason"],
                       ["lib.helpers", "lib.jason"]],
        "llamadas": [["lib.jason.decode", "lib.decoder.parse"],
                     ["lib.helpers.json_map", "lib.codegen.build_kv_iodata"]],
        # REAL: Codegen y Encode se nombran y llaman en los dos sentidos
        # (codegen.ex:107 Encode.key, encode.ex:288 Codegen.jump_table); el SCC
        # suma Encoder (Encode -> Encoder.encode) y Helpers (`require
        # Jason.Helpers` en el quote de __deriving__, encoder.ex:88)
        "ciclos": 1,
    },
    {
        "nombre": "petitparser", "lenguaje": "dart",
        "url": "https://github.com/petitparser/dart-petitparser",
        "sha": "33c6956b9ee5236be23556998f46e515d52685c7",
        # `abstract class Parser<R>`, metodo `=>`, `sealed class`, extension y
        # getter: ninguno era simbolo con los patrones (10 clases de 194)
        "simbolos": ["lib.src.core.parser.Parser", "lib.src.core.parser.parse",
                     "lib.src.core.result.Result", "lib.src.matcher.accept.AcceptParser",
                     "lib.src.core.token.line", "lib.src.parser.character.char.char"],
        # un `export` de barril, el `package:` propio (pubspec `name: petitparser`)
        # y un `import ... as`: los tres se perdian (147 de 646 aristas)
        "aristas": [["lib.core", "lib.src.core.parser"],
                    ["test.debug_test", "lib.petitparser"],
                    ["test.parser_combinator_test", "test.generated.sequence_test"]],
        # sin no_aristas: sus externos (meta, collection, test) no tienen
        # homonimo local; `package:` ajeno y `part of` van en test_dart_imports.py.
        # Sin llamadas: dart no las extrae (carencia declarada en la tabla).
        # REALES: Dart admite imports ciclicos. SCC de 11 en core/ (parser ->
        # context -> token -> ... -> parser), y a pares reference<->resolve,
        # greedy<->lazy, linter<->internal/linter_rules,
        # optimize<->internal/optimize_rules, predicate/{character,
        # single_character, unicode_character} y matcher/pattern/* (4).
        "herencias": [["lib.src.parser.combinator.optional.OptionalParser", "lib.src.parser.combinator.delegate.DelegateParser"]],
        "ciclos": 7,
    },
    {
        "nombre": "libyaml", "lenguaje": "c",
        "url": "https://github.com/yaml/libyaml",
        "sha": "90a56d4500aa1a1798514c5cb55c3ad4cb095f94",
        # `static int\nf(...)` (emitter/loader/parser/scanner casi enteros) y
        # `YAML_DECLARE(int)\nf(...)`; el patron de antes solo veia 90 de 228
        "simbolos": ["parser.yaml_parser_parse", "api.yaml_parser_initialize",
                     "emitter.yaml_emitter_emit_stream_start",
                     "loader.yaml_parser_load_document", "tests.run-dumper.compare_nodes"],
        # `#include "yaml_private.h"` junto al fichero y `"../src/yaml_private.h"`;
        # `<yaml.h>` va por -Iinclude y no deja arista (carencia declarada)
        "aristas": [["api", "yaml_private"], ["tests.run-emitter-test-suite", "yaml_private"]],
        # `return f(...)` (parser.c:249) e `if (!f(...))` entre ficheros
        # (loader.c:99, declarada en yaml.h, definida en parser.c)
        "llamadas": [["parser.yaml_parser_state_machine", "parser.yaml_parser_parse_stream_start"],
                     ["loader.yaml_parser_load", "parser.yaml_parser_parse"]],
        # los .c solo incluyen yaml_private.h, que no incluye a ninguno
        "ciclos": 0,
    },
    {
        "nombre": "react-hot-toast", "lenguaje": "tsx+ts",
        "url": "https://github.com/timolins/react-hot-toast",
        "sha": "e725d38e0faec05f7b8fb10644b616ef978d2f4d",
        # componentes como `const X: React.FC<P> = (...) =>`, `React.memo(...)`,
        # arrow con tipo de retorno y const sin exportar: ninguno era simbolo
        "simbolos": ["components.toaster.Toaster", "components.toast-bar.ToastBar",
                     "components.toaster.getPositionStyle", "components.toaster.ToastWrapper",
                     "core.use-toaster.useToaster"],
        # ts -> tsx (el barril src/index.ts, que se llamaba "" y desaparecia),
        # tsx -> ts, y el `from '../src'` de los tests
        "aristas": [["index", "components.toaster"], ["components.toaster", "core.use-toaster"],
                    ["test.toast.test", "index"]],
        # headless/index.ts y src/index.ts acaban los dos en `index`; headless
        # solo importa ../core/*. Esta arista fabricaria el ciclo index<->headless
        "no_aristas": [["headless", "index"]],
        # `<ToastBar .../>` es una llamada (JSX); useToaster es un hook de un .ts
        "llamadas": [["components.toaster.Toaster", "components.toast-bar.ToastBar"],
                     ["components.toaster.Toaster", "core.use-toaster.useToaster"]],
        # index -> headless -> core/*; components -> core. core no sube nunca.
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
    herencias = {(o, d) for o, d, t in s.get("edges") or [] if t == "EXTENDS"}
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
    for o, d in repo.get("herencias", []):
        if (o, d) not in herencias:
            fallos.append("falta la herencia %s -> %s" % (o, d))
    for o, d in repo.get("no_herencias", []):
        if (o, d) in herencias:
            fallos.append("herencia INVENTADA %s -> %s" % (o, d))
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
