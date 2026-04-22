resource "oci_ons_notification_topic" "alerts" {
  compartment_id = var.compartment_ocid
  name           = var.monitoring_topic_name
  description    = "Alert topic for Open Mic Odyssey infrastructure alarms"
}

resource "oci_ons_subscription" "email" {
  count          = trimspace(var.notification_email) != "" ? 1 : 0
  compartment_id = var.compartment_ocid
  topic_id       = oci_ons_notification_topic.alerts.id
  protocol       = "EMAIL"
  endpoint       = var.notification_email
}

resource "oci_ons_subscription" "webhook" {
  count          = trimspace(var.notification_webhook_endpoint) != "" ? 1 : 0
  compartment_id = var.compartment_ocid
  topic_id       = oci_ons_notification_topic.alerts.id
  protocol       = "HTTPS"
  endpoint       = var.notification_webhook_endpoint
}

resource "oci_monitoring_alarm" "cpu_high" {
  compartment_id       = var.compartment_ocid
  display_name         = "openmicodyssey-cpu-high"
  metric_compartment_id = var.compartment_ocid
  namespace            = "oci_computeagent"
  query                = "CpuUtilization[1m]{resourceId = \"${oci_core_instance.web.id}\"}.mean() > ${var.cpu_alarm_threshold}"
  severity             = "CRITICAL"
  is_enabled           = true
  pending_duration     = "PT5M"
  destinations         = [oci_ons_notification_topic.alerts.id]
  body                 = "Compute CPU utilization is above threshold for 5 minutes."
}

resource "oci_monitoring_alarm" "memory_high" {
  compartment_id       = var.compartment_ocid
  display_name         = "openmicodyssey-memory-high"
  metric_compartment_id = var.compartment_ocid
  namespace            = "oci_computeagent"
  query                = "MemoryUtilization[1m]{resourceId = \"${oci_core_instance.web.id}\"}.mean() > ${var.memory_alarm_threshold}"
  severity             = "CRITICAL"
  is_enabled           = true
  pending_duration     = "PT5M"
  destinations         = [oci_ons_notification_topic.alerts.id]
  body                 = "Compute memory utilization is above threshold for 5 minutes."
}

resource "oci_monitoring_alarm" "lb_unhealthy_backends" {
  compartment_id       = var.compartment_ocid
  display_name         = "openmicodyssey-lb-unhealthy-backends"
  metric_compartment_id = var.compartment_ocid
  namespace            = "oci_lbaas"
  query                = "UnhealthyBackendServers[1m]{resourceId = \"${oci_load_balancer_load_balancer.web.id}\", backendSetName = \"${oci_load_balancer_backend_set.web.name}\"}.mean() > 0"
  severity             = "CRITICAL"
  is_enabled           = true
  pending_duration     = "PT2M"
  destinations         = [oci_ons_notification_topic.alerts.id]
  body                 = "One or more load balancer backend servers are unhealthy."
}

resource "oci_monitoring_alarm" "lb_backend_5xx" {
  compartment_id       = var.compartment_ocid
  display_name         = "openmicodyssey-lb-backend-5xx"
  metric_compartment_id = var.compartment_ocid
  namespace            = "oci_lbaas"
  query                = "HttpCode_Backend_5xx_Count[1m]{resourceId = \"${oci_load_balancer_load_balancer.web.id}\"}.sum() > ${var.backend_5xx_alarm_threshold}"
  severity             = "ERROR"
  is_enabled           = true
  pending_duration     = "PT2M"
  destinations         = [oci_ons_notification_topic.alerts.id]
  body                 = "Backend 5xx responses are above the configured threshold."
}
