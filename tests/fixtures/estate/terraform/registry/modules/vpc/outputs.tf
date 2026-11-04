output "vpc_id" {
  description = "The VPC's id."
  value       = try(aws_vpc.this[0].id, null)
}

output "private_subnets" {
  description = "The private subnets' ids."
  value       = aws_subnet.private[*].id
}

output "public_subnets" {
  description = "The public subnets' ids."
  value       = aws_subnet.public[*].id
}

output "natgw_ids" {
  value = aws_nat_gateway.this[*].id
}
