resource "azurerm_ai_foundry" "main" {
  name                = "${local.org}-ai-${local.resource_suffix}"
  location            = module.primary_region.location
  resource_group_name = azurerm_resource_group.primary.name
  storage_account_id  = azurerm_storage_account.foundry.id
  key_vault_id        = azurerm_key_vault.main.id

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_ai_services" "main" {
  name                = "${local.org}-ais-${local.resource_suffix}"
  location            = module.primary_region.location
  resource_group_name = azurerm_resource_group.primary.name
  sku_name            = "S0"

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_storage_account" "foundry" {
  name                     = "pinsstadafoundry${var.environment}"
  location                 = module.primary_region.location
  resource_group_name      = azurerm_resource_group.primary.name
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_ai_foundry_project" "default" {
  name               = "${local.org}-aip-${local.resource_suffix}"
  location           = module.primary_region.location
  ai_services_hub_id = azurerm_ai_foundry.main.id

  identity {
    type = "SystemAssigned"
  }
}