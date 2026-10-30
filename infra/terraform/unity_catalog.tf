locals {
  uc_root_url = "abfss://${azurerm_storage_container.uc_root.name}@${azurerm_storage_account.uc.name}.dfs.core.windows.net"
  schemas     = ["raw", "bronze", "silver", "gold", "agents"]
}

resource "databricks_storage_credential" "uc" {
  name    = "sc-${local.name}"
  comment = "Access connector for the macro-peru catalog storage"

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.this.id
  }
}

resource "databricks_external_location" "uc_root" {
  name            = "el-${local.name}"
  url             = local.uc_root_url
  credential_name = databricks_storage_credential.uc.name
  comment         = "Root of the macro-peru catalog storage"
  depends_on      = [azurerm_role_assignment.connector_storage]
}

resource "databricks_catalog" "this" {
  name         = var.catalog_name
  storage_root = "${local.uc_root_url}/${var.catalog_name}"
  comment      = "Analista Macro Peru: BCRP data and agent (${var.env})"
  properties   = local.tags
  depends_on   = [databricks_external_location.uc_root]
}

resource "databricks_schema" "this" {
  for_each     = toset(local.schemas)
  catalog_name = databricks_catalog.this.name
  name         = each.key
}

resource "databricks_volume" "raw" {
  for_each     = toset(["raw_api", "raw_docs"])
  catalog_name = databricks_catalog.this.name
  schema_name  = databricks_schema.this["raw"].name
  name         = each.key
  volume_type  = "MANAGED"
}

# The CI/CD SP deploys jobs, pipelines, functions and models into the catalog.
resource "databricks_grants" "catalog" {
  catalog = databricks_catalog.this.name

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }

  grant {
    principal = databricks_service_principal.cicd.application_id
    privileges = [
      "USE_CATALOG", "USE_SCHEMA", "CREATE_SCHEMA", "CREATE_TABLE", "CREATE_FUNCTION",
      "CREATE_MODEL", "CREATE_VOLUME", "CREATE_MATERIALIZED_VIEW", "SELECT", "MODIFY",
      "EXECUTE", "READ_VOLUME", "WRITE_VOLUME",
    ]
  }
}
