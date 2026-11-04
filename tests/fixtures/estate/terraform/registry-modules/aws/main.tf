# The public registry's own modules, called as a team calls them: read from
# the module cache (infragram's, filled once) at the versions pinned here.

provider "aws" {
  region = "eu-west-1"
}

locals {
  name = "shop-prod"
  azs  = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name             = local.name
  cidr             = "10.0.0.0/16"
  azs              = local.azs
  private_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets   = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  database_subnets = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  tags = { Environment = "prod" }
}

module "web_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "6.0.0"

  name   = "${local.name}-web"
  vpc_id = module.vpc.vpc_id
  ingress_rules = {
    https = { cidr_ipv4 = "0.0.0.0/0", from_port = 443, to_port = 443 }
  }
}

module "db_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "6.0.0"

  name   = "${local.name}-db"
  vpc_id = module.vpc.vpc_id
  ingress_rules = {
    postgres = { referenced_security_group_id = module.web_sg.id, from_port = 5432, to_port = 5432 }
  }
}

module "web" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.4"

  name                   = "${local.name}-web"
  instance_type          = "t3.small"
  subnet_id              = element(module.vpc.public_subnets, 0)
  create_security_group  = false
  vpc_security_group_ids = [module.web_sg.id]
}

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "7.2.2"

  identifier           = "${local.name}-db"
  engine               = "postgres"
  engine_version       = "16"
  family               = "postgres16"
  major_engine_version = "16"
  instance_class       = "db.t4g.medium"
  allocated_storage    = 20
  db_name              = "shop"
  username             = "shop"

  db_subnet_group_name   = module.vpc.database_subnet_group
  vpc_security_group_ids = [module.db_sg.id]
  multi_az               = true
}
