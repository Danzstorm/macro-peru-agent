data "databricks_current_user" "me" {}

# Same Entra ID application that GitHub Actions authenticates as (OIDC).
resource "databricks_service_principal" "cicd" {
  application_id        = var.cicd_client_id
  display_name          = "sp-macro-peru-cicd"
  workspace_access      = true
  databricks_sql_access = true
}

# Trade-off: workspace admin is the simplest way to let the SP create jobs, pipelines,
# serving endpoints and apps. Acceptable for a personal project with a single workspace;
# a shared workspace should use per-resource permissions instead.
data "databricks_group" "admins" {
  display_name = "admins"
}

resource "databricks_group_member" "cicd_admin" {
  group_id  = data.databricks_group.admins.id
  member_id = databricks_service_principal.cicd.id
}
