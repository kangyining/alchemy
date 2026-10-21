/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_LOGGER: string;
  readonly VITE_LOGGER_FILTER: string;
  /** Report agent ADK base URL. Omit to use same-origin /report-agent-api (server proxies to REPORT_AGENT_URL). */
  readonly VITE_REPORT_AGENT_URL: string;
  // Add other env variables here
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
