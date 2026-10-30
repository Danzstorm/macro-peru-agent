# storage_account_name comes from -backend-config (bootstrap output).
# Locally it authenticates with `az login`; in CI with OIDC (ARM_USE_OIDC=true).
terraform {
  backend "azurerm" {
    resource_group_name = "rg-macro-peru-tfstate"
    container_name      = "tfstate"
    key                 = "macro-peru/dev.tfstate"
    use_azuread_auth    = true
  }
}
