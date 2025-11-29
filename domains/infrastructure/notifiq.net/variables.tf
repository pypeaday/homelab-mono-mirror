variable "cloudflare_api_token" {
  description = "Cloudflare API Token"
}
variable "cloudflare_account_id" {
  description = "value for cloudflare_account_id"
}
variable "namecheap_username" {
  description = "value for namecheap_username"
}
variable "namecheap_api_key" {
  description = "value for namecheap_api_key"
}

# TODO: ovviously come back to these defaults
variable "production_branch" { default = "dev1" }
variable "preview_branch" { default = "dev1" }
variable "cloudflare_pages_name" {
  default = "notifiq-net"
}
variable "cloudflare_account_name" {
}
variable "github_owner" {
  default = "pypeaday"
  # default = "DigitalHarbor7"
}
variable "cloudflare_pages_target_repo" {
  default = "soonish"
}
variable "cloudflare_pages_root_dir" {
  default = "website"
}

# variable "protonmail_verification_key1" {
#   description = "value for protonmail_verification_key"
# }
# variable "protonmail_verification_key2" {
#   description = "value for protonmail_verification_key"
# }
# variable "protonmail_verification_key3" {
#   description = "value for protonmail_verification_key"
# }
