resource "aws_vpc" "main" { cidr_block = "10.0.0.0/16" }
resource "aws_subnet" "a" {
  vpc_id = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}
resource "aws_security_group" "lb" {
  vpc_id = aws_vpc.main.id
  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "app" {
  vpc_id = aws_vpc.main.id
  ingress {
    from_port = 8080
    to_port = 8080
    protocol = "tcp"
    security_groups = [aws_security_group.lb.id]
  }
}
resource "aws_security_group" "db" {
  vpc_id = aws_vpc.main.id
  ingress {
    from_port = 5432
    to_port = 5432
    protocol = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  ingress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    security_groups = [aws_security_group.lb.id]
  }
}
resource "aws_instance" "web" {
  count = 2
  ami = "ami-1"
  instance_type = "t3.micro"
  subnet_id = aws_subnet.a.id
  vpc_security_group_ids = [aws_security_group.app.id]
}
resource "aws_db_instance" "db" {
  engine = "postgres"
  instance_class = "db.t3.micro"
  vpc_security_group_ids = [aws_security_group.db.id]
}
resource "aws_lb" "alb" {
  subnets = [aws_subnet.a.id]
  security_groups = [aws_security_group.lb.id]
}
