"""AWS prices: the table built from AWS's price list, and the pricers that read it.

Held here, with no network:

- the builder keeps the standard commercial regions only, removes a usage
  type's region prefix, and leaves the account's free tier out of a rate;
- EC2, EBS, NAT gateways, load balancers, RDS and Aurora (provisioned and
  Serverless v2), ElastiCache Serverless, VPC IPAM and Route Server, S3,
  Lambda, DynamoDB, Route 53 and CloudFront are priced from a small table: the
  arithmetic, tiers, fixed resources against usage, and every default
  marked assumed;
- an unknown size, a region the table does not hold and a sizing key no
  pricer reads are refused, never priced as a default;
- a database instance class goes by AWS's own name (``db.r6g.2xlarge``),
  in the table and in what an element says; the short form AWS's usage
  types write (``db.r6g.2xl``) is read as it;
- a drawing is priced from the table: the region from its frames, a free
  component said free, one not priced said why;
- the shipped table prices a t3.micro at AWS's published rate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.nodes.aws import compute, databases, networking_content_delivery as net
from infragram.nodes.frames import aws as frames
from infragram.pricing import PricingError, price_project, tables as tables_module
from infragram.pricing.ask import HOURS, Ask
from infragram.pricing.aws import COVERAGE
from infragram.pricing.build import aws as builder, write_table
from infragram.pricing.tables import load_table

TODAY = "2026-10-08"


def _metered(rates: dict) -> dict:
    return {"keys": ["region", "item", "from"], "rates": rates}


#: A few of AWS's real us-east-1 rates (and one eu-west-1), as the builder files them.
SERVICES = {
    "ec2": {
        "keys": ["region", "os", "instance_type"],
        "rates": {
            "us-east-1": {
                "Linux": {"t3.micro": 0.0104, "m6i.large": 0.096},
                "Windows": {"t3.micro": 0.0196},
            },
            "eu-west-1": {"Linux": {"t3.micro": 0.0114}},
        },
        "info": {"instance_type": {"t3.micro": "2 vCPU, 1 GiB"}},
    },
    "ebs": _metered(
        {
            "us-east-1": {
                "gp3": {"0": 0.08},
                "gp3-iops": {"0": 0.005},
                "gp3-throughput": {"0": 40.96},
                "io2": {"0": 0.125},
                "io2-iops": {"0": 0.065, "32000": 0.0455, "64000": 0.03185},
                "snapshot": {"0": 0.05},
            }
        }
    ),
    "nat-gateway": _metered({"us-east-1": {"hour": {"0": 0.045}, "gb": {"0": 0.045}}}),
    "vpc": _metered(
        {
            "us-east-1": {
                "public-ipv4": {"0": 0.005},
                "ipam-ip-hour": {"0": 0.00027},
                "route-server-endpoint-hour": {"0": 0.75},
            }
        }
    ),
    "elb": _metered(
        {
            "us-east-1": {
                "alb-hour": {"0": 0.0225},
                "alb-lcu": {"0": 0.008},
                "clb-hour": {"0": 0.025},
                "clb-gb": {"0": 0.008},
            }
        }
    ),
    "data-transfer": _metered(
        {"us-east-1": {"internet-out": {"0": 0.09, "10240": 0.085, "51200": 0.07}}}
    ),
    "s3": _metered(
        {
            "us-east-1": {
                "storage-standard": {"0": 0.023, "51200": 0.022, "512000": 0.021},
                "read-standard": {"0": 4e-07},
                "write-standard": {"0": 5e-06},
            }
        }
    ),
    "lambda": _metered(
        {
            "us-east-1": {
                "requests": {"0": 2e-07},
                "gb-second": {"0": 1.66667e-05},
                "requests-arm": {"0": 2e-07},
                "gb-second-arm": {"0": 1.33334e-05},
            }
        }
    ),
    "recovery-controller": _metered(
        {
            "global": {
                "cluster-hour": {"0": 2.5},
                "readiness-check-hour": {"0": 0.045},
                "region-switch-plan": {"0": 70.0},
            }
        }
    ),
    "rds": {
        "keys": ["region", "engine", "deployment", "instance_class"],
        "rates": {
            "us-east-1": {
                "PostgreSQL": {
                    "Single-AZ": {"db.t3.micro": 0.018},
                    "Multi-AZ": {"db.t3.micro": 0.036},
                },
                "Aurora PostgreSQL": {
                    "Single-AZ": {"db.t3.medium": 0.082, "db.r6g.2xlarge": 1.038}
                },
            }
        },
    },
    "rds-usage": _metered(
        {
            "us-east-1": {
                "Single-AZ gp3": {"0": 0.115},
                "Multi-AZ gp3": {"0": 0.23},
                "Single-AZ gp2": {"0": 0.115},
                "aurora storage": {"0": 0.1},
                "aurora io-request": {"0": 2e-07},
                "aurora-serverless acu-hour": {"0": 0.12},
                "aurora-serverless-io-optimized acu-hour": {"0": 0.16},
                "aurora-io-optimized storage": {"0": 0.225},
            }
        }
    ),
    "elasticache-usage": _metered(
        {
            "us-east-1": {
                "valkey serverless-gb-hour": {"0": 0.084},
                "valkey serverless-ecpu": {"0": 2.3e-09},
                "redis serverless-gb-hour": {"0": 0.125},
                "redis serverless-ecpu": {"0": 3.4e-09},
            }
        }
    ),
    "dynamodb": _metered(
        {
            "us-east-1": {
                "read-request": {"0": 1.25e-07},
                "write-request": {"0": 6.25e-07},
                "storage": {"0": 0.25},
            }
        }
    ),
    "route53": _metered(
        {
            "global": {
                "hosted-zone": {"0": 0.5, "25": 0.1},
                "query-standard": {"0": 4e-07, "1000000000": 2e-07},
            }
        }
    ),
    "cloudfront": {
        "keys": ["area", "item", "from"],
        "rates": {
            "United States": {
                "data-out": {"0": 0.085, "10240": 0.08},
                "https-request": {"0": 1e-06},
            }
        },
    },
}


@pytest.fixture
def table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    services = {
        name: {
            "title": name.upper(),
            "source": "test",
            "published": "2026-10-01",
            "unit": "x",
            **body,
        }
        for name, body in SERVICES.items()
    }
    write_table("aws", services, read=TODAY, folder=tmp_path)
    monkeypatch.setattr(tables_module, "tables_dir", lambda: tmp_path)
    load_table.cache_clear()
    yield load_table("aws")
    load_table.cache_clear()


def _ask(table, service_id: str, sizing: dict | None = None, region: str | None = None) -> Ask:
    return Ask(
        element_id="e",
        name="Element",
        provider="aws",
        service_id=service_id,
        sizing=sizing or {},
        framed_region=region,
        default_region=COVERAGE.default_region,
        table=table,
        today=TODAY,
    )


def _price(table, service_id: str, sizing: dict | None = None, region: str | None = None):
    return COVERAGE.pricers[service_id](_ask(table, service_id, sizing, region))


def _lines(price) -> dict[str, tuple[float, float, str, bool]]:
    return {item.label: (item.quantity, item.rate, item.kind, item.assumed) for item in price.lines}


# ------------------------------------------------------------------ the builder
def test_only_the_standard_commercial_regions_are_kept() -> None:
    names = {
        code: [code]
        for code in (
            "us-east-1",
            "eu-west-1",
            "ap-southeast-7",
            "us-gov-west-1",
            "cn-north-1",
            "eusc-de-east-1",
            "us-east-2-mci-1",
            "us-east-1-bos-1",
        )
    }
    assert builder.regions(names) == ["ap-southeast-7", "eu-west-1", "us-east-1"]


def test_a_usage_types_region_prefix_is_removed_and_only_it() -> None:
    prefixes = ("eu-west-2", "EUW2")
    assert builder._unprefixed("EUW2-NatGateway-Hours", prefixes) == "NatGateway-Hours"
    assert builder._unprefixed("eu-west-2-KMS-Keys", prefixes) == "KMS-Keys"
    # another region's prefix, or a word that looks like one, is kept
    assert builder._unprefixed("TS-LoadBalancerUsage", prefixes) == "TS-LoadBalancerUsage"
    assert builder._unprefixed("Global-Request", prefixes) == "Global-Request"


def test_the_free_tier_is_left_out_of_a_rate() -> None:
    def dimension(begin: str, price: str) -> dict:
        return {"beginRange": begin, "pricePerUnit": {"USD": price}}

    # SNS: the first million requests free, then $0.50 a million
    assert builder._tiers([dimension("1000000", "0.0000005"), dimension("0", "0")]) == [
        (0.0, 5e-07)
    ]
    # S3 Standard: three paid tiers, kept in order
    assert builder._tiers(
        [dimension("51200", "0.022"), dimension("0", "0.023"), dimension("512000", "0.021")]
    ) == [(0.0, 0.023), (51200.0, 0.022), (512000.0, 0.021)]
    # a rate of nothing with nothing after it is a real rate of nothing
    assert builder._tiers([dimension("0", "0")]) == [(0.0, 0.0)]
    assert builder._tiers([{"beginRange": "0", "pricePerUnit": {"CNY": "1"}}]) is None


# ------------------------------------------------------------------ compute
def test_ec2_is_priced_by_type_os_count_and_hours(table) -> None:
    price = _price(table, "ec2", {"instance_type": "t3.micro", "count": 2})
    assert price.monthly == round(0.0104 * HOURS * 2, 2)
    assert price.hourly == pytest.approx(0.0104 * 2)
    assert price.fixed == price.monthly and price.usage == 0
    assert set(price.assumed) == {"os", "region", "hours"}
    assert price.sizing == {
        "region": "us-east-1",
        "os": "Linux",
        "instance_type": "t3.micro",
        "count": 2,
        "hours": HOURS,
    }
    assert "2 vCPU, 1 GiB" in price.rate and price.priced == TODAY
    windows = _price(
        table, "ec2-instance", {"instance_type": "t3.micro", "os": "windows", "hours": 100}
    )
    assert windows.monthly == round(0.0196 * 100, 2) and windows.sizing["os"] == "Windows"


def test_ec2_takes_its_region_from_the_frames_and_a_root_volume_when_given(table) -> None:
    price = _price(table, "ec2", {"instance_type": "t3.micro"}, region="eu-west-1")
    assert price.sizing["region"] == "eu-west-1" and "region" not in price.assumed
    assert price.monthly == round(0.0114 * HOURS, 2)
    with pytest.raises(PricingError, match="EBS has no region 'eu-west-1'"):
        # the small table holds no EBS rate in eu-west-1: refused, not guessed
        _price(table, "ec2", {"instance_type": "t3.micro", "volume_gb": 30, "region": "eu-west-1"})
    us = _price(table, "ec2", {"instance_type": "t3.micro", "volume_gb": 30})
    assert _lines(us)["Root volume (gp3)"] == (30, 0.08, "fixed", False)


@pytest.mark.parametrize(
    ("sizing", "says"),
    [
        ({"instance_type": "t3.mikro"}, "has no instance_type 't3.mikro'; it has t3.micro"),
        (
            {"instance_type": "t3.micro", "region": "mars-north-1"},
            "no prices for region 'mars-north-1'",
        ),
        ({"instance_type": "t3.micro", "instance_typ": "m6i.large"}, "not instance_typ"),
        ({"instance_type": "t3.micro", "os": "BeOS"}, "os 'BeOS' is not one of Linux"),
        ({"instance_type": "t3.micro", "count": 0}, "count must be 1"),
        ({"instance_type": "t3.micro", "hours": 800}, "hours must be 1"),
    ],
)
def test_what_ec2_cannot_price_is_refused(table, sizing: dict, says: str) -> None:
    with pytest.raises(PricingError, match=says.replace("(", r"\(").replace(")", r"\)")):
        _price(table, "ec2", sizing)


def test_lambda_prices_requests_and_gb_seconds_with_its_defaults(table) -> None:
    price = _price(table, "lambda")
    lines = _lines(price)
    assert lines["Requests"] == (1, pytest.approx(0.2), "usage", True)
    # 1 M requests x 200 ms x 128 MB = 25,000 GB-seconds
    assert lines["Duration"][0] == pytest.approx(25000)
    assert price.monthly == round(0.2 + 25000 * 1.66667e-05, 2)
    assert price.fixed == 0 and price.usage == price.monthly
    assert {"requests_millions", "memory_mb", "duration_ms", "arch"} <= set(price.assumed)
    arm = _price(
        table,
        "lambda",
        {"arch": "arm", "requests_millions": 10, "memory_mb": 1024, "duration_ms": 100},
    )
    assert _lines(arm)["Duration"][:2] == (pytest.approx(1e6), 1.33334e-05)


# ------------------------------------------------------------------ storage and networking
def test_ebs_prices_gp3_extras_over_what_is_included_and_io2_iops_in_tiers(table) -> None:
    gp3 = _price(
        table, "elastic-block-store", {"size_gb": 100, "iops": 4000, "throughput_mbps": 250}
    )
    lines = _lines(gp3)
    assert lines["gp3 storage"] == (100, 0.08, "fixed", True)  # one volume, assumed
    assert lines["gp3 IOPS over the included 3,000"][:2] == (1000, 0.005)
    # 125 MiB/s over the included 125, at $40.96 per GiB/s-month
    assert lines["gp3 throughput over the included 125 MiB/s"][0] * lines[
        "gp3 throughput over the included 125 MiB/s"
    ][1] == pytest.approx(125 * 40.96 / 1024)
    io2 = _price(
        table, "elastic-block-store", {"volume_type": "io2", "size_gb": 100, "iops": 40000}
    )
    assert io2.monthly == round(100 * 0.125 + 32000 * 0.065 + 8000 * 0.0455, 2)
    assert io2.fixed == io2.monthly


def test_s3_storage_is_tiered_and_usage_is_marked_assumed(table) -> None:
    price = _price(table, "simple-storage-service", {"storage_gb": 60000})
    lines = _lines(price)
    assert lines["Standard storage (first 51,200 GB-month)"][:2] == (51200, 0.023)
    assert lines["Standard storage (51,200 to 512,000 GB-month)"][:2] == (8800, 0.022)
    assert lines["GET and other requests"] == (1, pytest.approx(0.4), "usage", True)
    assert lines["Data transfer out to the internet"] == (10, 0.09, "usage", True)
    assert price.fixed == 0
    assert price.monthly == round(51200 * 0.023 + 8800 * 0.022 + 0.4 + 0.9, 2)
    assert "storage_gb" not in price.assumed and "data_out_gb" in price.assumed


def test_a_nat_gateway_is_fixed_hours_and_usage_gb(table) -> None:
    price = _price(table, "vpc-nat-gateway", {"gateways": 2, "data_gb": 1000})
    assert price.fixed == round(2 * HOURS * 0.045, 2) and price.usage == 45.0
    assert price.hourly == pytest.approx(0.09)
    assert "hours" in price.assumed and "gateways" not in price.assumed


def test_load_balancers_by_type(table) -> None:
    alb = _price(table, "elastic-load-balancing-application-load-balancer")
    assert alb.monthly == round(HOURS * 0.0225 + HOURS * 0.008, 2)
    assert alb.fixed == round(HOURS * 0.0225, 2) and "capacity_units" in alb.assumed
    classic = _price(table, "elastic-load-balancing", {"type": "classic", "data_gb": 50})
    assert classic.monthly == round(HOURS * 0.025 + 50 * 0.008, 2)
    with pytest.raises(PricingError, match="not capacity_unit"):
        _price(table, "elastic-load-balancing", {"capacity_unit": 2})


def test_an_elastic_ip_is_a_public_ipv4_address_by_the_hour(table) -> None:
    price = _price(table, "ec2-elastic-ip-address", {"addresses": 3, "hours": 100})
    assert price.monthly == round(3 * 100 * 0.005, 2)


# ------------------------------------------------------------------ databases
def test_rds_prices_the_instance_and_its_storage(table) -> None:
    price = _price(table, "rds")
    lines = _lines(price)
    assert lines["PostgreSQL Single-AZ instance hours, db.t3.micro"][:2] == (HOURS, 0.018)
    assert lines["gp3 storage"] == (20, 0.115, "fixed", True)
    assert price.monthly == round(HOURS * 0.018 + 20 * 0.115, 2)
    assert {"engine", "deployment", "instance_class", "storage_gb"} <= set(price.assumed)
    multi = _price(table, "rds-multi-az", {"instance_class": "db.t3.micro", "storage_gb": 100})
    assert multi.sizing["deployment"] == "Multi-AZ"
    assert multi.monthly == round(HOURS * 0.036 + 100 * 0.23, 2)


def test_aurora_prices_its_storage_and_io_when_given(table) -> None:
    price = _price(table, "aurora", {"storage_gb": 50, "io_requests_millions": 10})
    lines = _lines(price)
    assert lines["Aurora PostgreSQL Single-AZ instance hours, db.t3.medium"][1] == 0.082
    assert lines["Aurora storage"][:2] == (50, 0.1)
    assert lines["I/O requests"][:2] == (10, pytest.approx(0.2))


@pytest.mark.parametrize("given", ["db.r6g.2xlarge", "db.r6g.2xl"])
def test_a_database_class_is_priced_by_awss_name_or_its_usage_type_short_form(
    table, given: str
) -> None:
    price = _price(table, "aurora", {"instance_class": given})
    lines = _lines(price)
    assert lines["Aurora PostgreSQL Single-AZ instance hours, db.r6g.2xlarge"][1] == 1.038
    assert price.sizing["instance_class"] == "db.r6g.2xlarge"


def test_the_builder_files_a_database_class_by_its_instance_type() -> None:
    def product(usage: str, **attributes: str) -> builder.Product:
        return builder.Product.model_construct(
            family="Database Instance", usage=usage, attributes=attributes, unit="Hrs", tiers=[]
        )

    aurora = product(
        "InstanceUsage:db.r6g.2xl",
        databaseEngine="Aurora PostgreSQL",
        licenseModel="No license required",
        instanceType="db.r6g.2xlarge",
    )
    assert builder._rds_key(aurora) == ("Aurora PostgreSQL", "Single-AZ", "db.r6g.2xlarge")
    documents = builder._storage_mode("InstanceUsage", "InstanceUsageIOOptimized")
    assert documents(product("InstanceUsage:db.r5.12xl", instanceType="db.r5.12xlarge")) == (
        "Standard",
        "db.r5.12xlarge",
    )
    # an offer without the attribute keeps the usage type's name
    assert documents(product("InstanceUsageIOOptimized:db.r6g.large")) == (
        "I/O-Optimized",
        "db.r6g.large",
    )


def test_application_recovery_controller_is_priced_by_its_feature(table) -> None:
    cluster = _price(table, "application-recovery-controller")
    assert cluster.monthly == round(2.5 * HOURS, 2)
    assert cluster.sizing["feature"] == "routing controls"
    plan = _price(table, "application-recovery-controller", {"feature": "region switch"})
    # USD 70 a plan a month, not a routing control cluster's 1,825
    assert plan.monthly == 70.0 and plan.sizing["feature"] == "region switch"
    two = _price(table, "application-recovery-controller", {"feature": "region switch", "plans": 2})
    assert two.monthly == 140.0
    with pytest.raises(PricingError, match="region switch"):
        _price(table, "application-recovery-controller", {"feature": "zonal autopilot"})


def test_aurora_serverless_prices_acu_hours_and_storage_when_the_sizing_says_so(table) -> None:
    price = _price(table, "aurora", {"serverless": "yes", "acus": 2, "storage_gb": 50})
    lines = _lines(price)
    # the hours are assumed, so the line is too
    assert lines["Aurora capacity unit hours"] == (2 * HOURS, 0.12, "fixed", True)
    assert lines["Aurora storage"][:2] == (50, 0.1)
    assert price.monthly == round(2 * HOURS * 0.12 + 50 * 0.1, 2)
    io = _price(table, "aurora-mysql-instance", {"serverless": True, "storage": "io-optimized"})
    assert io.monthly == round(0.5 * HOURS * 0.16 + 20 * 0.225, 2)
    assert {"acus", "storage_gb", "hours"} <= set(io.assumed)
    # not said, or said no: provisioned, and serverless is never an assumption
    for sizing in ({}, {"serverless": "no"}):
        provisioned = _price(table, "aurora", sizing)
        assert "Aurora PostgreSQL Single-AZ instance hours, db.t3.medium" in _lines(provisioned)
        assert "serverless" not in provisioned.assumed
    with pytest.raises(PricingError, match="serverless 'maybe' is not yes or no"):
        _price(table, "aurora", {"serverless": "maybe"})


def test_elasticache_serverless_prices_data_stored_and_ecpus(table) -> None:
    price = _price(
        table,
        "elasticache-elasticache-for-redis",
        {"serverless": "yes", "data_gb": 2, "ecpus_millions": 10},
    )
    assert _lines(price)["Data stored"][:2] == (2 * HOURS, 0.125)
    assert price.rate == "ElastiCache Serverless for Redis"
    assert price.monthly == round(2 * HOURS * 0.125 + 10e6 * 3.4e-09, 2)
    valkey = _price(table, "elasticache", {"serverless": "yes"})
    assert valkey.sizing["engine"] == "Valkey" and "engine" in valkey.assumed
    assert valkey.monthly == round(1 * HOURS * 0.084 + 100e6 * 2.3e-09, 2)


@pytest.mark.parametrize(
    ("sizing", "says"),
    [
        ({"engine": "Postgres"}, "engine 'Postgres' is not one of"),
        ({"instance_class": "db.t3.mikro"}, "has no instance_class 'db.t3.mikro'"),
        (
            {"deployment": "Multi-AZ", "instance_class": "db.t3.micro", "storage_type": "io9"},
            "storage_type",
        ),
    ],
)
def test_what_rds_cannot_price_is_refused(table, sizing: dict, says: str) -> None:
    with pytest.raises(PricingError, match=says):
        _price(table, "rds", sizing)


def test_dynamodb_on_demand_with_its_defaults(table) -> None:
    price = _price(table, "dynamodb")
    assert price.monthly == round(0.125 + 0.625 + 10 * 0.25, 2)
    assert price.fixed == 0 and {"reads_millions", "writes_millions", "storage_gb"} <= set(
        price.assumed
    )


# ------------------------------------------------------------------ one rule for counts and hours
@pytest.mark.parametrize(
    ("sizing", "says"),
    [
        ({"count": 2.5}, "count must be a whole number, not 2.5"),
        ({"count": 100_001}, "count must be 1 to 100000"),
        ({"count": "3"}, "count '3' is not the right kind of value"),
        ({"hours": 0}, "hours must be 1 to 744"),
        ({"hours": 745}, "hours must be 1 to 744"),
    ],
)
def test_a_count_or_hours_out_of_the_one_rule_is_refused(table, sizing: dict, says: str) -> None:
    ask = _ask(table, "ec2-table", sizing)
    with pytest.raises(PricingError, match=says):
        ask.count() if "count" in sizing else ask.hours()


def test_a_whole_float_count_is_a_count_and_hours_default_to_the_month(table) -> None:
    ask = _ask(table, "ec2-table", {"count": 3.0})
    assert ask.count() == 3 and ask.hours() == HOURS
    assert ask.was_assumed("hours") and not ask.was_assumed("count")


# ------------------------------------------------------------------ priced once for the world
def test_route53_and_cloudfront_are_priced_once_for_the_world(table) -> None:
    zones = _price(
        table, "route-53", {"hosted_zones": 30, "queries_millions": 2}, region="eu-west-1"
    )
    assert zones.monthly == round(25 * 0.5 + 5 * 0.1 + 2 * 0.4, 2)
    assert "region" not in zones.sizing and "region" not in zones.assumed
    cdn = _price(table, "cloudfront", {"data_out_gb": 20000})
    lines = _lines(cdn)
    assert lines["Data transfer out to the internet (first 10,240 GB)"][:2] == (10240, 0.085)
    assert lines["Data transfer out to the internet (over 10,240 GB)"][:2] == (9760, 0.08)
    with pytest.raises(PricingError, match="area 'Mars' is not one of United States"):
        _price(table, "cloudfront", {"area": "Mars"})


# ------------------------------------------------------------------ a drawing
def test_a_drawing_is_priced_from_the_table(table) -> None:
    with Diagram(
        "Priced", "Web servers and a database.", slug="priced", providers=("aws",)
    ) as diagram:
        with frames.Cloud("AWS Cloud"), frames.Region("us-east-1"), frames.VPC("VPC 10.0.0.0/16"):
            web = compute.EC2("Web servers")
            databases.RDS("PostgreSQL")
            net.ElasticLoadBalancing("Load balancer") >> web
        web.sizing(instance_type="m6i.large", count=2)
    project = diagram.to_project()
    result = price_project(project, today=TODAY)
    assert not result.notes, result.notes
    prices = {
        element.name: element.attributes.get("price")
        for element, _ in _walk(project.topology)
        if element.component is not None
    }
    assert prices["Web servers"]["monthly"] == round(0.096 * HOURS * 2, 2)
    assert prices["Web servers"]["sizing"]["region"] == "us-east-1"
    assert prices["Load balancer"]["source"].startswith("test")
    assert result.monthly == round(sum(price["monthly"] for price in prices.values() if price), 2)


def _walk(element, ancestors=()):
    yield element, ancestors
    for child in element.children:
        yield from _walk(child, (*ancestors, element))


def test_every_pricer_refuses_a_sizing_key_it_does_not_read(table) -> None:
    """A typo is never priced silently as a default, whatever the service."""
    refused = 0
    for service_id, pricer in COVERAGE.pricers.items():
        try:
            pricer(_ask(table, service_id, {"zzz_not_a_key": 1}))
        except PricingError as error:
            # the small table may hold no rates for the service: that is a refusal too
            assert "zzz_not_a_key" in str(error) or any(
                word in str(error) for word in ("holds no", "has no", "offers no")
            ), (
                service_id,
                error,
            )
            refused += 1
    assert refused == len(COVERAGE.pricers)


# ------------------------------------------------------------------ the shipped table
def test_the_shipped_table_prices_a_t3_micro_at_awss_rate() -> None:
    load_table.cache_clear()
    shipped = load_table("aws")
    price = _price(
        shipped, "ec2", {"instance_type": "t3.micro", "os": "Linux", "region": "us-east-1"}
    )
    # AWS's published on-demand rate for t3.micro Linux in N. Virginia
    assert price.hourly == 0.0104
    assert price.monthly == round(0.0104 * HOURS, 2)
    assert shipped.read[:2] == "20" and price.published[:2] == "20"
    load_table.cache_clear()


def test_the_shipped_table_names_database_classes_as_aws_does() -> None:
    load_table.cache_clear()
    shipped = load_table("aws")
    short = []
    for name in ("rds", "docdb", "neptune"):
        for region in shipped.service(name).rates.values():
            for deployments in region.values():
                for classes in deployments.values() if name == "rds" else [deployments]:
                    # a metal size keeps its short name: db.m8i.metal-48xl is AWS's own
                    short += [c for c in classes if c.endswith("xl") and ".metal-" not in c]
    assert not short, short[:5]
    aurora = shipped.service("rds").choices("us-east-1", "Aurora PostgreSQL", "Single-AZ")
    assert {"db.r6g.xlarge", "db.r6g.2xlarge"} <= set(aurora)
    load_table.cache_clear()
