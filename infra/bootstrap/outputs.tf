output "client_id" {
  value = azuread_application.cicd.client_id
}

output "service_principal_object_id" {
  value = azuread_service_principal.cicd.object_id
}

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  value = var.subscription_id
}

output "tfstate_storage_account" {
  value = azurerm_storage_account.tfstate.name
}
