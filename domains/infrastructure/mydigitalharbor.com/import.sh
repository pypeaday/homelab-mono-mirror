# #!/bin/bash
ZONE_ID="2c2859cc402bec500562dcb728d42610"
#
# # import the cloudflare_zone resource
terraform import -var-file .tf.vars cloudflare_zone.zone $ZONE_ID
#
terraform import -var-file .tf.vars cloudflare_record.txt_protonmail_verification $ZONE_ID/cef910ec0b418777815ee96c6beb2794

terraform import -var-file .tf.vars cloudflare_record.www $ZONE_ID/a82bf6af19d744b6bf0925ffa7ffe5d1

terraform import -var-file .tf.vars cloudflare_record.mydigitalharbor $ZONE_ID/e0cfeef7e9e85400b1d39409c5a7b72f

terraform import -var-file .tf.vars cloudflare_record.develop $ZONE_ID/0520c17cf8bf03e0ee2618b1e6b0f8b3
# TODO: finish importing stuff
#
#
# # # import the namecheap_domain_dns resource
# terraform import -var-file .tf.vars namecheap_domain_dns.mydns mydigitalharbor.com
