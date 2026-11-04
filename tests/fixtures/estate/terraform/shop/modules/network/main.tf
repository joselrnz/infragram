variable "name" {
  type = string
}

variable "cidr" {
  type = string
}

resource "aws_vpc" "this" {
  cidr_block = var.cidr

  tags = {
    Name = var.name
  }
}

resource "aws_subnet" "public" {
  for_each = { a = 0, b = 1 }

  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.cidr, 8, each.value)
  availability_zone       = "eu-central-1${each.key}"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.name}-public-${each.key}"
  }
}

resource "aws_subnet" "private" {
  count = 2

  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.cidr, 8, count.index + 10)
  availability_zone = "eu-central-1${["a", "b"][count.index]}"

  tags = {
    Name = "${var.name}-private-${["a", "b"][count.index]}"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "this" {
  subnet_id     = aws_subnet.public["a"].id
  allocation_id = aws_eip.nat.id
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
