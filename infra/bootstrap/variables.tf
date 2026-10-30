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
  description = "GitHub repository as it appears in the OIDC token subject. Repos with immutable subjects (GitHub default) use owner@owner_id/name@repo_id; check GET /repos/{owner}/{repo}/actions/oidc/customization/sub"
  type        = string
  default     = "Danzstorm@54243238/macro-peru-agent@1440036337"
}
