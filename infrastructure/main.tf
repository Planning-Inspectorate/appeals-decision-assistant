data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "primary" {
  name     = "${local.org}-rg-${local.resource_suffix}"
  location = module.primary_region.location

  tags = local.tags
}

resource "azurerm_key_vault" "main" {

  # checkov:skip=CKV_AZURE_189: Consider moving to VPN; requires RBAC
  # checkov:skip=CKV_AZURE_109: Route traffic via a VNet; Private Endpoint consideration
  # checkov:skip=CKV2_AZURE_32: Private Endpoint relies on the VNet

  name                        = "${local.org}-kv-${local.shorter_resource_suffix}-euw"
  location                    = module.primary_region.location
  resource_group_name         = azurerm_resource_group.primary.name
  enabled_for_disk_encryption = true
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days  = 7
  purge_protection_enabled    = true
  enable_rbac_authorization   = true
  sku_name                    = "standard"

  tags = local.tags
}
