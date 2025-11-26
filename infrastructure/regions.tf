module "primary_region" {
  # checkov:skip=CKV_TF_1: Trusted Source

  source  = "claranet/regions/azurerm"
  version = "8.0.2"

  azure_region = local.primary_location
}
