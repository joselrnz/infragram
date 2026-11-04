# A small shop on AWS, written the way people write Terraform: a network
# module, counted instances behind a load balancer, a queue feeding a
# function, and the helpers every configuration carries.

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region = var.region
}

locals {
  name = "${var.project}-${var.environment}"
}

module "network" {
  source = "./modules/network"

  name = local.name
  cidr = var.cidr
}

module "labels" {
  source  = "cloudposse/label/null"
  version = "0.25.0"
}

data "aws_ami" "linux" {
  most_recent = true
  owners      = ["amazon"]
}

resource "aws_security_group" "alb" {
  name   = "${local.name}-alb"
  vpc_id = module.network.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "web" {
  name   = "${local.name}-web"
  vpc_id = module.network.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "web_from_alb" {
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
}

resource "aws_lb" "public" {
  name               = "${local.name}-alb"
  load_balancer_type = "application"
  subnets            = module.network.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]
}

resource "aws_lb_target_group" "web" {
  name     = "${local.name}-web"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = module.network.vpc_id
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.public.arn
  port              = 443
  protocol          = "HTTPS"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_instance" "web" {
  count = var.web_count

  ami                    = data.aws_ami.linux.id
  instance_type          = "t3.small"
  subnet_id              = module.network.private_subnet_ids[count.index]
  vpc_security_group_ids = [aws_security_group.web.id]

  tags = {
    Name = "${local.name}-web-${count.index + 1}"
  }
}

resource "aws_lb_target_group_attachment" "web" {
  count = var.web_count

  target_group_arn = aws_lb_target_group.web.arn
  target_id        = aws_instance.web[count.index].id
}

resource "aws_sqs_queue" "jobs" {
  name = "${local.name}-jobs"
}

resource "aws_lambda_function" "worker" {
  function_name = "${local.name}-worker"
  role          = aws_iam_role.worker.arn
  runtime       = "python3.12"
  handler       = "app.handler"
  filename      = "worker.zip"
}

resource "aws_lambda_event_source_mapping" "jobs" {
  event_source_arn = aws_sqs_queue.jobs.arn
  function_name    = aws_lambda_function.worker.arn
}

resource "aws_iam_role" "worker" {
  name               = "${local.name}-worker"
  assume_role_policy = jsonencode({ Version = "2012-10-17" })
}

resource "random_password" "db" {
  length = 24
}
