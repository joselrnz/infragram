"""Finding the class to import ranks the one an architect means first.

The search listed matches alphabetically and ignored the curated aliases the
editor's sidebar reads, so "s3" listed twenty S3 resource glyphs and never
``SimpleStorageService``, "aks" missed ``KubernetesServices``, and "vpc" put
another cloud's VPC card before the AWS frame. ``infragram find`` and the MCP
server's ``find_components`` share one ranked search now.
"""

from __future__ import annotations

import json

import pytest

from infragram.catalog.find import find
from infragram.cli.user.find import main


def _first(query: str, library: str | None = None) -> str:
    hits = find(query, library)
    assert hits, query
    return f"{hits[0].module.removeprefix('infragram.nodes.')}.{hits[0].name}"


@pytest.mark.parametrize(
    ("query", "library", "expected"),
    [
        ("s3", None, "aws.storage.SimpleStorageService"),
        ("ec2", None, "aws.compute.EC2"),
        ("vpc", None, "frames.aws.VPC"),
        ("vpc", "aws", "frames.aws.VPC"),
        ("load balancer", "aws", "aws.networking_content_delivery.ElasticLoadBalancing"),
        ("subnet", "azure", "frames.azure.Subnet"),
    ],
)
def test_the_class_meant_comes_first(query: str, library: str | None, expected: str) -> None:
    assert _first(query, library) == expected


def test_an_alias_finds_the_service() -> None:
    names = [hit.name for hit in find("aks", "azure")[:3]]
    assert "KubernetesServices" in names


def test_a_service_comes_before_the_glyphs_drawn_inside_it() -> None:
    hits = [
        hit for hit in find("simple storage", "aws") if hit.name.startswith("SimpleStorageService")
    ]
    assert hits[0].name == "SimpleStorageService" and not hits[0].glyph
    assert any(hit.glyph for hit in hits[1:])


def test_the_command_prints_import_lines_and_json(capsys) -> None:
    assert main(["s3", "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("from infragram.nodes.aws.storage import SimpleStorageService")
    assert main(["aks", "--library", "azure", "--json", "--limit", "2"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 2 and all(row["import"].startswith("from infragram.nodes.") for row in rows)
    assert main(["no-such-thing-anywhere"]) == 1


@pytest.mark.slow
def test_the_index_read_from_source_is_the_one_importing_gives() -> None:
    """``node_classes`` reads the generated modules' source (0.1 s) instead of
    importing all 600 (12 s); importing them must still name the same classes,
    the same way."""
    import importlib
    import pkgutil

    from infragram import nodes
    from infragram.catalog.find import node_classes

    imported = set()
    for info in pkgutil.walk_packages(nodes.__path__, prefix="infragram.nodes."):
        if info.ispkg or info.name.rsplit(".", 1)[1].startswith("_"):
            continue
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            if (
                isinstance(value, type)
                and not name.startswith("_")
                and value.__module__ == info.name
                and (getattr(value, "ICON", None) or getattr(value, "KIND", None))
            ):
                doc = (value.__doc__ or "").strip()
                title = str(getattr(value, "TYPE", "") or (doc.splitlines()[0] if doc else ""))
                imported.add(
                    (
                        info.name,
                        name,
                        str(getattr(value, "ICON", "") or ""),
                        title.strip().rstrip("."),
                    )
                )
    read = {(item.module, item.name, item.icon, item.title) for item in node_classes()}
    assert read == imported
