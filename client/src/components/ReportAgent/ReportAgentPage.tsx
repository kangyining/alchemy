import { useState, useCallback, useRef } from 'react';

const APP_NAME = 'report_agents';
const USER_ID = 'web-user';

/** Base URL for report agent ADK. Local dev: use proxy /report-agent-api → localhost:8000. Prod: set VITE_REPORT_AGENT_URL to Cloud Run URL. */
function getReportAgentBaseUrl(): string {
  const env = import.meta.env.VITE_REPORT_AGENT_URL;
  if (env && typeof env === 'string' && env.trim() !== '') {
    return env.trim().replace(/\/$/, '');
  }
  if (import.meta.env.DEV) {
    return ''; // same origin → Vite proxy /report-agent-api
  }
  return '';
}

/** In dev we use a path prefix so Vite proxies to localhost:8000. */
function getReportAgentApiBase(): string {
  const base = getReportAgentBaseUrl();
  if (base) {
    return base;
  }
  return '/report-agent-api';
}

type Step = {
  author: string;
  label: string;
  summary: string;
  truncated?: boolean;
  isThrottle?: boolean;
};

type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

const SUMMARY_MAX = 180;

function truncateText(text: string, max = SUMMARY_MAX): { text: string; truncated: boolean } {
  if (text.length <= max) {
    return { text, truncated: false };
  }
  return { text: text.slice(0, max), truncated: true };
}

function summarizeStateDelta(state: unknown): string {
  if (!state) return '';
  if (typeof state === 'string') return state;
  if (typeof state !== 'object') return String(state);
  const obj = state as Record<string, unknown>;
  const preferredKeys = ['status', 'step', 'phase', 'message', 'detail', 'progress', 'current', 'label'];
  const parts: string[] = [];
  for (const key of preferredKeys) {
    const value = obj[key];
    if (value == null) continue;
    if (typeof value === 'string') {
      if (value.trim() === '') continue;
      parts.push(value);
    } else if (typeof value === 'number' || typeof value === 'boolean') {
      parts.push(`${key}: ${String(value)}`);
    }
  }
  if (parts.length > 0) {
    return parts.join(' · ');
  }
  try {
    return JSON.stringify(obj);
  } catch {
    return '';
  }
}

function extractEventSummary(event: {
  content?: { parts?: Array<{ text?: string }> };
  actions?: { stateDelta?: Record<string, unknown> };
}): { summary: string; truncated: boolean } {
  const textParts = event.content?.parts?.map((p) => p.text).filter(Boolean) as string[] | undefined;
  if (textParts && textParts.length > 0) {
    return truncateText(textParts.join(' '));
  }
  const stateSummary = summarizeStateDelta(event.actions?.stateDelta);
  if (stateSummary) {
    return truncateText(stateSummary);
  }
  return { summary: '', truncated: false };
}

function getInlineData(part: unknown): { data?: string; mimeType?: string } | undefined {
  if (!part || typeof part !== 'object') return undefined;
  const obj = part as Record<string, unknown>;
  const inline =
    (obj.inlineData as Record<string, unknown> | undefined) ??
    (obj.inline_data as Record<string, unknown> | undefined);
  if (!inline || typeof inline !== 'object') return undefined;
  const data = inline.data as string | undefined;
  const mimeType = (inline.mimeType as string | undefined) ?? (inline.mime_type as string | undefined);
  return { data, mimeType };
}

function formatBase64Data(data: string, mimeType: string): string {
  return `data:${mimeType};base64,${data}`;
}

function normalizeBase64(data: string): string {
  const trimmed = data.trim();
  let base64 = trimmed;
  if (base64.startsWith('data:') && base64.includes(',')) {
    base64 = base64.split(',')[1] ?? '';
  }
  base64 = base64.replace(/\s/g, '').replace(/-/g, '+').replace(/_/g, '/');
  const pad = base64.length % 4;
  if (pad === 2) base64 += '==';
  else if (pad === 3) base64 += '=';
  return base64;
}

function base64ToBlob(base64: string, mimeType: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType || 'application/octet-stream' });
}

function inferMimeTypeFromFilename(filename: string): string {
  if (filename.endsWith('.pdf')) return 'application/pdf';
  if (filename.endsWith('.pptx')) {
    return 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
  }
  return 'application/octet-stream';
}

function coerceVersion(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getAuthorMeta(author: string): { label: string; isThrottle: boolean; slideNumber?: number } {
  if (!author) return { label: 'Unknown', isThrottle: false };
  if (author === 'IngestionAgent') return { label: 'Parsing Documents', isThrottle: false };
  if (author === 'ReportAssemblyAgent') return { label: 'Assembling Report', isThrottle: false };
  if (author.startsWith('Throttle_') || author.startsWith('Throttle')) {
    return { label: 'Waiting', isThrottle: true };
  }
  // ADK format: SlideAgent_{slide_number:02d}_{safe_title} (safe_title may use underscores for spaces)
  const slideMatch = author.match(/^SlideAgent_(\d+)_?(.*)$/);
  if (slideMatch?.[1]) {
    const num = Number.parseInt(slideMatch[1], 10);
    if (!Number.isFinite(num)) return { label: author, isThrottle: false };
    const safeTitle = slideMatch[2]?.trim().replace(/_/g, ' ');
    const label = safeTitle ? `Slide ${num}: ${safeTitle}` : `Slide ${num}`;
    return { label, isThrottle: false, slideNumber: num };
  }
  return { label: author, isThrottle: false };
}

function extractProgressFromStateDelta(state?: Record<string, unknown>): { current?: number; total?: number } {
  if (!state) return {};
  const totals = ['total_slides', 'slides_total', 'slide_total', 'slide_count', 'num_slides', 'slides'];
  const currents = ['slides_generated', 'slide', 'slide_index', 'current_slide', 'current'];
  const pickNumber = (keys: string[]) => {
    for (const key of keys) {
      const value = state[key];
      if (typeof value === 'number' && Number.isFinite(value)) return value;
      if (typeof value === 'string') {
        const parsed = Number.parseInt(value, 10);
        if (Number.isFinite(parsed)) return parsed;
      }
    }
    return undefined;
  };
  const total = pickNumber(totals);
  let current = pickNumber(currents);
  const assemblyResult = state['assembly_result'];
  if (typeof assemblyResult === 'string') {
    try {
      const parsed = JSON.parse(assemblyResult) as Record<string, unknown>;
      const generated = parsed['slides_generated'];
      if (typeof generated === 'number' && Number.isFinite(generated)) {
        current = current ?? generated;
      }
      const totalFromAssembly = parsed['slides_total'];
      if (typeof totalFromAssembly === 'number' && Number.isFinite(totalFromAssembly)) {
        return { current, total: totalFromAssembly };
      }
    } catch {
      // ignore parse errors
    }
  }
  return { current, total };
}

export default function ReportAgentPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [artifacts, setArtifacts] = useState<{ pptxVersion?: number; pdfVersion?: number }>({});
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('idle');
  const [streamWarning, setStreamWarning] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<{ label: string; summary?: string } | null>(null);
  const [progress, setProgress] = useState<{ current?: number; total?: number }>({});
  const [downloading, setDownloading] = useState<{ pptx: boolean; pdf: boolean }>({
    pptx: false,
    pdf: false,
  });
  const pendingStepsRef = useRef<Step[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasStreamedRef = useRef(false);

  const apiBase = getReportAgentApiBase();
  const visibleSteps = steps.filter((step) => !step.isThrottle);
  const progressPercent =
    progress.total && progress.current
      ? Math.min(100, Math.max(0, (progress.current / progress.total) * 100))
      : null;

  const readFileAsBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        const base64 = result.includes(',') ? result.split(',')[1] : result;
        resolve(base64 ?? '');
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

  const getMimeType = (file: File): string => {
    const map: Record<string, string> = {
      'application/pdf': 'application/pdf',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/csv': 'text/csv',
    };
    return map[file.type] || file.type || 'application/octet-stream';
  };

  const flushPendingSteps = useCallback(() => {
    if (pendingStepsRef.current.length === 0) {
      return;
    }
    setSteps((prev) => [...prev, ...pendingStepsRef.current]);
    pendingStepsRef.current = [];
  }, []);

  const enqueueStep = useCallback(
    (step: Step) => {
      pendingStepsRef.current.push(step);
      if (flushTimerRef.current == null) {
        flushTimerRef.current = setTimeout(() => {
          flushTimerRef.current = null;
          flushPendingSteps();
        }, 300);
      }
    },
    [flushPendingSteps],
  );

  const downloadArtifact = useCallback(
    async (artifactName: string, version: number, filename: string, key: 'pptx' | 'pdf') => {
      if (!sessionId) {
        setError('No session ID found for download.');
        return;
      }
      setDownloading((prev) => ({ ...prev, [key]: true }));
      try {
        const res = await fetch(
          `${apiBase}/apps/${APP_NAME}/users/${USER_ID}/sessions/${sessionId}/artifacts/${artifactName}/versions/${version}`,
        );
        if (!res.ok) {
          const text = await res.text();
          throw new Error(`Artifact fetch failed: ${res.status} ${text}`);
        }
        const json = (await res.json()) as Record<string, unknown>;
        const inline = getInlineData(json);
        if (!inline?.data) {
          throw new Error('Artifact missing inlineData.');
        }
        const mimeType = inline.mimeType || inferMimeTypeFromFilename(filename);
        const base64 = normalizeBase64(inline.data);
        if (!base64) {
          throw new Error('Artifact data was empty.');
        }
        let url: string | null = null;
        try {
          const blob = base64ToBlob(base64, mimeType);
          url = URL.createObjectURL(blob);
        } catch {
          url = formatBase64Data(base64, mimeType);
        }
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        if (url?.startsWith('blob:')) {
          setTimeout(() => URL.revokeObjectURL(url as string), 1000);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setDownloading((prev) => ({ ...prev, [key]: false }));
      }
    },
    [apiBase, sessionId],
  );

  const runReport = useCallback(async () => {
    if (files.length === 0) {
      setError('Please select at least one file.');
      return;
    }
    setError(null);
    setSteps([]);
    setArtifacts({});
    setStreamWarning(null);
    setCurrentStep(null);
    setProgress({});
    pendingStepsRef.current = [];
    if (flushTimerRef.current) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    setStreamStatus('connecting');
    setRunning(true);
    hasStreamedRef.current = false;
    const sid = crypto.randomUUID();
    setSessionId(sid);

    try {
      let sawArtifacts = false;
      const sessionRes = await fetch(
        `${apiBase}/apps/${APP_NAME}/users/${USER_ID}/sessions/${sid}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        },
      );
      if (!sessionRes.ok) {
        const text = await sessionRes.text();
        throw new Error(`Session create failed: ${sessionRes.status} ${text}`);
      }

      const fileParts = await Promise.all(
        files.map(async (file) => ({
          inlineData: {
            mimeType: getMimeType(file),
            data: await readFileAsBase64(file),
            displayName: file.name,
          },
        })),
      );

      const runBody = {
        appName: APP_NAME,
        userId: USER_ID,
        sessionId: sid,
        newMessage: {
          role: 'user',
          parts: [
            { text: 'Generate the financial report from the uploaded documents.' },
            ...fileParts,
          ],
        },
        streaming: true,
      };

      const runRes = await fetch(`${apiBase}/run_sse`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(runBody),
      });
      if (!runRes.ok) {
        const text = await runRes.text();
        throw new Error(`Run failed: ${runRes.status} ${text}`);
      }

      const reader = runRes.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        while (true) {
          const match = buffer.match(/\r?\n\r?\n/);
          if (!match || match.index == null) break;
          const eventChunk = buffer.slice(0, match.index);
          buffer = buffer.slice(match.index + match[0].length);
          const dataLines = eventChunk
            .split(/\r?\n/)
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trimStart());
          if (dataLines.length === 0) continue;
          const data = dataLines.join('\n').trim();
          if (!data || data === '[DONE]') continue;
          try {
            const event = JSON.parse(data) as {
              author?: string;
              content?: { parts?: Array<{ text?: string }> };
              actions?: {
                artifactDelta?: Record<string, unknown>;
                artifact_delta?: Record<string, unknown>;
                stateDelta?: Record<string, unknown>;
                state_delta?: Record<string, unknown>;
              };
            };
            if (!hasStreamedRef.current) {
              hasStreamedRef.current = true;
              setStreamStatus('streaming');
            }
            const author = event.author ?? 'unknown';
            const authorMeta = getAuthorMeta(author);
            const actions = event.actions ?? {};
            const stateDelta = actions.stateDelta ?? actions.state_delta;
            const normalizedEvent = {
              content: event.content,
              actions: {
                stateDelta,
              },
            };
            const { summary, truncated } = extractEventSummary(normalizedEvent);
            if (summary || author) {
              enqueueStep({
                author,
                label: authorMeta.label,
                summary,
                truncated,
                isThrottle: authorMeta.isThrottle,
              });
              if (!authorMeta.isThrottle) {
                setCurrentStep({ label: authorMeta.label, summary: summary || undefined });
              }
            }
            const progressUpdate = extractProgressFromStateDelta(stateDelta);
            if (progressUpdate.current || progressUpdate.total || authorMeta.slideNumber) {
              setProgress((prev) => {
                const nextCurrent = Math.max(
                  prev.current ?? 0,
                  progressUpdate.current ?? 0,
                  authorMeta.slideNumber ?? 0,
                );
                const nextTotal = progressUpdate.total ?? prev.total;
                return {
                  current: nextCurrent > 0 ? nextCurrent : prev.current,
                  total: nextTotal,
                };
              });
            }
            const delta =
              (actions.artifactDelta as Record<string, unknown> | undefined) ??
              (actions.artifact_delta as Record<string, unknown> | undefined);
            if (delta) {
              const pptxVersion = coerceVersion(delta['financial_report.pptx']);
              const pdfVersion = coerceVersion(delta['financial_report.pdf']);
              if (pptxVersion != null || pdfVersion != null) {
                sawArtifacts = true;
                setArtifacts((prev) => ({
                  ...prev,
                  ...(pptxVersion != null ? { pptxVersion } : {}),
                  ...(pdfVersion != null ? { pdfVersion } : {}),
                }));
              }
            }
          } catch {
            // ignore parse errors for non-JSON lines
          }
        }
      }
      flushPendingSteps();
      setStreamStatus((prev) => (prev === 'error' ? prev : 'done'));
      if (!sawArtifacts && hasStreamedRef.current) {
        setStreamWarning('Stream ended without artifacts. The run may have failed or the backend did not save outputs.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStreamStatus('error');
      flushPendingSteps();
    } finally {
      setRunning(false);
    }
  }, [files, apiBase, enqueueStep, flushPendingSteps]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files ? Array.from(e.target.files) : [];
    setFiles(list);
    setError(null);
  }, []);

  return (
    <div className="flex h-full flex-col overflow-auto p-4 md:p-6">
      <div className="mx-auto w-full max-w-2xl space-y-6">
        <h1 className="text-3xl font-semibold text-gray-900 dark:text-gray-100">
          Financial Report Generation
        </h1>
        <p className="text-base text-gray-600 dark:text-gray-400">
          Please upload all required documents for the financial report (supported formats: PDF, DOCX, XLSX, CSV). 
          The final report will be generated in PDF format.
        </p>

        <div className="flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <label className="block text-base font-medium text-gray-700 dark:text-gray-300">
            Files
          </label>
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.xlsx,.csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/csv"
            onChange={handleFileChange}
            disabled={running}
            className="block w-full text-base text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-gray-100 file:px-4 file:py-2 file:text-base file:font-medium file:text-gray-700 hover:file:bg-gray-200 dark:file:bg-gray-700 dark:file:text-gray-300"
          />
          {files.length > 0 && (
            <p className="text-base text-gray-600 dark:text-gray-400">
              {files.length} file(s) selected: {files.map((f) => f.name).join(', ')}
            </p>
          )}
          <button
            type="button"
            onClick={runReport}
            disabled={running}
            title={files.length === 0 ? 'Select at least one file first' : undefined}
            className="rounded-md bg-[#A89968] px-4 py-2 text-base font-medium text-white hover:bg-[#958b5e] disabled:opacity-50 dark:bg-[#A89968] dark:hover:bg-[#958b5e]"
          >
            {running ? 'Running…' : 'Generate report'}
          </button>
          {streamStatus !== 'idle' && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Stream status: {streamStatus}
            </p>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-base text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </div>
        )}
        {streamWarning && !error && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-base text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
            {streamWarning}
          </div>
        )}
        {error && !running && files.length > 0 && (
          <button
            type="button"
            onClick={runReport}
            className="w-fit rounded-md bg-gray-900 px-4 py-2 text-base font-medium text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-200"
          >
            Retry
          </button>
        )}

        {(running || streamStatus !== 'idle' || steps.length > 0) && (
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h2 className="mb-3 text-base font-medium text-gray-700 dark:text-gray-300">Steps</h2>
            <div className="mb-4 space-y-1 text-base text-gray-600 dark:text-gray-400">
              <div className="flex items-center justify-between">
                <span>
                  Current:{' '}
                  <span className="font-medium text-gray-800 dark:text-gray-200">
                    {currentStep?.label ?? (running ? 'Waiting for first event…' : '—')}
                  </span>
                </span>
                {progress.total ? (
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {progress.current ?? 0} / {progress.total} slides
                  </span>
                ) : progress.current ? (
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    Slide {progress.current}
                  </span>
                ) : null}
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                {progressPercent != null ? (
                  <div
                    className="h-full rounded-full bg-[#A89968] transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                ) : running ? (
                  <div className="h-full w-full animate-pulse rounded-full bg-[#A89968]/60" />
                ) : null}
              </div>
            {currentStep?.summary && (
              <p className="text-sm text-gray-500 dark:text-gray-400">{currentStep.summary}</p>
            )}
            </div>
            {visibleSteps.length > 0 && (
              <ul className="space-y-2">
                {visibleSteps.map((s, i) => (
                  <li key={i} className="text-base text-gray-600 dark:text-gray-400">
                    <span className="font-medium text-gray-800 dark:text-gray-200">{s.label}</span>
                    {s.summary ? ` — ${s.summary}${s.truncated ? '…' : ''}` : ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {artifacts.pdfVersion != null && sessionId && (
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h2 className="mb-3 text-base font-medium text-gray-700 dark:text-gray-300">Download Report</h2>
            <div className="flex gap-4">
              {artifacts.pdfVersion != null && (
                <button
                  type="button"
                  onClick={() =>
                    downloadArtifact(
                      'financial_report.pdf',
                      artifacts.pdfVersion as number,
                      'financial_report.pdf',
                      'pdf',
                    )
                  }
                  disabled={downloading.pdf}
                  className="rounded-md bg-[#A89968] px-4 py-2 text-base font-medium text-white hover:bg-[#958b5e] disabled:opacity-50 dark:bg-[#A89968] dark:hover:bg-[#958b5e]"
                >
                  {downloading.pdf ? 'Downloading…' : 'Download PDF'}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
