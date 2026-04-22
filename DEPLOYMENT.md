# Deployment Guide (OCI)

This document outlines a suggested build for deploying the Open Mic Odyssey Flask site on Oracle Cloud Infrastructure (OCI).

## Goals

- Deploy the contents of the `website/` folder as a standalone application.
- The GitHub Actions mirror workflow (`deploy-website-mirror.yml`) pushes `website/` to [`zwitschi/openmicodyssey-website`](https://github.com/zwitschi/openmicodyssey-website) on every push to `main`.
- In the deployed repository `app.py` sits at the root, so the WSGI entrypoint is `app:app`.
- Keep the stack simple for first launch and easy to scale later.
- Use managed OCI services for TLS, edge delivery, and observability.

## Target Architecture

```text
Users
  -> OCI CDN
  -> OCI Load Balancer (HTTPS/TLS)
  -> Nginx on OCI Compute instance(s)
  -> Gunicorn
  -> Flask app (website.app:app)

Supporting services:
- OCI DNS (domain records)
- OCI Object Storage (backups, artifacts, optional static/media offload)
- OCI Monitoring + Alarms
```

## Suggested OCI Services

- Compute: 1 Ubuntu VM (flex shape) for app runtime.
- Networking: VCN + public subnet + NSG.
- Load Balancer: public LB for TLS termination and health checks.
- CDN: OCI CDN in front of LB for cacheable static paths.
- Object Storage: backups, release artifacts, and optional media hosting.
- DNS: OCI DNS zone and records for `openmicodyssey.com`.

## Build Order

1. Create OCI compartment, VCN, subnet, route table, and NSG rules.
2. Provision Compute instance and attach SSH key.
3. Install runtime dependencies on VM:
   - Python
   - virtualenv
   - Nginx
   - app dependencies from `requirements.txt`
4. Deploy app code from [`zwitschi/openmicodyssey-website`](https://github.com/zwitschi/openmicodyssey-website) and configure Gunicorn service:
   - app entrypoint: `app:app` (`app.py` is at the repository root after mirroring)
   - run under `systemd` with restart policy
5. Configure Nginx reverse proxy to Gunicorn on localhost.
6. Provision OCI Load Balancer:
   - backend set to Compute instance(s)
   - health checks on app endpoint
   - HTTPS listener and managed certificate
7. Enable OCI CDN and set caching behavior for static assets.
8. Configure DNS records to point domain to CDN/LB.
9. Add monitoring alarms (CPU, memory, unhealthy backend, 5xx rate).
10. Configure backup flow to Object Storage (nightly snapshots/artifacts).

## Security Baseline

- Allow inbound:
  - `80/443` from internet
  - `22` only from admin IP allowlist
- Enforce HTTPS redirect at LB or Nginx.
- Store secrets in OCI Vault or CI/CD secret store, not in repo.
- Use least-privilege OCI IAM policies for deployment user/service.
- Keep OS packages and Python dependencies patched.
- Enable host-level firewall and SSH hardening.

## Reliability and Scaling

- Start with one VM for launch simplicity.
- Keep app stateless to support horizontal scaling.
- Scale path:
  - add second Compute instance behind LB
  - tune Gunicorn workers by CPU/memory metrics
  - offload heavy static/media content to Object Storage + CDN

## Deployment Checklist

Pre-deploy:

- Confirm environment variables for production are set.
- Confirm `requirements.txt` is up to date.
- Confirm domain and TLS certificate ownership/validation.

Staging validation:

- `/` loads and trailer renders.
- `/film`, `/gallery`, `/support`, `/patreon` return HTTP 200.
- static assets resolve from `/static`.
- JSON-LD script is present in rendered page output.

Production cutover:

- Point DNS to production endpoint.
- Verify HTTPS and redirect behavior.
- Run smoke tests on all primary routes.
- Confirm alarms are active and notifying the team.

Rollback:

- Keep previous artifact/version available.
- Repoint deployment to prior known-good release if smoke tests fail.

## Runtime Commands

Linux production start command (run from the mirrored repository root):

```bash
gunicorn app:app --bind 0.0.0.0:8000
```

Local development (from this source repository root):

```powershell
# Windows — gunicorn does not run natively; use Flask dev server
.venv\Scripts\python.exe -m flask --app website.app run --debug
```

Note: in the source repository the entrypoint is `website.app:app` because `app.py` lives under `website/`. After the mirror workflow runs, `app.py` is at the destination repo root so the production entrypoint becomes `app:app`.

## Delivery — Mirror Workflow

The GitHub Actions workflow at `.github/workflows/deploy-website-mirror.yml` handles content delivery:

- Triggers on pushes to `main` that touch `website/**`, `requirements.txt`, or the workflow file.
- Stages a clean bundle from `website/` with caches removed.
- Copies `requirements.txt` and `website/README.md` into the bundle root.
- Rewrites entrypoint references in the README (`website.app:app` → `app:app`).
- Diffs the bundle against the destination and skips the commit if nothing changed.
- Pushes to [`zwitschi/openmicodyssey-website`](https://github.com/zwitschi/openmicodyssey-website).

Required GitHub configuration in this source repository:

| Type     | Name                    | Value                                              |
| -------- | ----------------------- | -------------------------------------------------- |
| Secret   | `WEBSITE_DEPLOY_TOKEN`  | GitHub token with push access to destination repo  |
| Variable | `WEBSITE_DEPLOY_BRANCH` | destination branch (defaults to `main` if omitted) |

## Terraform Workflow

Use Terraform from the `infra/` directory to create and update OCI resources.

### 1) Prepare variable file

- Copy `infra/terraform.tfvars.example` to `infra/terraform.tfvars`.
- Replace all placeholder values with real OCI IDs, SSH key, and TLS certificate/key data.
- Do not commit `infra/terraform.tfvars`.

### 2) Initialize Terraform

```bash
cd infra
terraform init
```

### 3) Validate and review plan

```bash
terraform validate
terraform plan -out=tfplan
```

### 4) Apply changes

```bash
terraform apply tfplan
```

### 5) Check outputs

```bash
terraform output
```

Expected key outputs include:

- compute `public_ip`
- load balancer `load_balancer_hostname`
- `dns_record_fqdn`

### 6) Update or destroy workflow

For normal updates:

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

For teardown (non-production only):

```bash
terraform destroy
```

### 7) Recommended execution order

1. Run the GitHub mirror workflow so `zwitschi/openmicodyssey-website` is current.
2. Run Terraform `plan` and `apply` in this repository's `infra/` directory.
3. Verify DNS, HTTPS, and route health checks.
4. Run smoke tests for `/`, `/film`, `/gallery`, `/support`, and `/patreon`.

## Future Enhancements

- Add WAF policy in front of CDN/LB if threat profile increases.
- Add blue/green deployment flow for safer releases.
- Add synthetic uptime checks for main routes.
- Add Terraform-driven OCI provisioning (see `infra/` once scaffolded).
