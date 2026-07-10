# Phase 1 stub — no resources provisioned yet.
#
# Planned shape: RDS Postgres 16 (+pgvector) as the single datastore backing
# both the app and the Procrastinate job queue, ECS/Fargate for the API and
# workers, S3 for document/export storage, all in eu-west-2. Add resources
# here as each is actually needed — do not pre-build unused infrastructure.
