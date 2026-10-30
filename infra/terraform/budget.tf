# Budget alerts at 50%, 80% and 100% on the project RG and on the Databricks managed RG
# (where the workspace's own storage and networking are billed).
locals {
  budget_scopes = {
    project = azurerm_resource_group.this.id
    managed = azurerm_databricks_workspace.this.managed_resource_group_id
  }
}

resource "azurerm_consumption_budget_resource_group" "this" {
  for_each          = local.budget_scopes
  name              = "budget-${local.name}-${each.key}"
  resource_group_id = each.value
  amount            = var.budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = var.alert_emails
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}
