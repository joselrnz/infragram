"""Each provider package's type stub names what its ``__getattr__`` returns.

``aws.EC2`` resolves through the package's module ``__getattr__``, which an
editor cannot see into, so nothing completed a short name. ``gen:nodes`` now
writes an ``__init__.pyi`` beside each package listing every class the short
form finds; a stub that named a different class than the package returns (a
name two categories share, taken from the wrong one) would send an editor to
the wrong definition. ``generate-nodes.py --check`` keeps the stubs current.

Every generated node module has a stub too. A type checker builds each
pydantic class an ``__init__`` of its model fields unless the class declares
one itself, so a generated class -- which inherits ``Element``'s or
``Frame``'s -- read as taking ``id=``, ``name=``, ``type=`` and
``compute.EC2("web")`` as an error. The stub beside each module declares the
real ``__init__`` on every class. A checker reads the stub in place of the
module, so the two must name the same classes, and the signature must be the
one that runs.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

import infragram.nodes as nodes
from infragram.nodes import Element, Frame
from infragram.paths import repo_root

STUBS = sorted(Path(nodes.__file__).parent.glob("*/__init__.pyi"))


def _imports(stub: Path) -> dict[str, str]:
    """name -> category module, from the stub's ``from .<module> import`` lines."""
    names: dict[str, str] = {}
    for node in ast.parse(stub.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            for alias in node.names:
                names[alias.asname or alias.name] = node.module
    return names


def test_every_provider_package_has_a_stub() -> None:
    packages = {
        path.parent.name
        for path in Path(nodes.__file__).parent.glob("*/__init__.py")
        if "CATEGORIES" in path.read_text(encoding="utf-8")
    }
    assert packages and packages == {stub.parent.name for stub in STUBS}


def test_a_stub_names_the_class_the_short_form_returns() -> None:
    checked = 0
    for stub in STUBS:
        package = importlib.import_module(f"infragram.nodes.{stub.parent.name}")
        for name, module in _imports(stub).items():
            category = importlib.import_module(f"{package.__name__}.{module}")
            assert getattr(package, name) is getattr(category, name), f"{package.__name__}.{name}"
            checked += 1
        categories = {
            alias.name
            for node in ast.parse(stub.read_text(encoding="utf-8")).body
            if isinstance(node, ast.ImportFrom) and node.level == 1 and not node.module
            for alias in node.names
        }
        assert categories == set(package.CATEGORIES), package.__name__
    assert checked > 3500


# ---------------------------------------------- each generated module's own stub


NODES = repo_root() / "plugin" / "src" / "infragram" / "nodes"
MODULES = sorted(
    path
    for path in NODES.glob("*/*.py")
    if path.name != "__init__.py" and "__pycache__" not in path.parts
)


def _classes(path: Path) -> dict[str, ast.ClassDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def _declared(init: ast.FunctionDef) -> list[tuple[str, str, bool]]:
    """A stub ``__init__``'s parameters after ``self``: (how it is passed,
    name, whether it has a default)."""
    args = init.args
    positional = [*args.posonlyargs, *args.args][1:]
    defaults = len(args.defaults)
    out = [
        ("positional", arg.arg, index >= len(positional) - defaults)
        for index, arg in enumerate(positional)
    ]
    out += [
        ("keyword", arg.arg, default is not None)
        for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
    ]
    if args.kwarg is not None:
        out.append(("var-keyword", args.kwarg.arg, False))
    return out


def _runs(base: type) -> list[tuple[str, str, bool]]:
    """The same three facts about the ``__init__`` the base really has."""
    kinds = {
        inspect.Parameter.POSITIONAL_OR_KEYWORD: "positional",
        inspect.Parameter.KEYWORD_ONLY: "keyword",
        inspect.Parameter.VAR_KEYWORD: "var-keyword",
    }
    parameters = list(inspect.signature(vars(base)["__init__"]).parameters.values())[1:]
    return [(kinds[p.kind], p.name, p.default is not p.empty) for p in parameters]


def test_there_are_generated_modules_to_check() -> None:
    assert len(MODULES) > 250, len(MODULES)


@pytest.mark.parametrize("module", MODULES, ids=lambda p: f"{p.parent.name}.{p.stem}")
def test_the_stub_names_the_classes_the_module_defines(module: Path) -> None:
    stub = module.with_suffix(".pyi")
    assert stub.is_file(), f"{stub.name} is missing: run scripts/tools/generate-nodes.py"
    real, declared = _classes(module), _classes(stub)
    assert list(declared) == list(real)
    root = Frame if module.parent.name == "frames" else Element
    expected = _runs(root)
    public = [name for name in declared if not name.startswith("_")]
    assert public, module
    for name in public:
        inits = [n for n in declared[name].body if isinstance(n, ast.FunctionDef)]
        assert [n.name for n in inits] == ["__init__"], name
        assert _declared(inits[0]) == expected, name


def test_a_generated_class_is_built_the_way_its_stub_says() -> None:
    compute = importlib.import_module("infragram.nodes.aws.compute")
    node = compute.EC2("web", "t3.small", role="app")
    assert (node.name, node.attributes["detail"], node.role) == ("web", "t3.small", "app")
    frames = importlib.import_module("infragram.nodes.frames.aws")
    assert frames.VPC("VPC 10.0.0.0/16", flow="row").attributes["flow"] == "row"
