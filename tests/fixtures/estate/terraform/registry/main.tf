# Terraform written the way the registry's modules write it: conditional
# counts, try(), for expressions, dynamic blocks, for_each over maps and over
# a module, heredocs with template directives, splats, and the blocks a
# reader passes over (backend, provider aliases, moved, import, removed,
# check, lifecycle preconditions, variable validations).

terraform {
  required_version = ">= 1.7"

  backend "s3" {
    bucket = "acme-terraform-state"
    key    = "platform/terraform.tfstate"
    region = "eu-west-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.40, < 7.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

locals {
  name = "acme-${var.environment}"
  # a data source's answer: only a plan knows it
  all_azs = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    Environment = var.environment
    Repository  = "github.com/acme/platform"
  }

  services = {
    api    = { port = 8080, public = true, size = "t3.small" }
    worker = { port = 9000, public = false, size = "t3.medium" }
  }
  public_services = { for name, service in local.services : name => service if service.public }
  ports           = [for service in values(local.services) : service.port]
  service_index   = { for i, name in keys(local.services) : name => i }
}

module "vpc" {
  source = "./modules/vpc"

  name            = local.name
  cidr            = var.cidr
  azs             = var.azs
  private_subnets = [for k, v in var.azs : cidrsubnet(var.cidr, 4, k)]
  public_subnets  = [for k, v in var.azs : cidrsubnet(var.cidr, 8, k + 48)]

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "prod"

  tags = local.tags
}

module "service_sg" {
  source   = "./modules/sg"
  for_each = local.services

  name   = "${local.name}-${each.key}"
  vpc_id = module.vpc.vpc_id
  ingress_rules = [
    { port = each.value.port, source_security_group_id = aws_security_group.alb.id },
  ]
}

# ------------------------------------------------------------------ the services
resource "aws_instance" "service" {
  for_each = local.services

  ami                    = data.aws_ami.al2023.id
  instance_type          = each.value.size
  subnet_id              = element(module.vpc.private_subnets, local.service_index[each.key])
  vpc_security_group_ids = [module.service_sg[each.key].security_group_id]
  iam_instance_profile   = aws_iam_instance_profile.service.name

  user_data = <<-EOT
    #!/bin/bash
    echo "${each.key} listens on ${each.value.port}"
    %{for port in local.ports~}
    echo "peer port ${port}"
    %{endfor~}
  EOT

  metadata_options {
    http_tokens = "required"
  }

  dynamic "ebs_block_device" {
    for_each = each.value.public ? [] : [1]

    content {
      device_name = "/dev/sdf"
      volume_size = 50
    }
  }

  lifecycle {
    ignore_changes = [ami]

    precondition {
      condition     = contains(["t3.small", "t3.medium"], each.value.size)
      error_message = "Pick a burstable size."
    }
  }

  tags = merge(local.tags, { Name = "${local.name}-${each.key}" })
}

# ------------------------------------------------------------------ the public edge
resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "The public load balancer: ${join(", ", [for p in [80, 443] : "port ${p}"])}"
  vpc_id      = module.vpc.vpc_id

  dynamic "ingress" {
    for_each = toset([80, 443])

    content {
      description = "from anywhere on ${ingress.value}"
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "public" {
  count = length(local.public_services) > 0 ? 1 : 0

  name               = "${local.name}-public"
  load_balancer_type = "application"
  subnets            = module.vpc.public_subnets
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "service" {
  for_each = local.public_services

  name     = substr("${local.name}-${each.key}", 0, 32)
  port     = each.value.port
  protocol = "HTTP"
  vpc_id   = module.vpc.vpc_id

  health_check {
    path    = "/health"
    matcher = "200-299"
  }
}

resource "aws_lb_target_group_attachment" "service" {
  for_each = local.public_services

  target_group_arn = aws_lb_target_group.service[each.key].arn
  target_id        = aws_instance.service[each.key].id
}

resource "aws_lb_listener" "https" {
  count = length(local.public_services) > 0 ? 1 : 0

  load_balancer_arn = aws_lb.public[0].arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.service["api"].arn
  }
}

# ------------------------------------------------------------------ identity
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "service" {
  name               = "${local.name}-service"
  assume_role_policy = data.aws_iam_policy_document.assume.json

  inline_policy {
    name = "logs"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }]
    })
  }
}

resource "aws_iam_instance_profile" "service" {
  name = "${local.name}-service"
  role = aws_iam_role.service.name
}

resource "aws_s3_bucket" "logs" {
  provider = aws.us_east_1

  bucket        = "acme-logs-${var.environment}"
  force_destroy = var.environment != "prod"
}

# ------------------------------------------------------------------ what a reader passes over
moved {
  from = aws_instance.api
  to   = aws_instance.service["api"]
}

import {
  to = aws_s3_bucket.logs
  id = "acme-logs-prod"
}

removed {
  from = aws_s3_bucket.old

  lifecycle {
    destroy = false
  }
}

check "health" {
  data "http" "api" {
    url = "https://${aws_lb.public[0].dns_name}/health"
  }

  assert {
    condition     = data.http.api.status_code == 200
    error_message = "The API is not healthy."
  }
}
