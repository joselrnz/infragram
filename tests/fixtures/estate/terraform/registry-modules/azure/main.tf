# Azure Verified Modules: a virtual network written with AzAPI, a network
# security group, and a VM beside them, read from the module cache.

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "shop" {
  name     = "rg-shop"
  location = "westeurope"
}

module "vnet" {
  source  = "Azure/avm-res-network-virtualnetwork/azurerm"
  version = "0.22.2"

  name             = "vnet-shop"
  location         = azurerm_resource_group.shop.location
  parent_id        = azurerm_resource_group.shop.id
  address_space    = ["10.1.0.0/16"]
  enable_telemetry = false

  subnets = {
    web = {
      name             = "snet-web"
      address_prefixes = ["10.1.1.0/24"]
    }
    data = {
      name             = "snet-data"
      address_prefixes = ["10.1.2.0/24"]
    }
  }
}

module "web_nsg" {
  source  = "Azure/avm-res-network-networksecuritygroup/azurerm"
  version = "0.5.1"

  name                = "nsg-web"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name
  enable_telemetry    = false

  security_rules = {
    https = {
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
  }
}

resource "azurerm_network_interface" "web" {
  name                = "nic-web"
  location            = azurerm_resource_group.shop.location
  resource_group_name = azurerm_resource_group.shop.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = module.vnet.subnets["web"].resource_id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_network_interface_security_group_association" "web" {
  network_interface_id      = azurerm_network_interface.web.id
  network_security_group_id = module.web_nsg.resource_id
}

resource "azurerm_linux_virtual_machine" "web" {
  name                  = "vm-web"
  location              = azurerm_resource_group.shop.location
  resource_group_name   = azurerm_resource_group.shop.name
  size                  = "Standard_B2s"
  admin_username        = "shop"
  network_interface_ids = [azurerm_network_interface.web.id]

  admin_ssh_key {
    username   = "shop"
    public_key = var.ssh_public_key
  }

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

variable "ssh_public_key" {
  type = string
}
