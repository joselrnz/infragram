"""The HCL writer lays text out the way ``terraform fmt`` does.

``verify:terraform`` holds every shipped skeleton to the Terraform CLI itself;
these hold the writer's rules without it:

- the ``=`` of consecutive one-line attributes align, and a blank line, a
  comment, a nested block or a value spanning lines ends the group;
- a list of scalars stays on one line, objects span lines;
- a file has one blank line between blocks and none after a comment;
- strings are quoted, and diagram text never becomes a template.
"""

from __future__ import annotations

from infragram.terraform.hcl import (
    BLANK,
    Attr,
    Block,
    Comment,
    Raw,
    identifier,
    literal,
    quote,
    render,
)


def test_consecutive_one_line_attributes_align_their_equals():
    text = render(
        [
            Block(
                "resource",
                ("aws_vpc", "main"),
                [
                    Attr("cidr_block", "10.0.0.0/16"),
                    Attr("enable_dns_support", True),
                ],
            )
        ]
    )
    assert text == (
        'resource "aws_vpc" "main" {\n'
        '  cidr_block         = "10.0.0.0/16"\n'
        "  enable_dns_support = true\n"
        "}\n"
    )


def test_a_blank_a_comment_a_block_or_a_value_spanning_lines_ends_the_group():
    text = render(
        [
            Block(
                "resource",
                ("x", "y"),
                [
                    Attr("a", 1),
                    Attr("long_name", 2),
                    BLANK,
                    Attr("b", 3),
                    Comment("note"),
                    Attr("cc", 4),
                    Block("inner", (), [Attr("k", "v")]),
                    Attr("d", 5),
                    Attr("tags", {"Name": "n", "Environment": Raw("var.environment")}),
                    Attr("eee", 6),
                ],
            )
        ]
    )
    assert text == (
        'resource "x" "y" {\n'
        "  a         = 1\n"
        "  long_name = 2\n"
        "\n"
        "  b = 3\n"
        "  # note\n"
        "  cc = 4\n"
        "  inner {\n"
        '    k = "v"\n'
        "  }\n"
        "  d = 5\n"
        "  tags = {\n"
        '    Name        = "n"\n'
        "    Environment = var.environment\n"
        "  }\n"
        "  eee = 6\n"
        "}\n"
    )


def test_scalars_stay_on_one_line_and_objects_in_a_list_span_lines():
    text = render(
        [
            Block(
                "locals",
                (),
                [
                    Attr("zones", ["a", "b"]),
                    Attr("empty", []),
                    Attr("none", {}),
                    Attr("rules", [{"port": 443}, {"port": 80}]),
                ],
            )
        ]
    )
    assert text == (
        "locals {\n"
        '  zones = ["a", "b"]\n'
        "  empty = []\n"
        "  none  = {}\n"
        "  rules = [\n"
        "    {\n"
        "      port = 443\n"
        "    },\n"
        "    {\n"
        "      port = 80\n"
        "    },\n"
        "  ]\n"
        "}\n"
    )


def test_a_file_has_one_blank_line_between_blocks_and_none_after_a_comment():
    text = render([Comment("first"), Block("a", (), [Attr("x", 1)]), Block("b", ("l",), [])])
    assert text == '# first\na {\n  x = 1\n}\n\nb "l" {}\n'


def test_a_long_comment_wraps_inside_eighty_columns():
    text = render([Block("a", (), [Comment("word " * 40), Attr("x", 1)])])
    comments = [line for line in text.splitlines() if line.lstrip().startswith("#")]
    assert len(comments) > 1
    assert all(len(line) <= 80 for line in comments)


def test_strings_are_quoted_and_diagram_text_is_never_a_template():
    assert quote('say "hi"\\ok\n') == '"say \\"hi\\"\\\\ok\\n"'
    assert quote("${var.name_prefix}-web") == '"${var.name_prefix}-web"'
    assert literal("cost ${price} and %{if x}") == "cost $${price} and %%{if x}"


def test_identifiers_are_names_terraform_accepts():
    assert identifier("web-a") == "web_a"
    assert identifier("A.B  C") == "a_b_c"
    assert identifier("3tier") == "n_3tier"
    assert identifier("  ") == "unnamed"
