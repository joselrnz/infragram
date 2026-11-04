variable "project" {
  type = string
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "web_count" {
  type    = number
  default = 2
}
