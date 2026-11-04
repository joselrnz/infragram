variable "environment" {
  description = "Where this runs."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "prod"], var.environment)
    error_message = "The environment is staging or prod."
  }
}

variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "cidr" {
  type     = string
  default  = "10.60.0.0/16"
  nullable = false

  validation {
    condition     = can(cidrhost(var.cidr, 0))
    error_message = "The CIDR must be a network."
  }
}

variable "azs" {
  type    = list(string)
  default = ["eu-west-1a", "eu-west-1b"]
}

variable "certificate_arn" {
  type      = string
  default   = null
  sensitive = true
}

variable "settings" {
  type = object({
    retention = optional(number, 30)
    flags     = optional(map(bool), {})
  })
  default = {}
}
