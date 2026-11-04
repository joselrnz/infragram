"""Google Cloud prices: the table built from the Cloud Billing Catalog API,
and the pricers that read it.

Held here, with no network:

- the builder refuses to run without an API key, and says how to get one;
- with one, it pages through the Catalog API's services and SKUs, keeps
  on-demand USD rates (units + nanos, the first tier with a price), files
  each under the regions it is sold in (the most specific SKU wins), keeps
  the key out of the cache and out of its errors, and reads the machine
  types from the machine-family pages' tables;
- a machine type is priced as vCPUs x core rate + GiB x RAM rate, a
  shared-core type at its share of a vCPU; Cloud SQL high availability at
  the regional rate; GKE's cluster fee; Cloud Storage's usage defaults,
  each marked assumed;
- an unknown machine type, a region the table does not hold and a sizing
  key no pricer reads are refused, never priced as a default.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from infragram.author import Diagram
from infragram.nodes.frames import gcp as frames
from infragram.nodes.gcp import core_products as gcp
from infragram.pricing import PricingError, price_project, tables as tables_module
from infragram.pricing.ask import HOURS, Ask
from infragram.pricing.build import gcp as builder, write_table
from infragram.pricing.gcp import COVERAGE
from infragram.pricing.tables import load_table

KEY = "AIza-test-key-not-real"
TODAY = "2026-10-08"


# ------------------------------------------------------------------ fixtures
def _money(price: float) -> dict:
    units = int(price)
    return {"currencyCode": "USD", "units": str(units), "nanos": round((price - units) * 1e9)}


def _sku(
    description: str,
    price: float,
    unit: str,
    regions: list[str],
    *,
    service: str = "Compute Engine",
    usage: str = "OnDemand",
    free_first: float = 0,
) -> dict:
    """One SKU as the Catalog API answers it."""
    tiers = [{"startUsageAmount": 0, "unitPrice": _money(price)}]
    if free_first:
        tiers = [
            {"startUsageAmount": 0, "unitPrice": _money(0)},
            {"startUsageAmount": free_first, "unitPrice": _money(price)},
        ]
    return {
        "name": f"services/x/skus/{abs(hash(description)) % 10**8:08d}",
        "skuId": f"{abs(hash(description)) % 10**8:08d}",
        "description": description,
        "category": {
            "serviceDisplayName": service,
            "resourceFamily": "Compute",
            "resourceGroup": "CPU",
            "usageType": usage,
        },
        "serviceRegions": regions,
        "pricingInfo": [
            {
                "summary": "",
                "pricingExpression": {
                    "usageUnit": unit,
                    "displayQuantity": 1,
                    "tieredRates": tiers,
                    "usageUnitDescription": unit,
                },
                "currencyConversionRate": 1,
                "effectiveTime": "2026-10-01T07:31:05.123Z",
            }
        ],
        "serviceProviderName": "Google",
    }


AMERICAS = ["us-central1", "us-east1"]
SERVICES = [
    [("6F81-5844-456A", "Compute Engine"), ("9662-B51E-5089", "Cloud SQL")],
    [("CCD8-9BF1-090E", "Kubernetes Engine"), ("95FF-2EF5-5EA1", "Cloud Storage")],
]
SKUS = {
    "6F81-5844-456A": [
        [
            _sku("E2 Instance Core running in Americas", 0.02181159, "h", AMERICAS),
            _sku("E2 Instance Ram running in Americas", 0.00292333, "GiBy.h", AMERICAS),
            _sku("E2 Instance Core running in Belgium", 0.02397004, "h", ["europe-west1"]),
            _sku("E2 Instance Ram running in Belgium", 0.00321311, "GiBy.h", ["europe-west1"]),
            _sku(
                "Spot Preemptible E2 Instance Core running in Americas",
                0.00654,
                "h",
                AMERICAS,
                usage="Preemptible",
            ),
            _sku(
                "Commitment v1: E2 Cpu in Americas for 1 Year",
                0.0137,
                "h",
                AMERICAS,
                usage="Commit1Yr",
            ),
        ],
        [
            _sku("N2 Instance Core running in Americas", 0.031611, "h", AMERICAS),
            # sold in one region only: wins there over the Americas SKU
            _sku("N2 Instance Core running in Iowa", 0.031, "h", ["us-central1"]),
            _sku("N2 Instance Ram running in Americas", 0.004237, "GiBy.h", AMERICAS),
            _sku("N2 Custom Instance Core running in Americas", 0.033191, "h", AMERICAS),
            _sku("N2 Custom Instance Ram running in Americas", 0.004449, "GiBy.h", AMERICAS),
            _sku("Nvidia Tesla A100 GPU running in Americas", 2.933908, "h", AMERICAS),
            _sku("Balanced PD Capacity", 0.1, "GiBy.mo", AMERICAS),
            _sku("Storage PD Capacity", 0.04, "GiBy.mo", AMERICAS),
            _sku(
                "Licensing Fee for Windows Server 2022 Datacenter Edition (CPU cost)",
                0.046,
                "h",
                ["global"],
            ),
        ],
    ],
    "9662-B51E-5089": [
        [
            _sku(
                f"Cloud SQL for PostgreSQL: {ha} - {item} in Americas",
                rate,
                unit,
                AMERICAS,
                service="Cloud SQL",
            )
            for ha, item, rate, unit in (
                ("Zonal", "vCPU", 0.0413, "h"),
                ("Zonal", "RAM", 0.007, "GiBy.h"),
                ("Regional", "vCPU", 0.0826, "h"),
                ("Regional", "RAM", 0.014, "GiBy.h"),
                ("Zonal", "Standard storage", 0.17, "GiBy.mo"),
                ("Regional", "Standard storage", 0.34, "GiBy.mo"),
            )
        ]
    ],
    "CCD8-9BF1-090E": [
        [
            _sku("Regional Kubernetes Clusters", 0.1, "h", ["global"], service="Kubernetes Engine"),
            _sku(
                "Autopilot Pod mCPU Requests (us-central1)",
                0.0445,
                "h",
                ["us-central1"],
                service="Kubernetes Engine",
            ),
            _sku(
                "Autopilot Pod Memory Requests (us-central1)",
                0.0049225,
                "GiBy.h",
                ["us-central1"],
                service="Kubernetes Engine",
            ),
        ]
    ],
    "95FF-2EF5-5EA1": [
        [
            _sku(
                "Standard Storage US Multi-region",
                0.026,
                "GiBy.mo",
                ["us"],
                service="Cloud Storage",
            ),
            _sku(
                "Standard Storage Iowa", 0.02, "GiBy.mo", ["us-central1"], service="Cloud Storage"
            ),
            _sku(
                "Regional Standard Class A Operations",
                0.000005,
                "count",
                ["global"],
                service="Cloud Storage",
                free_first=5000,
            ),
            _sku(
                "Regional Standard Class B Operations",
                0.0000004,
                "count",
                ["global"],
                service="Cloud Storage",
            ),
        ]
    ],
}

PAGES = {
    "general-purpose-machines": """
<h3>E2 standard</h3>
<table><thead><tr><th width="25%">Machine types</th><th>vCPUs<sup>1</sup></th>
<th>Memory (GB)</th><th>Local SSD</th></tr></thead><tbody>
<tr><td><code translate="no" dir="ltr">e2-standard-2</code></td><td>2</td><td>8</td><td>No</td></tr>
<tr><td><code>e2-standard-4</code></td><td>4</td><td>16</td><td>No</td></tr>
</tbody></table>
<table><thead><tr><th>Machine types</th><th>vCPUs</th><th>Fractional vCPUs<sup>1</sup></th>
<th>Memory (GB)</th></tr></thead><tbody>
<tr><td><code>e2-micro</code></td><td>2</td><td>0.25<sup>1</sup></td><td>1</td></tr>
<tr><td><code>e2-medium</code></td><td>2</td><td>1</td><td>4</td></tr>
</tbody></table>
<table><thead><tr><th>Machine types</th><th>vCPUs<sup>1</sup></th><th>Memory (GB)</th></tr>
</thead><tbody><tr><td><code>n2-standard-4</code></td><td>4</td><td>16</td></tr>
<tr><td><code>n2-highmem-2</code></td><td>2</td><td>16</td></tr></tbody></table>
<table><thead><tr><th>Machine types</th><th>Max number of disks</th></tr></thead>
<tbody><tr><td><code>n2-standard-4</code></td><td>128</td></tr></tbody></table>
""",
    "accelerator-optimized-machines": """
<table><tr><th></th><th colspan="6">Attached NVIDIA A100 40GB GPUs</th></tr>
<tr><th>Machine type</th><th>vCPU count<sup>1</sup></th><th>Instance memory (GB)</th>
<th>Attached Local SSD (GiB)</th><th>GPU count</th></tr>
<tr><td><code>a2-highgpu-1g</code></td><td>12</td><td>85</td><td>Yes</td><td>1</td></tr>
<tr><td><code>a2-highgpu-2g</code></td><td>24</td><td>170</td><td>Yes</td><td>2</td></tr>
</table>
""",
}


def _fake_catalog(requested: list[str]):
    """The Catalog API: services and SKUs, a page at a time, refusing a call with no key."""

    def fetch(url: str) -> bytes:
        requested.append(url)
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert parts.scheme == "https" and parts.netloc == "cloudbilling.googleapis.com"
        assert query["key"] == [KEY]
        page = int(query.get("pageToken", ["0"])[0])
        if parts.path == "/v1/services":
            body = {
                "services": [
                    {
                        "name": f"services/{sid}",
                        "serviceId": sid,
                        "displayName": name,
                        "businessEntityName": "businessEntities/GCP",
                    }
                    for sid, name in SERVICES[page]
                ]
            }
            pages = len(SERVICES)
        else:
            assert query["currencyCode"] == ["USD"]
            sid = parts.path.split("/")[3]
            body = {"skus": SKUS[sid][page]}
            pages = len(SKUS[sid])
        body["nextPageToken"] = str(page + 1) if page + 1 < pages else ""
        return json.dumps(body).encode()

    return fetch


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, list[str]]:
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv(builder.KEY_VARIABLE, KEY)
    requested: list[str] = []
    monkeypatch.setattr(builder, "fetch_url", _fake_catalog(requested))
    monkeypatch.setattr(
        builder,
        "download",
        lambda url, fresh=False: PAGES.get(url.rsplit("/", 1)[1], "<p>no tables</p>").encode(),
    )
    path = builder.build(folder=tmp_path / "prices", today=TODAY)
    return path, requested


# ------------------------------------------------------------------ the builder
def test_the_builder_refuses_without_a_key_and_says_how_to_get_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(builder.KEY_VARIABLE, raising=False)
    monkeypatch.setattr(builder, "fetch_url", lambda url: pytest.fail("no key, no request"))
    with pytest.raises(PricingError, match="Cloud Billing API enabled") as refused:
        builder.build(folder=tmp_path)
    assert builder.KEY_VARIABLE in str(refused.value)
    assert not (tmp_path / "gcp.json").exists()


def test_the_builder_pages_the_catalog_and_keeps_on_demand_rates(
    built: tuple[Path, list[str]],
) -> None:
    path, requested = built
    table = load_table("gcp", path.parent)
    assert table.read == TODAY and table.currency == "USD"
    compute = table.service("compute")
    # units + nanos; the Iowa SKU wins in us-central1, the Americas one elsewhere
    assert compute.rate("us-central1", "e2", "core") == 0.02181159
    assert compute.rate("us-central1", "n2", "core") == 0.031
    assert compute.rate("us-east1", "n2", "core") == 0.031611
    assert compute.rate("us-east1", "n2", "custom-core") == 0.033191
    assert compute.rate("europe-west1", "e2", "ram") == 0.00321311
    assert compute.published == "2026-10-01"
    # spot and committed rates are not list prices
    assert compute.choices("us-central1", "e2") == ["core", "ram"]
    assert table.service("gpu").rate("us-east1", "a100") == 2.933908
    assert table.service("windows").rate("global", "core") == 0.046
    assert table.service("disk").rate("us-central1", "pd-balanced") == 0.1
    sql = table.service("cloud_sql")
    assert sql.rate("us-central1", "postgres", "enterprise", "regional", "core") == 0.0826
    assert sql.rate("us-central1", "postgres", "enterprise", "zonal", "storage-ssd") == 0.17
    assert table.service("gke").rate("global", "cluster") == 0.1
    assert table.service("storage").rate("us", "standard") == 0.026
    # the free first tier is skipped: the rate is the first one with a price
    ops = table.service("storage_ops")
    assert ops.rate("global", "regional", "standard", "a") == 0.000005
    # every page of services and of each service's SKUs was read
    tokens = [parse_qs(urlsplit(url).query).get("pageToken", [""])[0] for url in requested]
    assert tokens.count("1") == 2 and len(requested) == 2 + 1 + 1 + 1 + 2


def test_the_builder_reads_machine_types_from_the_family_pages(
    built: tuple[Path, list[str]],
) -> None:
    table = load_table("gcp", built[0].parent)
    types = table.service("machine_types")
    assert types.rates["e2-standard-2"] == {"vcpus": 2, "memory_gb": 8}
    assert types.rates["n2-standard-4"] == {"vcpus": 4, "memory_gb": 16}
    # the fractional column, with its footnote marker left out
    assert types.rates["e2-micro"] == {"vcpus": 0.25, "memory_gb": 1}
    assert types.rates["a2-highgpu-2g"] == {"vcpus": 24, "memory_gb": 170, "gpus": 2}
    assert types.info["gpu"]["a2-highgpu-2g"] == "a100"
    assert types.describe("machine_type", "e2-standard-2") == "2 vCPU, 8 GB"


def test_the_key_stays_out_of_the_cache_and_the_errors(
    built: tuple[Path, list[str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache" / "price-build"
    files = list(cache.iterdir())
    assert files and not [f for f in files if KEY in f.name or KEY.encode() in f.read_bytes()]

    def refused(url: str) -> bytes:
        raise PricingError(f"{url} answered HTTP 403")

    monkeypatch.setattr(builder, "fetch_url", refused)
    with pytest.raises(PricingError) as error:
        builder.build(fresh=True, folder=tmp_path / "again", today=TODAY)
    assert KEY not in str(error.value) and "<key>" in str(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__


def test_units_convert_between_what_the_api_bills_and_what_the_table_holds() -> None:
    assert builder.convert(0.0001, "GiBy.h", "GiBy.mo") == pytest.approx(0.073)
    assert builder.convert(6.25, "TiBy", "GiBy") == pytest.approx(6.25 / 1024)
    assert builder.convert(0.05, "h", "mo") == pytest.approx(36.5)
    assert builder.convert(0.1, "h", "GiBy") is None


# ------------------------------------------------------------------ the pricers
RATES = {
    "compute": {
        "keys": ["region", "series", "resource"],
        "rates": {
            "us-central1": {
                "e2": {"core": 0.02181159, "ram": 0.00292333},
                "n2": {"core": 0.031611, "ram": 0.004237},
            }
        },
    },
    "machine_types": {
        "keys": ["machine_type", "field"],
        "rates": {
            "e2-standard-2": {"vcpus": 2, "memory_gb": 8},
            "e2-micro": {"vcpus": 0.25, "memory_gb": 1},
            "n2-standard-4": {"vcpus": 4, "memory_gb": 16},
        },
    },
    "disk": {"keys": ["region", "type"], "rates": {"us-central1": {"pd-balanced": 0.1}}},
    "cloud_sql": {
        "keys": ["region", "engine", "edition", "availability", "item"],
        "rates": {
            "us-central1": {
                "postgres": {
                    "enterprise": {
                        "zonal": {"core": 0.0413, "ram": 0.007, "storage-ssd": 0.17},
                        "regional": {"core": 0.0826, "ram": 0.014, "storage-ssd": 0.34},
                    }
                }
            }
        },
    },
    "gke": {"keys": ["region", "item"], "rates": {"global": {"cluster": 0.1}}},
    "storage": {"keys": ["region", "class"], "rates": {"us-central1": {"standard": 0.02}}},
    "storage_ops": {
        "keys": ["region", "scope", "class", "item"],
        "rates": {"global": {"regional": {"standard": {"a": 0.000005, "b": 0.0000004}}}},
    },
}


@pytest.fixture
def table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    services = {
        name: {"title": name, "source": "test", "unit": "x", **body} for name, body in RATES.items()
    }
    write_table("gcp", services, read=TODAY, folder=tmp_path)
    monkeypatch.setattr(tables_module, "tables_dir", lambda: tmp_path)
    load_table.cache_clear()
    yield load_table("gcp")
    load_table.cache_clear()


def _ask(table, service_id: str, sizing: dict | None = None, region: str | None = None) -> Ask:
    return Ask(
        element_id="e",
        name="Element",
        provider="gcp",
        service_id=service_id,
        sizing=sizing or {},
        framed_region=region,
        default_region="us-central1",
        table=table,
        today=TODAY,
    )


def _price(table, service_id: str, sizing: dict | None = None, region: str | None = None):
    return COVERAGE.pricers[service_id](_ask(table, service_id, sizing, region))


def test_a_machine_type_is_its_vcpus_at_the_core_rate_plus_its_memory_at_the_ram_rate(
    table,
) -> None:
    price = _price(table, "compute-engine", {"machine_type": "e2-standard-2", "disk_gb": 0})
    hourly = 2 * 0.02181159 + 8 * 0.00292333
    assert price.hourly == pytest.approx(hourly, abs=1e-6)
    assert price.monthly == round(hourly * HOURS, 2) == price.fixed
    assert price.sizing["vcpus"] == 2 and price.sizing["memory_gb"] == 8
    assert price.assumed == ["region", "count", "hours", "os"]
    (instance,) = price.lines
    assert instance.unit == "hours" and instance.quantity == HOURS and instance.kind == "fixed"


def test_a_shared_core_type_is_billed_its_share_of_a_vcpu(table) -> None:
    price = _price(table, "compute-engine", {"machine_type": "e2-micro", "count": 2})
    instance, disk = price.lines
    assert instance.rate == pytest.approx(0.25 * 0.02181159 + 1 * 0.00292333)
    assert instance.quantity == 2 * HOURS
    assert disk.quantity == 2 * 10 and disk.rate == 0.1 and disk.assumed


def test_a_custom_machine_is_priced_from_its_vcpus_and_memory(table) -> None:
    price = _price(table, "compute-engine", {"vcpus": 4, "memory_gb": 20, "disk_gb": 0})
    assert price.lines[0].rate == pytest.approx(4 * 0.031611 + 20 * 0.004237)
    assert price.sizing["machine_type"] == "n2-custom-4-20480" and "series" in price.assumed


def test_cloud_sql_high_availability_is_the_regional_rate(table) -> None:
    zonal = _price(table, "cloud-sql", {"tier": "db-custom-2-8192", "storage_gb": 10})
    ha = _price(table, "cloud-sql", {"tier": "db-custom-2-8192", "storage_gb": 10, "ha": True})
    assert zonal.lines[0].rate == pytest.approx(2 * 0.0413 + 8 * 0.007)
    assert ha.lines[0].rate == pytest.approx(2 * zonal.lines[0].rate)
    assert ha.lines[1].amount == round(10 * 0.34, 4) and ha.sizing["ha"] is True
    assert "engine" in zonal.assumed and "ha" not in ha.assumed


def test_gke_charges_the_cluster_fee_and_prices_its_nodes_as_vms(table) -> None:
    price = _price(
        table,
        "gke",
        {"machine_type": "e2-standard-2", "node_count": 2, "disk_gb": 0},
        "us-central1",
    )
    fee, nodes = price.lines
    assert fee.rate == 0.1 and fee.quantity == HOURS
    assert nodes.quantity == 2 * HOURS
    assert nodes.rate == pytest.approx(2 * 0.02181159 + 8 * 0.00292333)
    assert "region" not in price.assumed


def test_cloud_storage_prices_its_usage_defaults_and_marks_them_assumed(table) -> None:
    price = _price(table, "cloud-storage")
    stored, class_a, class_b = price.lines
    assert (stored.quantity, stored.unit, stored.amount) == (100, "GB-month", 2.0)
    assert (class_a.quantity, class_a.amount) == (1, 5.0)
    assert (class_b.quantity, class_b.amount) == (1, 0.4)
    assert all(item.kind == "usage" and item.assumed for item in price.lines)
    assert price.usage == price.monthly == 7.4 and price.fixed == 0
    assert {"storage_gb", "class_a_millions", "class_b_millions"} <= set(price.assumed)


@pytest.mark.parametrize(
    ("sizing", "region", "refusal"),
    [
        ({"machine_type": "e2-standard-3"}, None, "no machine_type 'e2-standard-3'; it has e2-"),
        ({}, "mars-north1", "no region 'mars-north1'"),
        ({"machine_type": "e2-standard-2", "instance_type": "t3.micro"}, None, "not instance_type"),
        ({"vcpus": 4}, None, "needs vcpus and memory_gb"),
    ],
)
def test_a_sizing_it_cannot_price_is_refused(table, sizing, region, refusal) -> None:
    with pytest.raises(PricingError, match=refusal):
        _price(table, "compute-engine", sizing, region)


def test_an_export_prices_a_compute_engine_vm_in_its_region_frame(table) -> None:
    with Diagram("Priced", "A VM in Iowa.", slug="priced-gcp", providers=("gcp",)) as diagram:
        with frames.Region("us-central1"):
            vm = gcp.ComputeEngine("Web server")
            gcp.VertexAI("Model")
        vm.sizing(machine_type="n2-standard-4", disk_gb=0)
    project = diagram.to_project()
    result = price_project(project, today=TODAY)
    ((element_id, price),) = result.priced
    assert element_id == "web-server" and price.sizing["region"] == "us-central1"
    assert price.monthly == round((4 * 0.031611 + 16 * 0.004237) * HOURS, 2)
    assert [why for _, _, why in result.unpriced] == ["gcp:vertex-ai"]


#: Every service the pricers read, with rates of the right size.
EVERY = {
    "compute": (
        ["region", "series", "resource"],
        {
            "us-central1": {
                "e2": {"core": 0.0218, "ram": 0.0029},
                "n2": {"core": 0.0316, "ram": 0.0042},
                "a2": {"core": 0.0317, "ram": 0.0042},
            }
        },
    ),
    "machine_types": (
        ["machine_type", "field"],
        {
            "e2-standard-2": {"vcpus": 2, "memory_gb": 8},
            "e2-medium": {"vcpus": 1, "memory_gb": 4},
            "n2-standard-4": {"vcpus": 4, "memory_gb": 16},
            "a2-highgpu-1g": {"vcpus": 12, "memory_gb": 85, "gpus": 1},
        },
    ),
    "gpu": (["region", "gpu"], {"us-central1": {"a100": 2.93, "t4": 0.35}}),
    "windows": (["region", "resource"], {"global": {"core": 0.046}}),
    "disk": (
        ["region", "type"],
        {"us-central1": {"pd-balanced": 0.1, "hyperdisk-balanced": 0.08, "local-ssd": 0.08}},
    ),
    "disk_performance": (
        ["region", "type", "what"],
        {"us-central1": {"hyperdisk-balanced": {"iops": 0.005, "throughput": 0.04}}},
    ),
    "ip": (["region", "state"], {"us-central1": {"in-use": 0.005, "reserved": 0.01}}),
    "cloud_sql": (
        ["region", "engine", "edition", "availability", "item"],
        {
            "us-central1": {
                "postgres": {
                    "enterprise": {"zonal": {"core": 0.04, "ram": 0.007, "storage-ssd": 0.17}}
                }
            }
        },
    ),
    "sql_license": (["region", "edition"], {"global": {"standard": 0.13}}),
    "alloydb": (
        ["region", "item"],
        {"us-central1": {"vcpu": 0.066, "memory": 0.011, "storage": 0.3}},
    ),
    "memorystore": (["region", "tier", "band"], {"us-central1": {"basic": {"m1": 0.049}}}),
    "spanner": (["region", "item"], {"us-central1": {"node": 0.9, "storage": 0.3}}),
    "bigtable": (["region", "item"], {"us-central1": {"node": 0.65, "ssd": 0.17, "hdd": 0.026}}),
    "firestore": (
        ["region", "item"],
        {"us-central1": {"reads": 3e-7, "writes": 9e-7, "storage": 0.15}},
    ),
    "gke": (
        ["region", "item"],
        {
            "global": {"cluster": 0.1},
            "us-central1": {"autopilot-vcpu": 0.0445, "autopilot-memory": 0.0049},
        },
    ),
    "cloud_run": (
        ["region", "item"],
        {"us-central1": {"cpu": 0.000024, "memory": 0.0000025, "requests": 4e-7}},
    ),
    "app_engine": (["region", "item"], {"us-central1": {"frontend": 0.05, "backend": 0.05}}),
    "storage": (["region", "class"], {"us-central1": {"standard": 0.02}}),
    "storage_ops": (
        ["region", "scope", "class", "item"],
        {"global": {"regional": {"standard": {"a": 5e-6, "b": 4e-7}}}},
    ),
    "filestore": (["region", "tier"], {"us-central1": {"basic-hdd": 0.16}}),
    "dataflow": (
        ["region", "item"],
        {"us-central1": {"batch-vcpu": 0.056, "batch-memory": 0.0035, "pd": 0.000054}},
    ),
    "dataproc": (["region", "item"], {"global": {"vcpu": 0.01}}),
    "composer": (
        ["region", "item"],
        {"us-central1": {"env-small": 0.35, "dcu": 0.06, "storage": 0.27}},
    ),
    "load_balancing": (
        ["region", "item"],
        {"us-central1": {"rule-minimum": 0.025, "rule-additional": 0.01, "data": 0.008}},
    ),
    "cdn": (
        ["region", "destination", "item"],
        {"global": {"north-america": {"egress": 0.08}, "all": {"lookups": 7.5e-7}}},
    ),
    "nat": (["region", "item"], {"us-central1": {"gateway": 0.0014, "data": 0.045}}),
    "vpn": (["region", "item"], {"us-central1": {"tunnel": 0.05}}),
    "interconnect": (
        ["region", "kind", "capacity"],
        {"global": {"dedicated": {"10g": 2.328, "vlan": 0.1}, "partner": {"1g": 0.0972}}},
    ),
    "armor": (["region", "item"], {"global": {"policy": 5, "rule": 1, "requests": 7.5e-7}}),
    "dns": (["region", "item"], {"global": {"zone": 0.2, "queries": 4e-7}}),
    "secrets": (["region", "item"], {"global": {"versions": 0.06, "access": 3e-6}}),
    "logging": (["region", "item"], {"global": {"ingestion": 0.5}}),
    "monitoring": (["region", "item"], {"global": {"ingestion": 0.258}}),
    "artifact_registry": (["region", "item"], {"us-central1": {"storage": 0.1}}),
    "scheduler": (["region", "item"], {"global": {"job": 0.1}}),
    "tasks": (["region", "item"], {"us-central1": {"operations": 4e-7}}),
    "kms": (["region", "item"], {"us-central1": {"key-version": 0.06, "operations": 3e-6}}),
    "cloud_build": (["region", "item"], {"us-central1": {"build-minute": 0.006}}),
    "workflows": (["region", "item"], {"us-central1": {"internal-step": 1e-5}}),
    "eventarc": (["region", "item"], {"global": {"events": 4e-7}}),
    "api_gateway": (["region", "item"], {"global": {"calls": 3e-6}}),
    # a multi-region rate prices the regions in it
    "bigquery": (["region", "item"], {"us": {"analysis": 6.25, "active-storage": 0.02}}),
    "pubsub": (["region", "item"], {"global": {"throughput": 40}}),
}


@pytest.mark.parametrize("service_id", sorted(COVERAGE.pricers))
def test_every_pricer_prices_its_defaults_from_a_full_table(
    tmp_path: Path, service_id: str
) -> None:
    services = {
        name: {"title": name, "source": "test", "unit": "x", "keys": keys, "rates": rates}
        for name, (keys, rates) in EVERY.items()
    }
    services["machine_types"]["info"] = {"gpu": {"a2-highgpu-1g": "a100"}}
    write_table("gcp", services, read=TODAY, folder=tmp_path)
    full = load_table("gcp", tmp_path)
    price = _price(full, service_id, region="us-central1")
    assert price.monthly > 0 and price.lines and all(item.amount >= 0 for item in price.lines)
    assert price.monthly == round(price.fixed + price.usage, 2)
    assert "region" not in price.assumed and price.assumed
    load_table.cache_clear()


def test_a_gpu_machine_adds_its_gpus_and_windows_its_licence(tmp_path: Path) -> None:
    services = {
        name: {"title": name, "source": "test", "unit": "x", "keys": keys, "rates": rates}
        for name, (keys, rates) in EVERY.items()
    }
    services["machine_types"]["info"] = {"gpu": {"a2-highgpu-1g": "a100"}}
    write_table("gcp", services, read=TODAY, folder=tmp_path)
    full = load_table("gcp", tmp_path)
    price = _price(
        full, "compute-engine", {"machine_type": "a2-highgpu-1g", "os": "windows", "disk_gb": 0}
    )
    instance, gpus, licence = price.lines
    assert instance.rate == pytest.approx(12 * 0.0317 + 85 * 0.0042)
    assert gpus.rate == 2.93 and licence.rate == pytest.approx(12 * 0.046)
    load_table.cache_clear()
