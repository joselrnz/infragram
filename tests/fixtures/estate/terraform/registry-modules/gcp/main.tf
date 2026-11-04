# The Google network module: a VPC network, subnetworks and firewall rules,
# read from the module cache.

provider "google" {
  project = "shop-prod-1234"
  region  = "europe-west1"
}

module "vpc" {
  source  = "terraform-google-modules/network/google"
  version = "~> 18.0"

  project_id   = "shop-prod-1234"
  network_name = "shop-vpc"
  routing_mode = "GLOBAL"

  subnets = [
    {
      subnet_name   = "web"
      subnet_ip     = "10.20.1.0/24"
      subnet_region = "europe-west1"
    },
    {
      subnet_name           = "data"
      subnet_ip             = "10.20.2.0/24"
      subnet_region         = "europe-west1"
      subnet_private_access = "true"
    },
  ]

  ingress_rules = [
    {
      name          = "allow-https"
      source_ranges = ["0.0.0.0/0"]
      target_tags   = ["web"]
      allow = [{
        protocol = "tcp"
        ports    = ["443"]
      }]
    },
    {
      name        = "allow-postgres-from-web"
      source_tags = ["web"]
      target_tags = ["db"]
      allow = [{
        protocol = "tcp"
        ports    = ["5432"]
      }]
    },
  ]
}

resource "google_compute_instance" "web" {
  name         = "web"
  machine_type = "e2-small"
  zone         = "europe-west1-b"
  tags         = ["web"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
  }

  network_interface {
    subnetwork = module.vpc.subnets["europe-west1/web"].self_link
  }
}

resource "google_compute_instance" "db" {
  name         = "db"
  machine_type = "e2-standard-4"
  zone         = "europe-west1-b"
  tags         = ["db"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
  }

  network_interface {
    subnetwork = module.vpc.subnets_self_links[1]
  }
}
