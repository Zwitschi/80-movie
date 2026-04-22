locals {
  dns_record_domain = "${local.dns_record_fqdn}."
}

resource "oci_dns_zone" "primary" {
  compartment_id = var.compartment_ocid
  name           = local.normalized_zone_name
  zone_type      = "PRIMARY"
}

resource "oci_dns_rrset" "website_a" {
  zone_name_or_id = oci_dns_zone.primary.name
  domain          = local.dns_record_domain
  rtype           = "A"

  items {
    domain = local.dns_record_domain
    rdata  = oci_load_balancer_load_balancer.web.ip_address_details[0].ip_address
    rtype  = "A"
    ttl    = var.dns_record_ttl
  }
}
