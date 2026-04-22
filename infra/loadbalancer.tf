resource "oci_load_balancer_load_balancer" "web" {
  compartment_id = var.compartment_ocid
  display_name   = "openmicodyssey-lb"
  shape          = var.lb_shape
  subnet_ids     = [oci_core_subnet.public.id]

  shape_details {
    minimum_bandwidth_in_mbps = var.lb_min_bandwidth_mbps
    maximum_bandwidth_in_mbps = var.lb_max_bandwidth_mbps
  }
}

resource "oci_load_balancer_backend_set" "web" {
  load_balancer_id = oci_load_balancer_load_balancer.web.id
  name             = "web-backend-set"
  policy           = "ROUND_ROBIN"

  health_checker {
    protocol          = "HTTP"
    port              = 80
    retries           = 3
    timeout_in_millis = 3000
    return_code       = 200
    url_path          = "/"
  }
}

resource "oci_load_balancer_backend" "web" {
  load_balancer_id = oci_load_balancer_load_balancer.web.id
  backendset_name  = oci_load_balancer_backend_set.web.name
  ip_address       = oci_core_instance.web.private_ip
  port             = 80
  weight           = 1
}

resource "oci_load_balancer_certificate" "https" {
  load_balancer_id   = oci_load_balancer_load_balancer.web.id
  certificate_name   = var.tls_certificate_name
  public_certificate = var.tls_public_certificate_pem
  private_key        = var.tls_private_key_pem

  ca_certificate = var.tls_ca_certificate_pem != "" ? var.tls_ca_certificate_pem : null
}

resource "oci_load_balancer_listener" "https" {
  load_balancer_id         = oci_load_balancer_load_balancer.web.id
  name                     = "https-listener"
  default_backend_set_name = oci_load_balancer_backend_set.web.name
  port                     = 443
  protocol                 = "HTTP"

  ssl_configuration {
    certificate_name        = oci_load_balancer_certificate.https.certificate_name
    verify_peer_certificate = false
  }
}

resource "oci_load_balancer_rule_set" "http_to_https" {
  load_balancer_id = oci_load_balancer_load_balancer.web.id
  name             = "http-to-https"

  items {
    action        = "REDIRECT"
    response_code = 301

    redirect_uri {
      protocol = "HTTPS"
      port     = 443
      host     = "{host}"
      path     = "/{path}"
      query    = "{query}"
    }
  }
}

resource "oci_load_balancer_listener" "http" {
  load_balancer_id         = oci_load_balancer_load_balancer.web.id
  name                     = "http-listener"
  default_backend_set_name = oci_load_balancer_backend_set.web.name
  port                     = 80
  protocol                 = "HTTP"
  rule_set_names           = [oci_load_balancer_rule_set.http_to_https.name]
}
