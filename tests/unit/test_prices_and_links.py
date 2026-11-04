"""What a component costs, and where it is read about.

Held here:

- every vendor library has a search of its own site, every link is https,
  EC2 has its own pages, and a component the table does not list gets a
  search for its name; the page carries the table;
- EC2 is priced from the price list the export fetches: the region from the
  frame around it, what the element does not say assumed and marked, what it
  says (``Element.sizing``) priced as said, a price it cannot give reported,
  never guessed, and a stale price removed; nothing else is priced;
- ``--prices`` prints what it priced and writes the price into the document;
- a fetched body is kept a day;
- (slow, needs the network) the real price list prices a t3.micro.
"""

from __future__ import annotations

import json

import pytest

from infragram.author import Diagram
from infragram.catalog.links import links_for, load_links
from infragram.nodes.aws import compute, databases, networking_content_delivery as net
from infragram.nodes.frames import aws
from infragram.paths import skill_assets
from infragram.pricing import PricingError, price_project
from infragram.pricing.aws import LOCATIONS, PRICE_FILE

RATES = {"t3.micro": "0.0104000000", "m6i.large": "0.0960000000"}


def _fake(
    requested: list[str], rates: dict[str, str] = RATES, published: str = "2026-09-24T16:51:17Z"
):
    """The network, as the two files AWS publishes: its locations and a price file."""

    def fetch(url: str) -> bytes:
        requested.append(url)
        if url == LOCATIONS:
            return json.dumps(
                {
                    "US East (N. Virginia)": {
                        "name": "US East (N. Virginia)",
                        "code": "us-east-1",
                        "type": "AWS Region",
                    },
                    "EU (Ireland)": {
                        "name": "EU (Ireland)",
                        "code": "eu-west-1",
                        "type": "AWS Region",
                    },
                    "Somewhere Local Zone": {
                        "name": "Somewhere Local Zone",
                        "code": "us-east-1-bos-1a",
                        "type": "AWS Local Zone",
                    },
                }
            ).encode()
        location = (
            url.split("ec2-ondemand-without-sec-sel/")[1]
            .split("/")[0]
            .replace("%20", " ")
            .replace("%28", "(")
            .replace("%29", ")")
        )
        rows = {
            f"{kind} {location}": {
                "price": price,
                "Instance Type": kind,
                "vCPU": "2",
                "Memory": "8 GiB",
            }
            for kind, price in rates.items()
        }
        return json.dumps(
            {
                "manifest": {"hawkFilePublicationDate": published, "currencyCode": "USD"},
                "regions": {location: rows},
            }
        ).encode()

    return fetch


def _diagram(sizing: dict | None = None, region: str | None = "eu-west-1"):
    with Diagram(
        "Priced", "Web servers and a database.", slug="priced", providers=("aws",)
    ) as diagram:
        with aws.Cloud("AWS Cloud"):
            if region:
                with aws.Region(region), aws.VPC("VPC 10.0.0.0/16"):
                    web = compute.EC2("Web servers")
                    databases.RDS("PostgreSQL")
            else:
                web = compute.EC2("Web servers")
            net.ElasticLoadBalancing("Load balancer") >> web
        if sizing:
            web.sizing(**sizing)
    return diagram.to_project()


def _price(project) -> dict:
    """The EC2's price: what the live pricer prices. The database and the
    load balancer are priced from the shipped table."""
    return next(
        element.attributes["price"]
        for element in _elements(project)
        if element.component is not None and element.component.service_id == "ec2"
    )


def _web_priced(result) -> bool:
    return any(element_id == "web-servers" for element_id, _ in result.priced)


def _elements(project):
    stack = [project.topology]
    while stack:
        element = stack.pop()
        yield element
        stack.extend(element.children)


# ------------------------------------------------------------------ links
def test_every_vendor_library_has_a_search_and_ec2_its_own_pages() -> None:
    providers = json.loads(
        (skill_assets() / "catalog" / "providers.json").read_text(encoding="utf-8")
    )
    libraries = {
        entry["id"]
        for entry in (providers["providers"] if isinstance(providers, dict) else providers)
    }
    table = load_links()
    assert set(table.libraries) == libraries - {"onprem"}, "Local & On-Premises names no vendor"
    urls = [library.search for library in table.libraries.values()]
    urls += [link.url for links in table.components.values() for link in links]
    assert all(url.startswith("https://") for url in urls)
    labels = [link.label for link in links_for("aws:ec2", "Amazon EC2")]
    assert labels == [
        "Product",
        "On-demand pricing",
        "Instance types",
        "Documentation",
        "Pricing calculator",
    ]
    (search,) = links_for("aws:elastic-load-balancing", "Elastic Load Balancing")
    assert search.url == "https://aws.amazon.com/search/?searchQuery=Elastic%20Load%20Balancing"
    (azure,) = links_for("azure:firewalls", "Firewalls & more")
    assert (
        azure.url.endswith("terms=Firewalls%20%26%20more")
        and azure.label == "Search learn.microsoft.com"
    )
    assert (
        links_for("onprem:server", "Server") == [] and links_for("infragram:users", "Users") == []
    )


def test_the_page_carries_the_links_of_the_libraries_it_embeds() -> None:
    """A card added in the page has its links too, and a card of a library
    the page does not embed cannot be added: its links stay out, a whole
    library's product pages (Databricks lists one a card) on every page."""
    from infragram.exports.render import render_project_html

    def carried(html: str) -> dict:
        start = html.index('id="infragram-component-links">') + len(
            'id="infragram-component-links">'
        )
        return json.loads(html[start : html.index("</script>", start)])

    links = carried(render_project_html(_diagram()))
    assert links["components"]["aws:ec2"][0]["url"] == "https://aws.amazon.com/ec2/"
    assert "aws" in links["libraries"] and "databricks" not in links["libraries"]
    assert not [key for key in links["components"] if key.startswith("databricks:")]
    every = carried(render_project_html(_diagram(), libraries="all"))
    assert set(every["libraries"]) == set(load_links().libraries)


# ------------------------------------------------------------------ pricing
def test_ec2_is_priced_from_its_frames_region_and_assumes_the_rest() -> None:
    requested: list[str] = []
    project = _diagram()
    result = price_project(project, source="live", fetch=_fake(requested), today="2026-09-25")
    assert _web_priced(result) and not result.notes
    price = _price(project)
    assert price["sizing"] == {
        "instance_type": "t3.micro",
        "region": "eu-west-1",
        "os": "Linux",
        "count": 1,
        "hours": 730,
    }
    assert price["assumed"] == ["instance_type", "os", "count", "hours"]
    assert price["hourly"] == 0.0104 and price["monthly"] == round(0.0104 * 730, 2)
    assert price["published"] == "2026-09-24" and price["priced"] == "2026-09-25"
    assert requested[1] == PRICE_FILE.format(location="EU%20%28Ireland%29", os="Linux")
    assert price["rate"].startswith("EC2 on-demand, Linux, shared tenancy")


def test_a_sizing_the_element_states_is_priced_as_stated() -> None:
    requested: list[str] = []
    project = _diagram(
        {"instance_type": "m6i.large", "count": 3, "os": "windows", "hours": 200}, region=None
    )
    price_project(project, source="live", fetch=_fake(requested), today="2026-09-25")
    price = _price(project)
    assert price["sizing"]["os"] == "Windows" and price["assumed"] == ["region"]
    assert price["monthly"] == round(0.096 * 200 * 3, 2)
    assert requested[1].endswith("/US%20East%20%28N.%20Virginia%29/Windows/index.json")


@pytest.mark.parametrize(
    ("sizing", "says"),
    [
        ({"instance_type": "x9.huge"}, "no on-demand Linux rate for x9.huge"),
        ({"instance_type": "large"}, "is not an EC2 instance type"),
        ({"region": "moon-1"}, "is not an AWS region"),
        ({"region": "ap-mars-9"}, "AWS lists no region"),
        ({"os": "BeOS"}, "no EC2 price file for the operating system"),
        ({"count": 0}, "whole number of instances"),
        ({"hours": 1000}, "hours a month"),
        ({"storage": 10}, "EC2 sizing takes"),
    ],
)
def test_a_price_it_cannot_give_is_reported_never_guessed(sizing: dict, says: str) -> None:
    project = _diagram(sizing)
    web = next(element for element in _elements(project) if element.id == "web-servers")
    web.attributes["price"] = {"monthly": 1.0, "origin": "live"}  # a price an earlier export wrote
    result = price_project(project, source="live", fetch=_fake([]), today="2026-09-25")
    assert not _web_priced(result) and len(result.notes) == 1 and says in result.notes[0], (
        result.notes
    )
    assert "price" not in web.attributes


def test_a_price_list_that_changed_shape_is_reported() -> None:
    def broken(url: str) -> bytes:
        return b"<html>moved</html>" if url != LOCATIONS else _fake([])(url)

    result = price_project(_diagram(), source="live", fetch=broken, today="2026-09-25")
    assert "is not the JSON AWS publishes" in result.notes[0]


def test_live_prices_what_it_fetches_and_the_rest_from_the_tables() -> None:
    project = _diagram()
    db = next(element for element in _elements(project) if element.id == "postgresql")
    db.attributes["price"] = {"monthly": 1.0, "origin": "live"}  # an earlier export's
    result = price_project(project, source="live", fetch=_fake([]), today="2026-09-25")
    priced = sorted(element.id for element in _elements(project) if "price" in element.attributes)
    assert priced == ["load-balancer", "postgresql", "web-servers"] and not result.unpriced
    # the EC2 fetched now, the database from the shipped table, replacing the old price
    assert _price(project)["origin"] == "live"
    assert db.attributes["price"]["origin"] == "table" and db.attributes["price"]["monthly"] != 1.0


def test_every_region_aws_lists_is_a_region() -> None:
    from infragram.pricing.aws import REGION

    for code in (
        "us-east-1",
        "us-gov-west-1",
        "eusc-de-east-1",
        "us-east-2-mci-1",
        "ap-southeast-4",
    ):
        assert REGION.fullmatch(code), code
    assert REGION.search("Region · eu-west-1").group(1) == "eu-west-1"
    assert REGION.search("us-east-1a") is None, "an availability zone is no region"


def test_a_price_file_that_is_not_an_object_or_lists_no_rates_is_a_note() -> None:
    for body in (b"[1, 2]", b'{"regions": {"EU (Ireland)": ["no", "rates"]}}'):

        def fetch(url: str, body=body) -> bytes:
            return _fake([])(url) if url == LOCATIONS else body

        result = price_project(_diagram(), source="live", fetch=fetch, today="2026-09-25")
        assert not _web_priced(result) and result.notes, body


def test_sizing_is_written_on_the_element_and_checked() -> None:
    from infragram.nodes.aws.compute import EC2

    with Diagram("Sized", "One server.", slug="sized", providers=("aws",)):
        web = EC2("web").sizing(instance_type="t3.small").sizing(count=2)
        assert web.attributes["sizing"] == {"instance_type": "t3.small", "count": 2}
        with pytest.raises(ValueError, match="at least one value"):
            web.sizing()
        with pytest.raises(ValueError, match="text or a number"):
            web.sizing(count=True)


def test_an_imported_instance_is_priced_and_written_as_the_type_it_is(
    tmp_path, monkeypatch
) -> None:
    """The import reads the instance type; the diagram file says it as
    ``.sizing``; the price and the Terraform export both use it."""
    from infragram.cli.user.compose import project_from_spec
    from infragram.cli.user.import_estate import import_terraform
    from infragram.terraform import terraform_files

    folder = tmp_path / "tf"
    folder.mkdir()
    (folder / "main.tf").write_text(
        'provider "aws" {\n  region = "eu-west-1"\n}\n'
        'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}\n'
        'resource "aws_subnet" "app" {\n  vpc_id     = aws_vpc.main.id\n  cidr_block = "10.0.1.0/24"\n}\n'
        'resource "aws_instance" "web" {\n  ami           = "ami-123"\n  instance_type = "m6i.large"\n'
        "  subnet_id     = aws_subnet.app.id\n}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert import_terraform(["tf", "--no-export", "--output-dir", "out"]) == 0
    spec = next((tmp_path / "out").glob("*.py"))
    assert ".sizing(instance_type='m6i.large')" in spec.read_text(encoding="utf-8")
    project = project_from_spec(spec)
    price_project(project, source="live", fetch=_fake([]), today="2026-09-25")
    price = _price(project)
    assert (
        price["sizing"]["instance_type"] == "m6i.large" and "instance_type" not in price["assumed"]
    )
    _plan, files = terraform_files(project)
    assert any('default     = "m6i.large"' in text for text in files.values())


# ------------------------------------------------------------------ export
def test_the_export_prints_what_it_priced_and_the_document_carries_it(
    tmp_path, monkeypatch, capsys
) -> None:
    from infragram.cli.user.export_project import main
    from infragram.pricing import fetch

    monkeypatch.setattr(fetch, "cached_fetch", _fake([]))
    document = tmp_path / "priced.infragram.json"
    document.write_text(
        _diagram({"instance_type": "m6i.large"}).model_dump_json(exclude_none=True),
        encoding="utf-8",
    )
    assert (
        main(
            [
                str(document),
                "--formats",
                "template",
                "--output-dir",
                str(tmp_path / "out"),
                "--prices",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    out = captured.out
    assert (
        "PRICED   web-servers: USD 70.08 a month (EC2 on-demand, Linux, shared tenancy, 2 vCPU, 8 GiB; assumed os, count, hours)"
        in out
    )
    # the total says what it covers; the database and the load balancer are
    # priced from the shipped table, or named as not priced where none is
    assert "cloud components" in out and "a month, on-demand list prices" in out
    written = json.loads((tmp_path / "out" / "priced.infragram.json").read_text(encoding="utf-8"))
    assert '"monthly": 70.08' in json.dumps(written)


def test_a_fetched_body_is_kept_a_day(tmp_path, monkeypatch) -> None:
    from infragram.pricing import fetch

    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path))
    calls: list[str] = []
    monkeypatch.setattr(fetch, "fetch_url", lambda url: calls.append(url) or b"{}")
    assert (
        fetch.cached_fetch("https://example.com/a")
        == b"{}"
        == fetch.cached_fetch("https://example.com/a")
    )
    assert calls == ["https://example.com/a"]
    import os
    import time

    (stale,) = (tmp_path / "pricing").iterdir()
    os.utime(stale, (time.time() - fetch.KEEP - 60,) * 2)
    fetch.cached_fetch("https://example.com/a")
    assert len(calls) == 2


def test_a_body_that_is_not_json_is_never_kept(tmp_path, monkeypatch) -> None:
    from infragram.pricing import fetch

    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path))
    monkeypatch.setattr(fetch, "fetch_url", lambda url: b"<html>sign in to the wifi</html>")
    with pytest.raises(PricingError, match="did not answer with JSON"):
        fetch.cached_fetch("https://example.com/b")
    assert not any((tmp_path / "pricing").iterdir())


@pytest.mark.slow
def test_the_real_price_list_prices_a_t3_micro() -> None:
    """Needs the network: the files AWS publishes still have the shape read here."""
    from infragram.pricing.fetch import fetch_url

    try:
        fetch_url("https://b0.p.awsstatic.com/locations/1.0/aws/current/locations.json")
    except PricingError as error:
        # a file that answers 404 moved: that fails; only no network skips
        if "answered HTTP" in str(error):
            raise
        pytest.skip(f"no network: {error}")
    project = _diagram(region="us-east-1")
    result = price_project(project, source="live", fetch=fetch_url)
    assert not result.notes, result.notes
    price = _price(project)
    assert 0.001 < price["hourly"] < 1 and price["published"][:2] == "20"
