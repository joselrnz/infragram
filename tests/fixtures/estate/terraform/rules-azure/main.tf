# Network security groups on Azure, written the way people write them: one
# group with inline rules on a subnet, one with rule resources on a network
# interface, and an application security group the web servers join.

terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "shop" {
  name     = "rg-shop"
  location = "westeurope"
}

resource "azurerm_virtual_network" "shop" {
  name                = "vnet-shop"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name
  address_space       = ["10.1.0.0/16"]
}

resource "azurerm_subnet" "web" {
  name                 = "snet-web"
  resource_group_name  = azurerm_resource_group.shop.name
  virtual_network_name = azurerm_virtual_network.shop.name
  address_prefixes     = ["10.1.1.0/24"]
}

resource "azurerm_subnet" "data" {
  name                 = "snet-data"
  resource_group_name  = azurerm_resource_group.shop.name
  virtual_network_name = azurerm_virtual_network.shop.name
  address_prefixes     = ["10.1.2.0/24"]
}

resource "azurerm_subnet" "ops" {
  name                 = "snet-ops"
  resource_group_name  = azurerm_resource_group.shop.name
  virtual_network_name = azurerm_virtual_network.shop.name
  address_prefixes     = ["10.1.3.0/24"]
}

# ------------------------------------------------------------------ servers
resource "azurerm_network_interface" "web" {
  count               = 2
  name                = "nic-web-${count.index}"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.web.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_linux_virtual_machine" "web" {
  count                 = 2
  name                  = "vm-web-${count.index}"
  resource_group_name   = azurerm_resource_group.shop.name
  location              = azurerm_resource_group.shop.location
  size                  = "Standard_B2s"
  admin_username        = "shop"
  network_interface_ids = [azurerm_network_interface.web[count.index].id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}

resource "azurerm_network_interface" "db" {
  name                = "nic-db"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.data.id
    private_ip_address_allocation = "Static"
    private_ip_address            = "10.1.2.10"
  }
}

resource "azurerm_linux_virtual_machine" "db" {
  name                  = "vm-db"
  resource_group_name   = azurerm_resource_group.shop.name
  location              = azurerm_resource_group.shop.location
  size                  = "Standard_D4s_v5"
  admin_username        = "shop"
  network_interface_ids = [azurerm_network_interface.db.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}

resource "azurerm_network_interface" "jump" {
  name                = "nic-jump"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.ops.id
    private_ip_address_allocation = "Static"
    private_ip_address            = "10.1.3.4"
  }
}

resource "azurerm_linux_virtual_machine" "jump" {
  name                  = "vm-jump"
  resource_group_name   = azurerm_resource_group.shop.name
  location              = azurerm_resource_group.shop.location
  size                  = "Standard_B1s"
  admin_username        = "shop"
  network_interface_ids = [azurerm_network_interface.jump.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}

resource "azurerm_application_security_group" "web" {
  name                = "asg-web"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name
}

resource "azurerm_network_interface_application_security_group_association" "web" {
  count                         = 2
  network_interface_id          = azurerm_network_interface.web[count.index].id
  application_security_group_id = azurerm_application_security_group.web.id
}

# ------------------------------------------------------------------ the web subnet's group, inline rules
resource "azurerm_network_security_group" "web" {
  name                = "nsg-web"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name

  security_rule {
    name                       = "https-in"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "ssh-from-jump"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "10.1.3.4/32"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "vnet-in"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "deny-rest"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "web" {
  subnet_id                 = azurerm_subnet.web.id
  network_security_group_id = azurerm_network_security_group.web.id
}

# ------------------------------------------------------------------ the database's group, rule resources
resource "azurerm_network_security_group" "data" {
  name                = "nsg-data"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name
}

resource "azurerm_network_security_rule" "postgres" {
  name                                  = "postgres-from-web"
  priority                              = 100
  direction                             = "Inbound"
  access                                = "Allow"
  protocol                              = "Tcp"
  source_port_range                     = "*"
  destination_port_range                = "5432"
  source_application_security_group_ids = [azurerm_application_security_group.web.id]
  destination_address_prefix            = "*"
  resource_group_name                   = azurerm_resource_group.shop.name
  network_security_group_name           = azurerm_network_security_group.data.name
}

resource "azurerm_network_security_rule" "admin" {
  name                        = "admin-from-ops"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_ranges     = ["22", "8000-8080"]
  source_address_prefix       = "10.1.3.0/24"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.shop.name
  network_security_group_name = azurerm_network_security_group.data.name
}

# a range that holds the database's own subnet says anything inside may pass
resource "azurerm_network_security_rule" "inside" {
  name                        = "anything-inside"
  priority                    = 200
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "9000"
  source_address_prefix       = "10.1.0.0/16"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.shop.name
  network_security_group_name = azurerm_network_security_group.data.name
}

resource "azurerm_network_interface_security_group_association" "db" {
  network_interface_id      = azurerm_network_interface.db.id
  network_security_group_id = azurerm_network_security_group.data.id
}
