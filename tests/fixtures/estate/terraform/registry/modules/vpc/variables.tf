variable "create_vpc" {
  type    = bool
  default = true
}

variable "putin_khuylo" {
  type    = bool
  default = true
}

variable "name" {
  type    = string
  default = ""
}

variable "cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "secondary_cidr_blocks" {
  type    = list(string)
  default = []
}

variable "use_ipam_pool" {
  type    = bool
  default = false
}

variable "enable_dns_hostnames" {
  type    = bool
  default = true
}

variable "enable_dns_support" {
  type    = bool
  default = true
}

variable "azs" {
  type    = list(string)
  default = []
}

variable "public_subnets" {
  type    = list(string)
  default = []
}

variable "public_subnet_ipv6_prefixes" {
  type    = list(string)
  default = []
}

variable "public_subnet_ipv6_native" {
  type    = bool
  default = false
}

variable "public_subnet_names" {
  type    = list(string)
  default = []
}

variable "public_subnet_suffix" {
  type    = string
  default = "public"
}

variable "public_subnet_tags_per_az" {
  type    = map(map(string))
  default = {}
}

variable "map_public_ip_on_launch" {
  type    = bool
  default = false
}

variable "private_subnets" {
  type    = list(string)
  default = []
}

variable "private_subnet_ipv6_prefixes" {
  type    = list(string)
  default = []
}

variable "private_subnet_names" {
  type    = list(string)
  default = []
}

variable "private_subnet_suffix" {
  type    = string
  default = "private"
}

variable "create_igw" {
  type    = bool
  default = true
}

variable "enable_nat_gateway" {
  type    = bool
  default = false
}

variable "single_nat_gateway" {
  type    = bool
  default = false
}

variable "one_nat_gateway_per_az" {
  type    = bool
  default = false
}

variable "reuse_nat_ips" {
  type    = bool
  default = false
}

variable "external_nat_ip_ids" {
  type    = list(string)
  default = []
}

variable "nat_gateway_destination_cidr_block" {
  type    = string
  default = "0.0.0.0/0"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "vpc_tags" {
  type    = map(string)
  default = {}
}
