variable "subscription_id" {
  description = "Azure subscription where everything is deployed"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus2"
}

variable "github_repo" {
  description = "GitHub repository allowed to authenticate through OIDC (owner/name)"
  type        = string
  default     = "Danzstorm/macro-peru-agent"
}
