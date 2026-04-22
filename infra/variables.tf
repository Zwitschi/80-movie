variable "tenancy_ocid" {
  description = "OCI tenancy OCID."
  type        = string
}

variable "user_ocid" {
  description = "OCI user OCID used by Terraform."
  type        = string
}

variable "fingerprint" {
  description = "Fingerprint for the API signing key."
  type        = string
}

variable "private_key_path" {
  description = "Path to the OCI API private key file."
  type        = string
}

variable "compartment_ocid" {
  description = "OCI compartment OCID where resources are created."
  type        = string
}

variable "region" {
  description = "OCI region identifier."
  type        = string
  default     = "eu-frankfurt-1"
}

variable "availability_domain" {
  description = "Availability domain name for compute resources (for example: kIdk:EU-FRANKFURT-1-AD-1)."
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key content for the compute instance."
  type        = string
}

variable "instance_shape" {
  description = "Compute instance shape."
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "OCPU count for flex shapes."
  type        = number
  default     = 1
}

variable "instance_memory_in_gbs" {
  description = "Memory in GB for flex shapes."
  type        = number
  default     = 6
}

variable "instance_display_name" {
  description = "Display name for the application compute instance."
  type        = string
  default     = "openmicodyssey-web"
}

variable "vcn_cidr" {
  description = "CIDR block for the VCN."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet."
  type        = string
  default     = "10.0.1.0/24"
}

variable "admin_cidr" {
  description = "CIDR range allowed to SSH to the instance."
  type        = string
  default     = "0.0.0.0/0"
}

variable "dns_zone_name" {
  description = "DNS zone name, including trailing dot."
  type        = string
  default     = "openmicodyssey.com."
}

variable "dns_record_name" {
  description = "DNS record label inside the zone (for example: @, www)."
  type        = string
  default     = "@"
}

variable "dns_record_ttl" {
  description = "TTL in seconds for the public A record."
  type        = number
  default     = 300
}

variable "tls_certificate_name" {
  description = "Display name for the load balancer TLS certificate resource."
  type        = string
  default     = "openmicodyssey-cert"
}

variable "lb_shape" {
  description = "OCI load balancer shape."
  type        = string
  default     = "flexible"
}

variable "lb_min_bandwidth_mbps" {
  description = "Minimum bandwidth in Mbps for a flexible load balancer shape."
  type        = number
  default     = 10
}

variable "lb_max_bandwidth_mbps" {
  description = "Maximum bandwidth in Mbps for a flexible load balancer shape."
  type        = number
  default     = 100
}

variable "tls_public_certificate_pem" {
  description = "PEM-encoded public certificate content for HTTPS listener."
  type        = string
  sensitive   = true
}

variable "tls_private_key_pem" {
  description = "PEM-encoded private key content for HTTPS listener certificate."
  type        = string
  sensitive   = true
}

variable "tls_ca_certificate_pem" {
  description = "Optional PEM-encoded CA chain for the HTTPS certificate."
  type        = string
  default     = ""
  sensitive   = true
}

variable "notification_email" {
  description = "Email address subscribed to OCI monitoring notifications."
  type        = string
  default     = ""
}

variable "notification_webhook_endpoint" {
  description = "Optional HTTPS webhook endpoint for OCI alarm notifications."
  type        = string
  default     = ""
}

variable "monitoring_topic_name" {
  description = "OCI Notifications topic name for deployment alarms."
  type        = string
  default     = "openmicodyssey-alerts"
}

variable "cpu_alarm_threshold" {
  description = "CPU utilization percentage threshold for alerting."
  type        = number
  default     = 80
}

variable "memory_alarm_threshold" {
  description = "Memory utilization percentage threshold for alerting."
  type        = number
  default     = 85
}

variable "backend_5xx_alarm_threshold" {
  description = "Threshold for backend 5xx responses per minute before alerting."
  type        = number
  default     = 5
}

variable "objectstorage_bucket_name" {
  description = "Bucket name for deployment artifacts and backup snapshots."
  type        = string
  default     = "openmicodyssey-artifacts"
}
