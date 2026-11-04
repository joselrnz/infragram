# A security group module: one group, its rules for_each over a map built
# by a for expression.

variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "ingress_rules" {
  type = list(object({
    port                     = number
    source_security_group_id = optional(string)
    cidr_ipv4                = optional(string)
  }))
  default = []
}

resource "aws_security_group" "this" {
  name_prefix = "${var.name}-"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "this" {
  for_each = { for rule in var.ingress_rules : tostring(rule.port) => rule }

  security_group_id            = aws_security_group.this.id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
  referenced_security_group_id = each.value.source_security_group_id
  cidr_ipv4                    = try(each.value.cidr_ipv4, null)
}

output "security_group_id" {
  value = aws_security_group.this.id
}
