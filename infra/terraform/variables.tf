variable "subscription_id" {
  type = string
}

variable "location" {
  type    = string
  default = "eastus2"
}

variable "env" {
  description = "Environment name (dev)"
  type        = string
}

variable "catalog_name" {
  description = "Unity Catalog catalog for this environment"
  type        = string
}

variable "cicd_client_id" {
  description = "Application (client) ID of the CI/CD service principal created in infra/bootstrap"
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget in USD for each resource group"
  type        = number
}

variable "alert_emails" {
  description = "Budget alert recipients. Pass with TF_VAR_alert_emails; never commit it."
  type        = list(string)
}
