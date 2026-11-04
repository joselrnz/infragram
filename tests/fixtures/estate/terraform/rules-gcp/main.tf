# Firewall rules on Google Cloud, written the way people write them: by
# network tag, by service account, from the internet, from a subnetwork's
# range, from Google's own ranges, and the broad internal rule.

terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = "shop-prod-1234"
  region  = "europe-west1"
}

resource "google_compute_network" "vpc" {
  name                    = "shop-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "web" {
  name          = "web"
  ip_cidr_range = "10.20.1.0/24"
  region        = "europe-west1"
  network       = google_compute_network.vpc.id
}

resource "google_compute_subnetwork" "data" {
  name          = "data"
  ip_cidr_range = "10.20.2.0/24"
  region        = "europe-west1"
  network       = google_compute_network.vpc.id
}

resource "google_compute_subnetwork" "app" {
  name          = "app"
  ip_cidr_range = "10.20.3.0/24"
  region        = "europe-west1"
  network       = google_compute_network.vpc.id
}

resource "google_service_account" "web" {
  account_id = "web"
}

resource "google_service_account" "db" {
  account_id = "db"
}

# ------------------------------------------------------------------ instances
resource "google_compute_instance" "web" {
  count        = 2
  name         = "web-${count.index}"
  machine_type = "e2-small"
  zone         = "europe-west1-b"
  tags         = ["web", "ssh"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.web.id
  }

  service_account {
    email  = google_service_account.web.email
    scopes = ["cloud-platform"]
  }
}

resource "google_compute_instance" "bastion" {
  name         = "bastion"
  machine_type = "e2-micro"
  zone         = "europe-west1-b"
  tags         = ["bastion"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.web.id
    access_config {}
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
    subnetwork = google_compute_subnetwork.data.id
    network_ip = "10.20.2.10"
  }

  service_account {
    email  = google_service_account.db.email
    scopes = ["cloud-platform"]
  }
}

# a managed instance group wears its template's tags
resource "google_compute_instance_template" "api" {
  name_prefix  = "api-"
  machine_type = "e2-medium"
  tags         = ["api"]

  disk {
    source_image = "debian-cloud/debian-12"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.app.id
  }
}

resource "google_compute_region_instance_group_manager" "api" {
  name               = "api"
  region             = "europe-west1"
  base_instance_name = "api"
  target_size        = 3

  version {
    instance_template = google_compute_instance_template.api.id
  }
}

# ------------------------------------------------------------------ rules
resource "google_compute_firewall" "https" {
  name          = "allow-https"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["web"]

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
}

resource "google_compute_firewall" "ssh" {
  name        = "allow-ssh-from-bastion"
  network     = google_compute_network.vpc.name
  source_tags = ["bastion"]
  target_tags = ["ssh"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_firewall" "postgres" {
  name                    = "allow-postgres-from-web"
  network                 = google_compute_network.vpc.id
  source_service_accounts = [google_service_account.web.email]
  target_service_accounts = [google_service_account.db.email]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

resource "google_compute_firewall" "metrics" {
  name          = "allow-metrics-from-web"
  network       = google_compute_network.vpc.name
  source_ranges = ["10.20.1.0/24"]
  target_tags   = ["db"]

  allow {
    protocol = "tcp"
    ports    = ["9100", "9187"]
  }
}

resource "google_compute_firewall" "api" {
  name        = "allow-api-from-web"
  network     = google_compute_network.vpc.name
  source_tags = ["web"]
  target_tags = ["api"]

  allow {
    protocol = "6"
    ports    = ["8080"]
  }
}

# the load balancer's health checkers reach nothing drawn
resource "google_compute_firewall" "health" {
  name          = "allow-health-checks"
  network       = google_compute_network.vpc.name
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["api"]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}

# Identity-Aware Proxy's range reaches nothing in the network
resource "google_compute_firewall" "iap" {
  name          = "allow-iap-ssh"
  network       = google_compute_network.vpc.name
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["ssh"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# a range that holds every subnetwork says anything inside may pass
resource "google_compute_firewall" "internal" {
  name          = "allow-internal"
  network       = google_compute_network.vpc.name
  source_ranges = ["10.20.0.0/16"]

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }
}

resource "google_compute_firewall" "ping" {
  name          = "allow-ping"
  network       = google_compute_network.vpc.name
  source_ranges = ["0.0.0.0/0"]

  allow {
    protocol = "icmp"
  }
}

resource "google_compute_firewall" "legacy" {
  name          = "allow-legacy"
  network       = google_compute_network.vpc.name
  disabled      = true
  source_ranges = ["0.0.0.0/0"]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}

resource "google_compute_firewall" "egress" {
  name               = "deny-egress"
  network            = google_compute_network.vpc.name
  direction          = "EGRESS"
  destination_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }
}
