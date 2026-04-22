locals {
  normalized_zone_name = trimsuffix(var.dns_zone_name, ".")

  # Build FQDN from label + zone. '@' represents the root record.
  dns_record_fqdn = var.dns_record_name == "@" ? local.normalized_zone_name : "${var.dns_record_name}.${local.normalized_zone_name}"
}

output "public_ip" {
  description = "Public IP address for the compute instance."
  value       = oci_core_instance.web.public_ip
}

output "load_balancer_hostname" {
  description = "Load balancer public IP address."
  value       = try(oci_load_balancer_load_balancer.web.ip_address_details[0].ip_address, null)
}

output "dns_record_fqdn" {
  description = "Fully qualified DNS name for the public website record."
  value       = local.dns_record_fqdn
}
