# #!/bin/bash

ZONE_ID="8598a6752f65df7358dcf668dfee3749"

terraform import -var-file .tf.vars cloudflare_record.protonmail2 $ZONE_ID/4988030c490daaab91830b72e0c84602
terraform import -var-file .tf.vars cloudflare_record.protonmail3 $ZONE_ID/ed32869fcf2b40e4083deebb4d660f49
terraform import -var-file .tf.vars cloudflare_record.protonmail $ZONE_ID/baa8586063098fb26c01c8e8d63af2ad

terraform import -var-file .tf.vars cloudflare_record.wildcard $ZONE_ID/0a5a3d5d9537a264080aa3b1e5abb4ed
terraform import -var-file .tf.vars cloudflare_record.mx20 $ZONE_ID/483adf3b86afb64d6d36eefc3fae9a21
terraform import -var-file .tf.vars cloudflare_record.mx10 $ZONE_ID/9a46256e1fa21758c49c57f982c39dd1
terraform import -var-file .tf.vars cloudflare_record.dmarc $ZONE_ID/60e9e7869e7f23fbf7025e5e9558c25b

terraform import -var-file .tf.vars cloudflare_record.spf $ZONE_ID/0c3da479ca9280c4d21ba86644b7c98e
terraform import -var-file .tf.vars cloudflare_record.txt_protonmail_verification $ZONE_ID/c09c649a9fa01f389123d6ee4057de32

# # import the cloudflare_zone resource
terraform import -var-file .tf.vars resource.cloudflare_zone.zone $ZONE_ID

# # import the namecheap_domain_dns resource
terraform import -var-file .tf.vars namecheap_domain_dns.mydns paynepride.com

