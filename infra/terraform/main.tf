locals {
  name = "macro-peru-${var.env}"
  tags = { project = "macro-peru", env = var.env, managed_by = "terraform" }
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

# ADLS Gen2 that backs the Unity Catalog catalog (managed tables and volumes).
resource "azurerm_storage_account" "uc" {
  name                            = "stmacroperu${var.env}${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.this.name
  location                        = azurerm_resource_group.this.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  is_hns_enabled                  = true
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  tags                            = local.tags
}

resource "azurerm_storage_container" "uc_root" {
  name                  = "uc-root"
  storage_account_id    = azurerm_storage_account.uc.id
  container_access_type = "private"
}

# Managed identity that Unity Catalog uses to reach the storage account.
resource "azurerm_databricks_access_connector" "this" {
  name                = "ac-${local.name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "connector_storage" {
  scope                = azurerm_storage_account.uc.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.this.identity[0].principal_id
}

# File events (on by default for new external locations): Databricks creates an
# Event Grid subscription and a Storage Queue so file arrival triggers and Auto Loader
# see new files. Without these roles the setup fails silently and triggers never fire.
resource "azurerm_role_assignment" "connector_file_events" {
  for_each = {
    "Storage Queue Data Contributor" = azurerm_storage_account.uc.id
    "Storage Account Contributor"    = azurerm_storage_account.uc.id
    "EventGrid Data Contributor"     = azurerm_resource_group.this.id
  }
  scope                = each.value
  role_definition_name = each.key
  principal_id         = azurerm_databricks_access_connector.this.identity[0].principal_id
}

resource "azurerm_databricks_workspace" "this" {
  name                        = "dbw-${local.name}"
  resource_group_name         = azurerm_resource_group.this.name
  location                    = azurerm_resource_group.this.location
  sku                         = "premium"
  managed_resource_group_name = "rg-${local.name}-managed"
  tags                        = local.tags
}
