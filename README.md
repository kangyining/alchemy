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

Chat calls the report service through `REPORT_AGENT_URL`. Set `REPORT_AGENT_API_KEY` to match the report service `API_KEY`, and configure `REPORTS_BUCKET`. The proxy requires a logged-in user and derives user/session IDs on the server. AWS and Cloud Run remain independent deployments.
`doc_ingest` is outside this repository.

## History and deployment

Source authors and dates are retained; commit IDs were rewritten to remove runtime data. Source branches are
under `archive/librechat/`, `archive/alchemy-infra/`, and `archive/report-agents/`.
[sources.json](sources.json) records the imported snapshots and branch references.
Archived branches use their original directory layout; new work belongs on `main`.

Root CI checks the chat build, authenticated report gateway, offline report routes, and CDK templates. Original component workflows remain inactive inside their component directories. Live deployments are unchanged.

AWS scripts now target this repository at `/opt/alchemy/apps/librechat`. Before a
future deployment, provision its environment/configuration and ensure the existing
SSM GitHub token can read this private repository. Existing hosts require a planned
checkout/configuration migration. Component licenses and attribution are retained.

Offline checks: `python -m unittest discover -s services/report-agents/tests`;
from `apps/librechat`, run `npx jest --config packages/api/jest.config.mjs --rootDir packages/api --runInBand --coverage=false --testPathPatterns reports.spec.ts`.
Cached documents and saved sessions are excluded from shared history. Full original
Git backups are local. Existing email-based report storage needs an explicit
migration before deploying the new opaque user IDs.
