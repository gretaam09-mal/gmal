# Infra

- `aws/` — Terraform stubs for AWS `eu-west-2` (UK hosting requirement). No
  resources are provisioned yet; see `aws/main.tf`.
- `ci/` — scripts invoked by GitHub Actions. The workflow definitions
  themselves live at the repository root in `.github/workflows/`, which is
  the only path GitHub Actions reads.
