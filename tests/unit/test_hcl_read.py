"""Reading HCL: the structure of a configuration, what is literal in it, and what it names.

- blocks, labels, attributes and nested blocks, one-line blocks, the three
  comment kinds, heredocs and templates with nested interpolations parse, and
  a file the reader cannot follow names its line;
- a value is read where it is literal: variables and locals from the scope,
  templates, conditionals, ``for`` expressions over lists and maps (with
  ``if`` and ``...``), the common functions (Terraform's ``/regex/`` replace,
  ``regexall``, ``cidrsubnets`` among them), and anything else is UNKNOWN
  rather than an error;
- a reference is found only where it is code, with the index it was written
  with and the key of the module instance it names, and ``var.``/``local.``/
  ``each.`` are the symbols an input stands for; ``element(list, i)`` is
  found with its list and index as written.
"""

from __future__ import annotations

import pytest

from infragram.terraform.hclread import (
    UNKNOWN,
    HclError,
    convert,
    element_calls,
    evaluate,
    parse,
    parse_json,
    references,
    symbols,
    type_of,
)

SAMPLE = r"""
# a comment
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

/* a block
   comment */
resource "aws_subnet" "private" {
  count             = 2 // how many
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr, 8, count.index + 10)
  availability_zone = "${var.region}${["a", "b"][count.index]}"
  tags              = merge(local.tags, { Name = "private-${count.index}" })
  policy            = <<-EOT
    {"Statement": "${aws_iam_role.x.arn}"}
  EOT
  lifecycle { ignore_changes = [tags] }
}
"""


def test_blocks_attributes_and_nested_blocks_parse_with_their_lines():
    body = parse(SAMPLE, "main.tf")
    assert [(b.type, b.labels, b.line) for b in body.blocks] == [
        ("terraform", (), 3),
        ("resource", ("aws_subnet", "private"), 11),
    ]
    subnet = body.blocks[1].body
    assert sorted(subnet.attributes) == [
        "availability_zone",
        "cidr_block",
        "count",
        "policy",
        "tags",
        "vpc_id",
    ]
    assert [b.type for b in subnet.blocks] == ["lifecycle"]
    assert subnet.attributes["count"].text == "2"
    assert subnet.attributes["policy"].text.startswith("<<-EOT")


def test_a_file_the_reader_cannot_follow_names_its_line():
    with pytest.raises(HclError, match=r"main\.tf:3"):
        parse('a = 1\nb = "two"\nc = "never closed\n', "main.tf")
    with pytest.raises(HclError, match="never closed"):
        parse('resource "x" "y" {\n  a = 1\n', "main.tf")


def test_values_are_read_where_they_are_literal():
    scope = {
        "var": {"cidr": "10.0.0.0/16", "region": "us-east-1", "project": "shop"},
        "local": {"tags": {"Team": "web"}},
        "count": {"index": 1},
    }
    subnet = parse(SAMPLE).blocks[1].body.attributes
    assert evaluate(subnet["cidr_block"], scope) == "10.0.11.0/24"
    assert evaluate(subnet["availability_zone"], scope) == "us-east-1b"
    assert evaluate(subnet["tags"], scope) == {"Team": "web", "Name": "private-1"}
    assert evaluate('{ a = 1, "b" = [true, null], c: 2.5 }') == {
        "a": 1,
        "b": [True, None],
        "c": 2.5,
    }
    assert evaluate('var.env == "prod" ? "big" : "small"', {"var": {"env": "prod"}}) == "big"
    assert evaluate('format("%s-%03d", "web", 7)') == "web-007"
    assert evaluate('"$${literal} and \\"quoted\\""') == '${literal} and "quoted"'


def test_terraform_functions_behave_as_terraform_says():
    assert evaluate('substr(replace(lower("Key-Vault_01"), "/[^a-z0-9]/", ""), 0, 6)') == "keyvau"
    assert evaluate('trim(substr("web-", 0, 63), "-")') == "web"
    assert evaluate('join(",", toset(["b", "a", "b"]))') == "a,b"
    assert evaluate('lookup({ a = 1 }, "b", 2)') == 2
    assert evaluate("one([7])") == 7
    # the registry's zone test, and its subnets
    assert evaluate('length(regexall("^[a-z]{2}-", "eu-west-1a")) > 0') is True
    assert evaluate('regex("^(?P<region>[a-z]+-[a-z]+-[0-9])(?P<zone>[a-z])$", "eu-west-1b")') == {
        "region": "eu-west-1",
        "zone": "b",
    }
    assert evaluate('cidrsubnets("10.0.0.0/16", 4, 4, 8, 4)') == [
        "10.0.0.0/20",
        "10.0.16.0/20",
        "10.0.32.0/24",
        "10.0.48.0/20",
    ]
    assert evaluate('cidrhost("10.0.1.0/24", 5)') == "10.0.1.5"
    assert evaluate("toset([443, 80, 443])") == [80, 443]
    assert evaluate('jsonencode({ b = 1, a = [true, "x"] })') == '{"a":[true,"x"],"b":1}'
    assert evaluate('formatlist("%s-%s", ["a", "b"], "x")') == ["a-x", "b-x"]
    assert evaluate('setproduct(["a"], [1, 2])') == [["a", 1], ["a", 2]]


def test_for_expressions_are_read_per_element():
    scope = {
        "var": {"azs": ["eu-west-1a", "eu-west-1b"], "cidr": "10.60.0.0/16"},
        "local": {
            "services": {
                "worker": {"port": 9000, "public": False},
                "api": {"port": 8080, "public": True},
            }
        },
    }
    assert evaluate("[for k, v in var.azs : cidrsubnet(var.cidr, 4, k)]", scope) == [
        "10.60.0.0/20",
        "10.60.16.0/20",
    ]
    # a map's elements in the order of its keys, filtered
    assert evaluate("{ for name, s in local.services : name => s.port if s.public }", scope) == {
        "api": 8080
    }
    assert evaluate("[for s in values(local.services) : s.port]", scope) == [8080, 9000]
    assert evaluate("{ for i, name in keys(local.services) : name => i }", scope) == {
        "api": 0,
        "worker": 1,
    }
    # grouped by a key given more than once, and nested
    assert evaluate("{ for k, s in local.services : s.public => k... }", scope) == {
        "false": ["worker"],
        "true": ["api"],
    }
    assert evaluate('[for a in [1, 2] : [for b in ["x", "y"] : "${a}${b}"]]') == [
        ["1x", "1y"],
        ["2x", "2y"],
    ]
    assert evaluate('join(", ", [for p in [80, 443] : "port ${p}"])') == "port 80, port 443"
    # a key given twice without ..., or a collection the reader cannot know
    assert evaluate('{ for k, s in local.services : "same" => k }', scope) is UNKNOWN
    assert evaluate("[for s in var.missing : s]", scope) is UNKNOWN


def test_anything_else_is_unknown_not_an_error():
    for text in (
        "aws_vpc.main.id",
        "var.missing",
        "[for s in var.x : s.id]",
        'base64gzip("x")',
        'file("x")',
        "var.x[*].id",
        "no closing (",
        "tostring(aws_vpc.main.id)",
        'regex("^z", "abc")',
        '{ for k in ["a", "a"] : k => 1 }',
    ):
        assert evaluate(text, {"var": {}}) is UNKNOWN, text


def test_references_are_found_where_they_are_code_with_their_index():
    scope = {"count": {"index": 1}, "each": {"key": "a"}}
    assert references("aws_subnet.private[count.index].id", scope) == ["aws_subnet.private[1]"]
    assert references('aws_subnet.public["a"].id') == ['aws_subnet.public["a"]']
    assert references("[aws_security_group.web.id, module.sg.id]") == [
        "aws_security_group.web",
        "module.sg.id",
    ]
    assert references("module.net.private_ids[count.index]", scope) == ["module.net.private_ids[1]"]
    assert references('"echo ${data.aws_ami.web.id} # not a comment"') == ["data.aws_ami.web"]
    # a string that only looks like an address, and an attribute of a local, name nothing
    assert references('"see aws_docs.page"') == []
    assert references("local.subnets.private_a.id") == []
    assert symbols("merge(var.tags, local.extra, { a = var.tags })") == ["var.tags", "local.extra"]
    # a module instance's output, by the key each gives
    assert references("module.sg[each.key].id", scope) == ['module.sg["a"].id']
    assert references("module.sg[var.unknown].id", scope) == ["module.sg.id"]
    assert symbols("try(each.value.port, 80)") == ["each.value"]
    # element()'s list and index, a trailing comma no argument
    assert element_calls(
        "element(\n  aws_subnet.public[*].id,\n  var.single ? 0 : count.index,\n)"
    ) == [("\n  aws_subnet.public[*].id", "\n  var.single ? 0 : count.index")]


def test_the_json_syntax_reads_into_the_same_shape():
    body = parse_json(
        '{"resource": {"aws_vpc": {"main": {"cidr_block": "10.0.0.0/16", "tags": {"Name": "x"}}}},'
        ' "variable": {"region": {"default": "eu-west-1"}}}'
    )
    assert [(b.type, b.labels) for b in body.blocks] == [
        ("resource", ("aws_vpc", "main")),
        ("variable", ("region",)),
    ]
    assert evaluate(body.blocks[0].body.attributes["tags"]) == {"Name": "x"}


def test_a_type_gives_optional_attributes_their_defaults():
    kind = type_of(
        "map(object({ name = string, ports = optional(list(number), [80]), zone = optional(string) }))"
    )
    assert convert({"web": {"name": "w", "ports": ["443"]}, "db": {"name": "d"}}, kind) == {
        "web": {"name": "w", "ports": [443], "zone": None},
        "db": {"name": "d", "ports": [80], "zone": None},
    }
    assert convert("5", type_of("number")) == 5
    assert convert("true", type_of("bool")) is True
    assert convert(UNKNOWN, kind) is UNKNOWN
    # a type the reader does not read converts nothing
    assert type_of("not a type (") == ("any",)


def test_a_function_that_rearranges_values_keeps_those_it_knows():
    scope = {"var": {}}
    assert evaluate("merge({ a = var.missing }, { b = 1 })", scope) == {"a": UNKNOWN, "b": 1}
    assert evaluate("length([var.missing, 2])", scope) == 2
    assert evaluate("keys({ b = var.missing, a = 1 })", scope) == ["a", "b"]
    # one that reads them does not
    assert evaluate('join(",", [var.missing])', scope) is UNKNOWN
    assert evaluate("merge(var.missing, { b = 1 })", scope) is UNKNOWN
    # a module as a value, and an attribute after an output's element
    assert references("module.subnet") == ["module.subnet"]
    assert references('module.vnet.subnets["web"].resource_id') == [
        'module.vnet.subnets["web"].resource_id'
    ]
