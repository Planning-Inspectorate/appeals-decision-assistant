locals {
  org              = "pins"
  service_name     = "ada"
  primary_location = "uk-south"

  resource_suffix         = "${local.service_name}-${var.environment}"
  shorter_resource_suffix = var.environment == "training" ? "${local.service_name}trai" : local.resource_suffix

  tags = merge(
    var.tags,
    {
      CreatedBy   = "terraform"
      Environment = var.environment
      ServiceName = local.service_name
      location    = local.primary_location
    }
  )
}
