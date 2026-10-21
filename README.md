# Alchemy

Chat, financial report generation, and AWS infrastructure in one private repository.

| Component | Location | Purpose |
| --- | --- | --- |
| LibreChat | [apps/librechat](apps/librechat) | Chat UI and streaming report proxy |
| Report agents | [services/report-agents](services/report-agents) | Google ADK workflow producing PDF/PPTX reports |
| AWS infrastructure | [infra/aws](infra/aws) | CDK definitions for the chat host |

## Development

Run commands from the component directory; each keeps its own lockfile and build context.

- Chat: `cd apps/librechat`, then `npm ci` and `npm run build`.
- Reports: `cd services/report-agents`, then `uv sync`. See its Dockerfile for the production runtime.
- Infrastructure: `cd infra/aws`, then `npm ci` and `npm run build`.

Chat calls the report service through `REPORT_AGENT_URL`; configure credentials and
environment files separately. AWS and Cloud Run remain independent deployments.
`doc_ingest` is outside this repository.

## History and deployment

All original commits retain their IDs, authors, and dates. Original branches are
under `archive/librechat/`, `archive/alchemy-infra/`, and `archive/report-agents/`.
[sources.json](sources.json) records the imported snapshots and branch references.
Archived branches use their original directory layout; new work belongs on `main`.

GitHub Actions is disabled for this import. Original workflow files remain with
their components; add selected workflows at the repository root before enabling
automation. The migration does not change live services.

AWS scripts now target this repository at `/opt/alchemy/apps/librechat`. Before a
future deployment, provision its environment/configuration and ensure the existing
SSM GitHub token can read this private repository. Existing hosts require a planned
checkout/configuration migration. Component licenses and attribution are retained.
