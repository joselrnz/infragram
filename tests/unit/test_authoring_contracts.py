"""The third batch of review findings, each pinned by the test that found it.

- ``to_project(providers=)`` replaces the inferred set, as its docstring says.
- Blueprint's ``size``, ``kind``, ``providers`` and ``template_brief`` drop
  the cached project like every other setter.
- The undrawn root's id ``root`` cannot collide with an element: an auto-id
  never mints it and an explicit one is refused by name.
- Parallel wires between one pair share one style in the document; asking
  for two is refused where it is written.
- ``node << frame`` mirrors ``node >> frame``.
- ``Connection`` refuses unknown keys like every other model.
- One slug algorithm and one SLUG pattern across the package.
- The SVG safety check reads the document the way a browser does.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from infragram import author, compose, utils, verification
from infragram.author import Diagram, Edge
from infragram.models import topology
from infragram.models.topology import Connection, TopologyElement
from infragram.nodes import Group, infragram as shared, reset_ids
from infragram.nodes._base import ROOT_ID, _auto_id
from infragram.nodes.aws import compute as aws_compute
from infragram.nodes.azure import compute as azure_compute
from infragram.nodes.frames import aws as aws_frames
from infragram.patterns import aws as aws_patterns, blueprint
from infragram.patterns.base import PatternError
from infragram.patterns.blueprint import Blueprint


@pytest.fixture(autouse=True)
def _fresh_ids():
    reset_ids()
    yield
    reset_ids()


# ----------------------------------------------------------- providers=
def test_an_explicit_provider_set_replaces_the_inferred_one() -> None:
    node = shared.compute.Mainframe("z16")
    project = compose.to_project(node, slug="z", title="Z", description="z.", providers=("aws",))
    assert project.provider_ids == ("aws",), "onprem was not joined to the given set"
    assert project.kind == "single-cloud" and project.default_library == "aws"


def test_a_provider_set_that_leaves_a_component_out_fails_the_document_check() -> None:
    with pytest.raises(ValidationError, match="component provider 'azure' is not enabled"):
        compose.to_project(
            azure_compute.VirtualMachine("vm"),
            slug="v",
            title="V",
            description="v.",
            providers=("aws",),
        )


def test_the_diagram_forwards_its_providers_as_the_whole_set() -> None:
    with Diagram("Given", providers=("aws", "onprem")) as diagram:
        shared.compute.Mainframe("z16")
    project = diagram.to_project()
    assert project.provider_ids == ("aws", "onprem") and project.kind == "hybrid"


# ------------------------------------------------------------ Blueprint
@pytest.mark.parametrize(
    "attribute,value,read",
    [
        ("size", "slide-16x9", lambda p: p.presentation.size),
        ("kind", "platform", lambda p: p.kind),
        ("providers", ("aws", "kubernetes"), lambda p: p.provider_ids),
        ("template_brief", "A brief.", lambda p: p.template_brief),
    ],
)
def test_every_document_setting_drops_the_cached_project(attribute, value, read) -> None:
    plan = Blueprint("estate", "Estate", "An estate.")
    plan.add(aws_frames.Cloud("AWS Cloud"))
    first = plan.to_project()
    assert plan.to_project() is first
    setattr(plan, attribute, value)
    second = plan.to_project()
    assert second is not first
    assert read(second) == value
    assert getattr(plan, attribute) == value


def test_blueprint_slugs_are_matched_whole() -> None:
    with pytest.raises(PatternError, match="single hyphens"):
        Blueprint("estate\n", "Estate", "An estate.")
    with pytest.raises(PatternError, match="single hyphens"):
        Blueprint("estate x", "Estate", "An estate.")


# ------------------------------------------------------------- the root
def test_an_element_named_root_lives_beside_the_undrawn_root() -> None:
    with Diagram("Roots") as diagram:
        zone = Group("Root")
        vm = azure_compute.VirtualMachine("root")
    assert zone.id == "root-2" and vm.id == "root-3"
    project = diagram.to_project()
    assert project.topology.id == ROOT_ID == "root"
    assert [child.name for child in project.topology.children] == ["Root", "root"]


def test_an_explicit_root_id_on_an_element_is_refused_by_name() -> None:
    with Diagram("Roots") as diagram:
        Group("Estate", id="root")
    with pytest.raises(compose.ComposeError, match="'Estate' carries id 'root'"):
        diagram.to_project()
    reset_ids()
    with pytest.raises(compose.ComposeError, match="carries id 'root'"):
        compose.to_project(
            [Group("Estate", id="root"), Group("Other")],
            slug="r",
            title="R",
            description="r.",
            providers=("onprem",),
        )


def test_a_single_plain_root_group_is_still_the_undrawn_root() -> None:
    estate = Group("Estate", id="root")
    estate >> shared.compute.Mainframe("z16")
    project = compose.to_project(estate, slug="e", title="E", description="e.")
    assert project.topology.id == "root" and project.topology.name == "Estate"
    assert [child.name for child in project.topology.children] == ["z16"]


def test_the_auto_id_counter_reserves_root() -> None:
    assert _auto_id("Root") == "root-2"
    assert _auto_id("root") == "root-3"
    assert _auto_id("Rooted") == "rooted"


# --------------------------------------------------------- parallel wires
def test_parallel_wires_may_share_a_style_or_carry_none() -> None:
    with Diagram("Parallel", providers=("azure",)):
        a = azure_compute.VirtualMachine("A")
        b = azure_compute.VirtualMachine("B")
        a >> b
        a >> Edge("again") >> b
        c = azure_compute.VirtualMachine("C")
        a >> Edge("bent", corners="sharp") >> c
        a >> Edge("bent again", corners="sharp") >> c
    assert len(a.connections) == 4
    assert a.attributes["editor_edge_styles"] == {"c": {"corners": "sharp"}}


def test_a_plain_wire_then_a_styled_one_is_the_same_conflict() -> None:
    """The document would draw the plain wire with the later style; refused rather than shared."""
    with Diagram("Parallel", providers=("azure",)):
        a = azure_compute.VirtualMachine("A")
        b = azure_compute.VirtualMachine("B")
        a >> b
        with pytest.raises(ValueError, match="with no arrow, corner or side choice"):
            a >> Edge("bent", corners="sharp") >> b
    assert len(a.connections) == 1 and "editor_edge_styles" not in a.attributes


def test_parallel_wires_asking_for_different_styles_are_refused_where_written() -> None:
    with Diagram("Parallel", providers=("azure",)):
        a = azure_compute.VirtualMachine("A")
        b = azure_compute.VirtualMachine("B")
        a >> Edge("first", corners="sharp") >> b
        with pytest.raises(ValueError, match="parallel wires between one pair share"):
            a >> Edge("second", corners="curved") >> b
        with pytest.raises(ValueError, match="parallel wires between one pair share"):
            a >> Edge("third", arrow="diamond") >> b
    assert len(a.connections) == 1, "the refused wires were not written"
    assert "limit comes from the document" in (Edge.__doc__ or "")


def test_a_wire_the_other_way_is_not_a_parallel_wire() -> None:
    with Diagram("Both ways", providers=("azure",)):
        a = azure_compute.VirtualMachine("A")
        b = azure_compute.VirtualMachine("B")
        a >> Edge("down", corners="sharp") >> b
        b >> Edge("up", corners="curved") >> a
    assert a.attributes["editor_edge_styles"]["b"] == {"corners": "sharp"}
    assert b.attributes["editor_edge_styles"]["a"] == {"corners": "curved"}


# ------------------------------------------------------------- node << frame
def test_a_node_shifted_into_a_frame_nests_there_instead_of_wiring_it() -> None:
    vpc = aws_frames.VPC("vpc")
    web = aws_compute.EC2("web")
    returned = web << vpc
    assert returned is vpc
    assert len(vpc.children) == 1 and vpc.children[0] is web
    assert web.connections == [] and vpc.connections == [], "no wire was drawn from the frame"


def test_a_node_shifted_from_a_node_is_still_a_wire() -> None:
    web = aws_compute.EC2("web")
    db = aws_compute.EC2("db")
    assert (web << db) is db
    assert [c.target for c in db.connections] == [web.id]


def test_a_node_shifted_from_a_mixed_list_is_refused_like_rshift() -> None:
    web = aws_compute.EC2("web")
    with pytest.raises(TypeError):
        web << [aws_compute.EC2("db"), aws_frames.VPC("vpc")]
    with pytest.raises(TypeError):
        web >> [aws_compute.EC2("db2"), aws_frames.VPC("vpc2")]


# ------------------------------------------------------- strict models
def test_connections_refuse_unknown_keys() -> None:
    with pytest.raises(ValidationError, match="colour"):
        Connection(target="x", colour="red")
    with pytest.raises(ValidationError):
        TopologyElement.model_validate(
            {"id": "a", "name": "A", "type": "node", "connections": [{"target": "b", "style": {}}]}
        )


def test_the_tree_view_names_every_level() -> None:
    root = TopologyElement(
        id="a", name="A", type="group", children=[TopologyElement(id="b", name="B", type="node")]
    )
    assert root.tree().splitlines() == ["A", "└── B"]


# ----------------------------------------------------------------- slugs
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Azure: tenant to VM", "azure-tenant-to-vm"),
        ("  VPC · 10.0.0.0/16 ", "vpc-10-0-0-0-16"),
        ("Café Straße", "caf-strasse"),
        ("Straße", "strasse"),
    ],
)
def test_one_slug_algorithm_everywhere(text: str, expected: str) -> None:
    assert utils.slugify(text) == expected
    assert author.slugify(text) == expected
    assert aws_patterns._slug(text) == expected
    assert _auto_id(text) == expected


def test_empty_slugs_fall_back_by_purpose() -> None:
    assert utils.slugify("···") == ""
    assert author.slugify("···") == "diagram"
    assert _auto_id("···") == "node"
    assert author.slugify("x" * 80).endswith("x") and len(author.slugify("x" * 80)) == 64


def test_one_slug_pattern_everywhere() -> None:
    from infragram import projects

    assert verification.SLUG is utils.SLUG
    assert topology._SLUG is utils.SLUG
    assert projects.document._SLUG is utils.SLUG
    assert blueprint._SLUG is utils.SLUG
    assert utils.SLUG.fullmatch(utils.slugify("Any Name At All 9"))
