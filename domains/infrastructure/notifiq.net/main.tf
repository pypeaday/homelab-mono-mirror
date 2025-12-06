resource "cloudflare_zone" "zone" {
  # account_id = data.cloudflare_accounts.cloudflare_account_data.id
  account_id = local.account_id
  zone       = local.domain
}

resource "cloudflare_record" "www" {
  zone_id = cloudflare_zone.zone.id

  name            = "www"
  type            = "CNAME"
  proxied         = true
  ttl             = 1
  allow_overwrite = false

  content = local.pages_domain
}

resource "cloudflare_record" "develop" {
  zone_id = cloudflare_zone.zone.id

  name            = "develop"
  type            = "CNAME"
  proxied         = true
  ttl             = 1
  allow_overwrite = false

  content = "develop.${local.pages_domain}"
}

resource "cloudflare_record" "domain" {
  zone_id = cloudflare_zone.zone.id

  name            = local.domain
  type            = "CNAME"
  proxied         = true
  ttl             = 1
  allow_overwrite = false

  content = local.pages_domain
}

# TODO: this stuff can come out to an email module or something
# resource "cloudflare_record" "protonmail" {
#   zone_id = cloudflare_zone.zone.id
#
#   name            = "protonmail._domainkey"
#   content         = var.protonmail_verification_key1
#   type            = "CNAME"
#   proxied         = false
#   ttl             = 1
#   allow_overwrite = false
# }
# resource "cloudflare_record" "protonmail2" {
#   zone_id         = cloudflare_zone.zone.id
#   name            = "protonmail2._domainkey"
#   content         = var.protonmail_verification_key2
#   type            = "CNAME"
#   proxied         = false
#   ttl             = 1
#   allow_overwrite = false
# }
#
# resource "cloudflare_record" "protonmail3" {
#   zone_id = cloudflare_zone.zone.id
#
#   name            = "protonmail3._domainkey"
#   content         = var.protonmail_verification_key3
#   type            = "CNAME"
#   proxied         = false
#   ttl             = 1
#   allow_overwrite = false
# }
# # TODO: couldn't add these with terraform for some reason
# # resource "cloudflare_record" "mx20" {
# #   zone_id = cloudflare_zone.zone.id
# #
# #   name            = local.domain
# #   type            = "MX"
# #   proxied         = false
# #   ttl             = 1
# #   allow_overwrite = false
# #   priority        = 20
# #
# #   data {
# #     target   = "mailsec.protonmail.ch"
# #     priority = 20
# #   }
# # }
# # resource "cloudflare_record" "mx10" {
# #   zone_id = cloudflare_zone.zone.id
# #
# #   name            = local.domain
# #   type            = "MX"
# #   proxied         = false
# #   ttl             = 1
# #   allow_overwrite = false
# #   priority        = 10
# #
# #   data {
# #     target = "mail.protonmail.ch"
# #     priority = 10
# #   }
# # }
# resource "cloudflare_record" "dmarc" {
#   zone_id = cloudflare_zone.zone.id
#
#   name            = "_dmarc"
#   type            = "TXT"
#   proxied         = false
#   ttl             = 1
#   allow_overwrite = false
#
#   content = "v=DMARC1; p=quarantine"
# }
# resource "cloudflare_record" "spf" {
#   zone_id = cloudflare_zone.zone.id
#
#   name            = local.domain
#   type            = "TXT"
#   proxied         = false
#   ttl             = 1
#   allow_overwrite = false
#
#   content = "v=spf1 include:_spf.protonmail.ch ~all"
# }
# resource "cloudflare_record" "txt_protonmail_verification" {
#   zone_id = cloudflare_zone.zone.id
#
#   name            = local.domain
#   type            = "TXT"
#   proxied         = false
#   ttl             = 1
#   allow_overwrite = false
#
#   content = "protonmail-verification=c9e84890def02f217b6e860913118e7524af7e52"
# }
#
# ################################################################################
#
# Create a new Namecheap domain DNS
resource "namecheap_domain_dns" "mydns" {
  provider = namecheapecosystem
  domain   = local.domain

  nameservers = cloudflare_zone.zone.name_servers
}


# Cloudflare Pages project with managing build config
resource "cloudflare_pages_project" "build_config" {
  # account_id = data.cloudflare_accounts.cloudflare_account_data.id
  account_id = var.cloudflare_account_id

  name              = local.cloudflare_pages_name
  production_branch = var.production_branch
  source {
    type = "github"
    config {
      owner                         = var.github_owner
      repo_name                     = var.cloudflare_pages_target_repo
      production_branch             = var.production_branch
      production_deployment_enabled = true
      preview_branch_includes       = [var.preview_branch]
    }
  }
  build_config {
    root_dir = var.cloudflare_pages_root_dir
  }
  deployment_configs {
    preview {}
    production {}
  }
}
resource "cloudflare_pages_domain" "cf_domain" {
  count = local.domain != "" ? 1 : 0

  # account_id = data.cloudflare_accounts.cloudflare_account_data.id
  account_id   = local.account_id
  project_name = cloudflare_pages_project.build_config.name
  domain       = local.domain
}

resource "cloudflare_pages_domain" "cf_domain_develop" {
  count = local.domain != "" ? 1 : 0

  account_id   = local.account_id
  project_name = cloudflare_pages_project.build_config.name
  domain       = "develop.${local.domain}"
}

resource "cloudflare_pages_domain" "cf_domain_www" {
  count = local.domain != "" ? 1 : 0

  account_id   = local.account_id
  project_name = cloudflare_pages_project.build_config.name
  domain       = "www.${local.domain}"
}

