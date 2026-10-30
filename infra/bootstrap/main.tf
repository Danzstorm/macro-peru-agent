# One-time bootstrap, applied locally with `az login` (local state, never committed).
# Creates what CI/CD needs before it can run: remote state storage and an Entra ID
# service principal that GitHub Actions uses through OIDC (no client secrets).

terraform {
  required_version = ">= 1.7"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id     = var.subscription_id
  storage_use_azuread = true
}

provider "azuread" {}

data "azurerm_client_config" "current" {}

locals {
  tags = { project = "macro-peru", managed_by = "terraform-bootstrap" }
  # Built-in role "Storage Blob Data Contributor".
  storage_blob_data_contributor_id = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
}

# ---------- Remote state ----------

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-macro-peru-tfstate"
  location = var.location
  tags     = local.tags
}

resource "azurerm_storage_account" "tfstate" {
  name                            = "stmacroperutf${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.tfstate.name
  location                        = azurerm_resource_group.tfstate.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false # Entra ID auth only
  tags                            = local.tags

  blob_properties {
    versioning_enabled = true # recover from a corrupted state file
  }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.tfstate.id
  container_access_type = "private"
  depends_on            = [azurerm_role_assignment.me_tfstate]
}

# The local user also authenticates to the state with Entra ID.
resource "azurerm_role_assignment" "me_tfstate" {
  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ---------- CI/CD identity (OIDC) ----------

resource "azuread_application" "cicd" {
  display_name = "sp-macro-peru-cicd"
  owners       = [data.azurerm_client_config.current.object_id]
}

resource "azuread_service_principal" "cicd" {
  client_id = azuread_application.cicd.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}

resource "azuread_application_federated_identity_credential" "github" {
  for_each = {
    main         = "repo:${var.github_repo}:ref:refs/heads/main"
    pull-request = "repo:${var.github_repo}:pull_request"
    env-prod     = "repo:${var.github_repo}:environment:prod"
  }
  application_id = azuread_application.cicd.id
  display_name   = "github-${each.key}"
  issuer         = "https://token.actions.githubusercontent.com"
  audiences      = ["api://AzureADTokenExchange"]
  subject        = each.value
}

resource "azurerm_role_assignment" "cicd_contributor" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.cicd.object_id
}

# Least privilege: the SP may create/delete role assignments, but ONLY for
# "Storage Blob Data Contributor" (needed by the Databricks Access Connector).
resource "azurerm_role_assignment" "cicd_rbac_admin_constrained" {
  scope                = "/subscriptions/${var.subscription_id}"
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azuread_service_principal.cicd.object_id
  condition_version    = "2.0"
  condition            = <<-EOT
    (
     (
      !(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})
     )
     OR
     (
      @Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.storage_blob_data_contributor_id}}
     )
    )
    AND
    (
     (
      !(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'})
     )
     OR
     (
      @Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.storage_blob_data_contributor_id}}
     )
    )
  EOT
}

resource "azurerm_role_assignment" "cicd_tfstate" {
  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.cicd.object_id
}
