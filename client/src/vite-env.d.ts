/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_LOGGER: string;
  readonly VITE_LOGGER_FILTER: string;
  /** Report agent ADK base URL. In dev, omit to use proxy /report-agent-api → localhost:8000. In prod, set to Cloud Run URL. */
  readonly VITE_REPORT_AGENT_URL: string;
  // Add other env variables here
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
