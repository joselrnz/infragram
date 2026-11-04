"""Patterns build once, expose parts by key, and compose into a Blueprint that
exports deterministically."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from infragram import compose
from infragram.exports import ExportResult
from infragram.models.topology import TopologyElement
from infragram.nodes import infragram as shared, reset_ids
from infragram.nodes.aws import compute, security_identity as sec
from infragram.nodes.frames import aws as frames
from infragram.patterns import Blueprint, Pattern, PatternError
from infragram.patterns.aws import EndpointSubnet, Guardrails, MultiAZ, Zone
from infragram.patterns.hybrid import DirectConnectUplink

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


@pytest.fixture(autouse=True)
def _fresh_ids():
    reset_ids()


class Pair(Pattern):
    """The smallest pattern: two nodes in a frame, both registered."""

    def build(self) -> TopologyElement:
        frame = frames.PrivateSubnet(self.name)
        self.part("web", frame >> compute.EC2("Web", "app"))
        self.part("db", frame >> compute.EC2("DB", "data"))
        return frame


# ---------------------------------------------------------------- Pattern
def test_a_pattern_builds_once_on_first_use() -> None:
    pair = Pair("Tier")
    assert not pair.built
    frame = pair.elements[0]
    assert pair.built
    assert pair.elements[0] is frame, "a second look must not rebuild"
    assert set(pair.parts) == {"web", "db"}
    assert pair["web"].name == "Web"
    assert len(pair) == 2 and "db" in pair and sorted(pair) == ["db", "web"]


def test_an_unknown_part_names_the_ones_that_exist() -> None:
    with pytest.raises(PatternError, match="no part 'cache'; it has: db, web"):
        Pair("Tier")["cache"]


def test_a_part_key_is_registered_once() -> None:
    class Twice(Pattern):
        def build(self) -> TopologyElement:
            frame = frames.PrivateSubnet(self.name)
            self.part("web", frame >> compute.EC2("A"))
            self.part("web", frame >> compute.EC2("B"))
            return frame

    with pytest.raises(PatternError, match="already has a part named 'web'"):
        Twice("Tier").realise()


def test_settings_are_fixed_once_built() -> None:
    pair = Pair("Tier")
    pair.name = "Renamed"
    assert pair.elements[0].name == "Renamed"
    with pytest.raises(PatternError, match="already built"):
        pair.name = "Too late"
    with pytest.raises(PatternError, match="non-empty"):
        Pair("Tier").name = "  "


def test_attach_nests_every_element_under_the_parent() -> None:
    vpc = frames.VPC("VPC")
    pair = Pair("Tier").attach(vpc)
    assert vpc.children == list(pair.elements)


def test_an_empty_build_is_an_error() -> None:
    class Nothing(Pattern):
        def build(self):
            return []

    with pytest.raises(PatternError, match="produced nothing"):
        Nothing("x").realise()


# -------------------------------------------------------------- AWS ones
def test_guardrails_default_to_the_usual_four_and_key_parts_by_slug() -> None:
    rails = Guardrails()
    assert rails.name == "Account-wide services"
    assert [child.name for child in rails.elements[0].children] == [
        "Amazon GuardDuty",
        "AWS CloudTrail",
        "AWS Security Hub",
        "AWS Config",
    ]
    assert rails["amazon-guardduty"].attributes["icon"] == "guardduty"


def test_guardrails_take_an_estates_own_services() -> None:
    rails = Guardrails("Watch", services=((sec.Macie, "Macie", "PII"),))
    assert [child.name for child in rails.elements[0].children] == ["Macie"]
    with pytest.raises(PatternError, match="at least one service"):
        Guardrails(services=())


def test_a_zone_takes_one_letter_and_fills_only_the_subnets_it_is_given() -> None:
    with pytest.raises(PatternError, match="one letter"):
        Zone("AB")

    def private(subnet, zone):
        zone.part("web", subnet >> compute.EC2("Web"))

    zone = Zone("a", private=private)
    frame = zone.elements[0]
    assert frame.name == "Availability Zone A"
    assert [child.name for child in frame.children] == ["Private subnet A"]
    assert "public" not in zone and zone["web"].name == "Web"


def test_multi_az_repeats_one_recipe_across_lettered_zones() -> None:
    def public(subnet, zone):
        zone.part("nat", subnet >> shared.networking.NetworkGateway("NAT Gateway"))

    def private(subnet, zone):
        zone.part("web", subnet >> compute.EC2("Web", zone.letter))

    zones = MultiAZ(3, public=public, private=private)
    assert zones.letters == ("A", "B", "C")
    assert [frame.name for frame in zones.elements] == [
        "Availability Zone A",
        "Availability Zone B",
        "Availability Zone C",
    ]
    assert [node.attributes["detail"] for node in zones.each("web")] == ["A", "B", "C"]
    assert zones.part_for("nat", "b").name == "NAT Gateway"
    assert zones["zone:C"] is zones.elements[2]
    assert len(zones.zones) == 3


def test_multi_az_draws_one_to_six_zones() -> None:
    for count in (0, 7):
        with pytest.raises(PatternError, match="1 to 6 zones"):
            MultiAZ(count)
    zones = MultiAZ(1)
    zones.count = 2
    zones.realise()
    with pytest.raises(PatternError, match="already built"):
        zones.count = 3


def test_endpoint_subnet_draws_each_endpoint_as_the_service_it_fronts() -> None:
    subnet = EndpointSubnet("A", ((sec.KeyManagementService, "KMS endpoint", "interface"),))
    assert subnet.elements[0].name == "Private subnet · endpoints A"
    assert subnet["kms-endpoint"].attributes["icon"] == "key-management-service"
    with pytest.raises(PatternError, match="at least one service"):
        EndpointSubnet("A", ())


# --------------------------------------------------------------- hybrid
def test_direct_connect_uplink_draws_the_site_the_location_and_the_circuit() -> None:
    uplink = DirectConnectUplink("HQ", bandwidth="1 Gbps dedicated", asn="AS 64512")
    site, location = uplink.elements
    assert site.name == "HQ" and location.name == "Direct Connect location"
    assert set(uplink.parts) == {"site", "edge", "firewall", "router", "location", "circuit"}
    assert uplink["router"].attributes["detail"] == "BGP · AS 64512"
    assert uplink["circuit"].attributes["detail"] == "1 Gbps dedicated"
    wire = next(c for c in uplink["router"].connections if c.target == uplink["circuit"].id)
    assert wire.kind == "dashed" and wire.label == "MACsec · BGP"
    with pytest.raises(PatternError, match="already built"):
        uplink.bandwidth = "10 Gbps"


# ------------------------------------------------------------- Blueprint
def test_a_blueprint_checks_its_words_as_they_are_set() -> None:
    with pytest.raises(PatternError, match="lower-case words"):
        Blueprint("Bad Slug", "T", "d")
    with pytest.raises(PatternError, match="needs a title"):
        Blueprint("ok", " ", "d")
    with pytest.raises(PatternError, match="needs a description"):
        Blueprint("ok", "T", "")
    with pytest.raises(PatternError, match="display must be"):
        Blueprint("ok", "T", "d", display="sticker")
    with pytest.raises(PatternError, match="theme must be"):
        Blueprint("ok", "T", "d", theme="sepia")


def test_a_blueprint_places_elements_and_patterns_and_writes_the_display() -> None:
    plan = Blueprint.fresh("estate", "Estate", "An estate.", display="icon")
    (cloud,) = plan.add(frames.Cloud("AWS Cloud"))
    vpc = cloud >> frames.VPC("VPC")
    pair = Pair("Tier").attach(vpc)
    rails = Guardrails()
    plan.add(*rails.elements)
    plan.link(pair["web"], pair["db"], label="SQL")

    assert plan.elements == (cloud, rails.elements[0])
    project = plan.to_project()
    assert project.presentation.display == "icon"
    assert project.slug == "estate" and project.kind == "single-cloud"
    assert project.topology.index()[pair["web"].id].connections[0].label == "SQL"


def test_a_blueprint_refuses_what_it_cannot_place() -> None:
    plan = Blueprint("estate", "Estate", "An estate.")
    with pytest.raises(PatternError, match="node or frame instances"):
        plan.add("not a node")  # type: ignore[arg-type]
    (cloud,) = plan.add(frames.Cloud("AWS Cloud"))
    with pytest.raises(PatternError, match="already at the top level"):
        plan.add(cloud)
    with pytest.raises(PatternError, match="at least one element"):
        Blueprint("empty", "E", "e.").to_project()


def test_the_project_is_cached_until_the_plan_changes() -> None:
    plan = Blueprint("estate", "Estate", "An estate.")
    plan.add(frames.Cloud("AWS Cloud"))
    first = plan.to_project()
    assert plan.to_project() is first
    plan.display = "icon"
    second = plan.to_project()
    assert second is not first and second.presentation.display == "icon"


def test_export_goes_through_compose_with_the_plans_theme_and_display(
    monkeypatch, tmp_path
) -> None:
    seen: dict = {}

    def fake_export_project(project, output_dir, **options):
        seen.update(options, slug=project.slug, output_dir=output_dir)
        return ExportResult(html=output_dir / f"{project.slug}.html")

    monkeypatch.setattr(compose.document, "export_project", fake_export_project)
    plan = Blueprint("estate", "Estate", "An estate.", theme="dark", display="icon")
    plan.add(frames.Cloud("AWS Cloud"))
    result = plan.export(tmp_path, formats=("html",), display="both")
    assert result.html == tmp_path / "estate.html"
    assert seen["theme"] == "dark" and seen["display"] == "both" and seen["formats"] == ("html",)
    with pytest.raises(PatternError, match="display must be"):
        plan.export(tmp_path, display="poster")


def test_export_many_needs_one_theme_or_an_explicit_one(monkeypatch, tmp_path) -> None:
    import infragram.patterns.blueprint as blueprint_module

    captured: dict = {}

    def fake_export_many(projects, output_dir, *, concurrency, **options):
        captured["slugs"] = [project.slug for project in projects]
        captured.update(options, concurrency=concurrency)
        return []

    monkeypatch.setattr(blueprint_module, "export_many", fake_export_many)
    light = Blueprint("a", "A", "a.")
    light.add(frames.Cloud("AWS Cloud"))
    dark = Blueprint("b", "B", "b.", theme="dark")
    dark.add(frames.Cloud("AWS Cloud"))
    with pytest.raises(PatternError, match="these differ: dark, light"):
        Blueprint.export_many([light, dark], tmp_path)
    Blueprint.export_many([light, dark], tmp_path, theme="light", concurrency=4)
    assert captured["slugs"] == ["a", "b"] and captured["theme"] == "light"
    assert captured["concurrency"] == 4


# -------------------------------------------------------- the examples
@pytest.mark.parametrize(
    "example",
    [
        "hybrid_direct_connect_staging.py",
        "aws_rstudio_shiny.py",
    ],
)
def test_the_pattern_built_examples_are_deterministic(example: str) -> None:
    """Same code, same ids, same document: what lets a team diff a diagram."""
    path = ROOT / "plugin" / "examples" / example
    first = (
        runpy.run_path(str(path), run_name="__spec__")["diagram"]
        .to_project()
        .model_dump(mode="json")
    )
    second = (
        runpy.run_path(str(path), run_name="__spec__")["diagram"]
        .to_project()
        .model_dump(mode="json")
    )
    assert first == second
    # Which look it draws is the example's to choose -- most follow the
    # document default and one asks for cards because it mixes the two.
    # That the two runs agree on it is the part this is about.
    assert first["presentation"]["display"] in {"card", "icon"}
