import { useState, useCallback, useRef, useEffect } from 'react';
import { useAuthContext, useLocalize } from '~/hooks';

const APP_NAME = 'report_agents';

type Step = {
  author: string;
  label: string;
  summary: string;
  truncated?: boolean;
  isThrottle?: boolean;
};

type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

type HistoryReport = {
  run_id: string;
  status: 'in_progress' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  pdf_filename?: string;
  error?: string;
  title?: string;
  message?: string;
};

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
  const preferredKeys = [
    'status',
    'step',
    'phase',
    'message',
    'detail',
    'progress',
    'current',
    'label',
  ];
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
  const textParts = event.content?.parts?.map((p) => p.text).filter(Boolean) as
    | string[]
    | undefined;
  if (textParts && textParts.length > 0) {
    const { text, truncated } = truncateText(textParts.join(' '));
    return { summary: text, truncated };
  }
  const stateSummary = summarizeStateDelta(event.actions?.stateDelta);
  if (stateSummary) {
    const { text, truncated } = truncateText(stateSummary);
    return { summary: text, truncated };
  }
  return { summary: '', truncated: false };
}

function coerceVersion(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getAuthorMeta(author: string): {
  label: string;
  isThrottle: boolean;
  slideNumber?: number;
} {
  if (!author) return { label: 'Unknown', isThrottle: false };
  if (author === 'IngestionAgent') return { label: 'Parsing Documents', isThrottle: false };
  if (author === 'ReportAssemblyAgent') return { label: 'Assembling Report', isThrottle: false };
  if (author.startsWith('Throttle_') || author.startsWith('Throttle')) {
    return { label: 'Waiting', isThrottle: true };
  }
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

function extractProgressFromStateDelta(state?: Record<string, unknown>): {
  current?: number;
  total?: number;
} {
  if (!state) return {};
  const totals = [
    'total_slides',
    'slides_total',
    'slide_total',
    'slide_count',
    'num_slides',
    'slides',
  ];
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

function formatReportDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function ReportAgentPage() {
  const localize = useLocalize();
  const { token } = useAuthContext();
  const userId = 'me';
  const encodedUserId = 'me';
  const reportFetch = useCallback(
    (url: string, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      headers.set('Authorization', `Bearer ${token ?? ''}`);
      return fetch(url, { ...init, headers });
    },
    [token],
  );
  const downloadReport = async (url: string, filename: string) => {
    try {
      const response = await reportFetch(url);
      if (!response.ok) throw new Error(response.statusText);
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (error) {
      setError(error instanceof Error ? error.message : String(error));
    }
  };
  const [files, setFiles] = useState<File[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('idle');
  const [streamWarning, setStreamWarning] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<{ label: string; summary?: string } | null>(null);
  const [progress, setProgress] = useState<{ current?: number; total?: number }>({});
  const [history, setHistory] = useState<HistoryReport[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const pendingStepsRef = useRef<Step[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasStreamedRef = useRef(false);

  // Warn user before leaving while report is generating
  useEffect(() => {
    if (!running) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [running]);

  const apiBase = '/report-agent-api';
  const visibleSteps = steps.filter((step) => !step.isThrottle);
  const progressPercent =
    progress.total && progress.current
      ? Math.min(100, Math.max(0, (progress.current / progress.total) * 100))
      : null;

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await reportFetch(`${apiBase}/reports/${encodedUserId}`);
      if (res.ok) {
        const data = (await res.json()) as HistoryReport[];
        setHistory(data);
      }
    } catch {
      // ignore — history is best-effort
    } finally {
      setHistoryLoading(false);
    }
  }, [apiBase, encodedUserId, reportFetch]);

  // Load history on mount
  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Refresh history when a run completes
  useEffect(() => {
    if (streamStatus === 'done') {
      fetchHistory();
    }
  }, [streamStatus, fetchHistory]);

  // Poll every 5s while any history entry is in_progress
  useEffect(() => {
    const hasInProgress = history.some((r) => r.status === 'in_progress');
    if (!hasInProgress) return;
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, [history, fetchHistory]);

  // Auto-poll every 5s while any run is in_progress
  useEffect(() => {
    const hasInProgress = history.some((r) => r.status === 'in_progress');
    if (!hasInProgress) return;
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, [history, fetchHistory]);

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
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
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

  const runReport = useCallback(async () => {
    if (files.length === 0) {
      setError('Please select at least one file.');
      return;
    }
    setError(null);
    setSteps([]);
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

    try {
      let sawArtifacts = false;
      const sessionRes = await reportFetch(
        `${apiBase}/apps/${APP_NAME}/users/${encodedUserId}/sessions/${sid}`,
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
        userId: userId,
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

      const runRes = await reportFetch(`${apiBase}/run_sse`, {
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
              actions: { stateDelta },
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
        setStreamWarning(
          'Stream ended without artifacts. The run may have failed or the backend did not save outputs.',
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStreamStatus('error');
      flushPendingSteps();
    } finally {
      setRunning(false);
    }
  }, [files, apiBase, encodedUserId, enqueueStep, flushPendingSteps, userId, reportFetch]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = e.target.files ? Array.from(e.target.files) : [];
    if (newFiles.length === 0) return;
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const unique = newFiles.filter((f) => !existingNames.has(f.name));
      return [...prev, ...unique];
    });
    setError(null);
    e.target.value = '';
  }, []);

  const removeFile = useCallback((name: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  }, []);

  return (
    <div className="flex h-full flex-col overflow-auto bg-gradient-to-b from-gray-50 to-white p-6 dark:from-gray-900 dark:to-gray-950 md:p-10">
      <div className="mx-auto w-full max-w-2xl space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#A89968]/10 dark:bg-[#A89968]/20">
              <svg
                className="h-5 w-5 text-[#A89968]"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                />
              </svg>
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-50">
              {localize('com_ui_report_financial_report_generation')}
            </h1>
          </div>
          <p className="text-base leading-relaxed text-gray-500 dark:text-gray-400">
            {localize(
              'com_ui_report_upload_your_documents_and_we_ll_generate_a_comprehensive_financial_report_in_pdf_format',
            )}
          </p>
        </div>

        {/* Upload Card */}
        <div className="overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-sm transition-shadow hover:shadow-md dark:border-gray-700/80 dark:bg-gray-800/80">
          <div className="border-b border-gray-100 bg-gray-50/50 px-6 py-4 dark:border-gray-700/50 dark:bg-gray-800/50">
            <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">
              {localize('com_ui_report_upload_documents')}
            </h2>
            <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
              {localize('com_ui_report_supported_pdf_docx_xlsx_csv_pptx')}
            </p>
          </div>
          <div className="space-y-4 p-6">
            <label
              className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-8 transition-colors ${
                running
                  ? 'border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800'
                  : 'border-gray-300 bg-gray-50/50 hover:border-[#A89968]/50 hover:bg-[#A89968]/5 dark:border-gray-600 dark:bg-gray-800/50 dark:hover:border-[#A89968]/40 dark:hover:bg-[#A89968]/5'
              }`}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#A89968]/10 dark:bg-[#A89968]/20">
                <svg
                  className="h-6 w-6 text-[#A89968]"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"
                  />
                </svg>
              </div>
              <div className="text-center">
                <span className="text-base font-medium text-gray-700 dark:text-gray-300">
                  {files.length > 0 ? 'Click to add more files' : 'Click to browse files'}
                </span>
                {files.length === 0 && (
                  <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
                    {localize('com_ui_report_select_one_or_more_files_at_a_time')}
                  </p>
                )}
              </div>
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.csv,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/csv,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                onChange={handleFileChange}
                disabled={running}
                className="hidden"
              />
            </label>
            {/* File list with remove buttons */}
            {files.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    {files.length} {localize('com_ui_report_file')}
                    {files.length > 1 ? 's' : ''} {localize('com_ui_report_selected')}
                  </span>
                  {!running && files.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setFiles([])}
                      className="text-sm font-medium text-red-500 transition-colors hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                    >
                      {localize('com_ui_report_remove_all')}
                    </button>
                  )}
                </div>
                <ul className="flex flex-wrap gap-2">
                  {files.map((f) => (
                    <li
                      key={f.name}
                      className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm text-gray-700 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300"
                    >
                      <svg
                        className="h-4 w-4 flex-shrink-0 text-[#A89968]"
                        fill="none"
                        viewBox="0 0 24 24"
                        strokeWidth={1.5}
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                        />
                      </svg>
                      <span className="max-w-[200px] truncate">{f.name}</span>
                      {!running && (
                        <button
                          type="button"
                          onClick={() => removeFile(f.name)}
                          className="ml-1 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600 dark:hover:bg-gray-600 dark:hover:text-gray-200"
                          title={`Remove ${f.name}`}
                        >
                          <svg
                            className="h-3 w-3"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={2}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M6 18 18 6M6 6l12 12"
                            />
                          </svg>
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <button
              type="button"
              onClick={runReport}
              disabled={running}
              title={files.length === 0 ? 'Select at least one file first' : undefined}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#A89968] px-5 py-3 text-base font-semibold text-white shadow-sm transition-all hover:bg-[#958b5e] hover:shadow-md disabled:opacity-50 dark:bg-[#A89968] dark:hover:bg-[#958b5e]"
            >
              {running ? (
                <>
                  <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  {localize('com_ui_report_generating_report')}
                </>
              ) : (
                <>
                  <svg
                    className="h-5 w-5"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
                    />
                  </svg>
                  {localize('com_ui_report_generate_report')}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Stay on page warning */}
        {running && (
          <div className="flex items-center gap-3 rounded-2xl border border-[#A89968]/30 bg-[#A89968]/5 px-5 py-3 dark:border-[#A89968]/20 dark:bg-[#A89968]/10">
            <svg
              className="h-5 w-5 flex-shrink-0 text-[#A89968]"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
              />
            </svg>
            <p className="text-sm font-medium text-[#958b5e] dark:text-[#C4B682]">
              {localize(
                'com_ui_report_your_report_is_being_generated_you_can_safely_close_this_page_it_will_continue_running_in_',
              )}
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-5 dark:border-red-800/50 dark:bg-red-900/20">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/40">
              <svg
                className="h-4 w-4 text-red-600 dark:text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
                />
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-base font-medium text-red-800 dark:text-red-300">{error}</p>
              {!running && files.length > 0 && (
                <button
                  type="button"
                  onClick={runReport}
                  className="mt-3 rounded-lg bg-red-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-red-700 dark:bg-red-700 dark:hover:bg-red-600"
                >
                  {localize('com_ui_report_retry')}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Warning */}
        {streamWarning && !error && (
          <div className="flex items-start gap-3 rounded-2xl border border-yellow-200 bg-yellow-50 p-5 dark:border-yellow-800/50 dark:bg-yellow-900/20">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-yellow-100 dark:bg-yellow-900/40">
              <svg
                className="h-4 w-4 text-yellow-600 dark:text-yellow-400"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
                />
              </svg>
            </div>
            <p className="text-base text-yellow-800 dark:text-yellow-300">{streamWarning}</p>
          </div>
        )}

        {/* Progress & Steps */}
        {(running || streamStatus !== 'idle' || steps.length > 0) && (
          <div className="overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-sm dark:border-gray-700/80 dark:bg-gray-800/80">
            <div className="border-b border-gray-100 bg-gray-50/50 px-6 py-4 dark:border-gray-700/50 dark:bg-gray-800/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {running && (
                    <span className="relative flex h-2.5 w-2.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#A89968] opacity-75" />
                      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#A89968]" />
                    </span>
                  )}
                  <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">
                    {localize('com_ui_report_progress')}
                  </h2>
                </div>
                {progress.total ? (
                  <span className="rounded-full bg-[#A89968]/10 px-3 py-1 text-sm font-medium text-[#A89968] dark:bg-[#A89968]/20">
                    {progress.current ?? 0} / {progress.total} {localize('com_ui_report_slides')}
                  </span>
                ) : null}
                {!progress.total && progress.current ? (
                  <span className="rounded-full bg-[#A89968]/10 px-3 py-1 text-sm font-medium text-[#A89968] dark:bg-[#A89968]/20">
                    {localize('com_ui_report_slide')} {progress.current}
                  </span>
                ) : null}
              </div>
            </div>
            <div className="p-6">
              {/* Current step */}
              <div className="mb-4 space-y-3">
                <div className="flex items-center gap-2 text-base">
                  <span className="text-gray-500 dark:text-gray-400">
                    {localize('com_ui_report_current')}
                  </span>
                  <span className="font-semibold text-gray-900 dark:text-gray-100">
                    {currentStep?.label ?? (running ? 'Initializing...' : '—')}
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                  {progressPercent != null ? (
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-[#A89968] to-[#C4B682] transition-all duration-500 ease-out"
                      style={{ width: `${progressPercent}%` }}
                    />
                  ) : null}
                  {progressPercent == null && running ? (
                    <div className="h-full w-full overflow-hidden rounded-full">
                      <div className="h-full w-full animate-pulse bg-gradient-to-r from-[#A89968]/40 via-[#A89968]/70 to-[#A89968]/40" />
                    </div>
                  ) : null}
                </div>
                {currentStep?.summary && (
                  <p className="text-sm italic text-gray-500 dark:text-gray-400">
                    {currentStep.summary}
                  </p>
                )}
              </div>
              {/* Steps timeline */}
              {visibleSteps.length > 0 && (
                <div className="mt-4 border-t border-gray-100 pt-4 dark:border-gray-700/50">
                  <ul className="space-y-3">
                    {visibleSteps.map((s, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <div className="mt-1.5 flex h-5 w-5 flex-shrink-0 items-center justify-center">
                          <div
                            className={`h-2 w-2 rounded-full ${
                              i === visibleSteps.length - 1 && running
                                ? 'animate-pulse bg-[#A89968]'
                                : 'bg-[#A89968]/40'
                            }`}
                          />
                        </div>
                        <div className="min-w-0 flex-1">
                          <span className="text-base font-medium text-gray-800 dark:text-gray-200">
                            {s.label}
                          </span>
                          {s.summary && (
                            <p className="mt-0.5 truncate text-sm text-gray-500 dark:text-gray-400">
                              {s.summary}
                              {s.truncated ? '...' : ''}
                            </p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Report History */}
        <div className="overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-sm dark:border-gray-700/80 dark:bg-gray-800/80">
          <div className="border-b border-gray-100 bg-gray-50/50 px-6 py-4 dark:border-gray-700/50 dark:bg-gray-800/50">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">
                {localize('com_ui_report_report_history')}
              </h2>
              <button
                type="button"
                onClick={fetchHistory}
                disabled={historyLoading || running}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 disabled:opacity-40 dark:text-gray-400 dark:hover:bg-gray-700/50 dark:hover:text-gray-200"
              >
                <svg
                  className={`h-4 w-4 ${historyLoading ? 'animate-spin' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"
                  />
                </svg>
                {localize('com_ui_report_refresh')}
              </button>
            </div>
          </div>

          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {/* In-progress entry for the current run */}
            {running && (
              <div className="flex items-center justify-between px-6 py-4">
                <div className="flex items-center gap-3">
                  <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {localize('com_ui_report_report_generating')}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      {currentStep?.label ?? 'Initializing'}
                    </p>
                  </div>
                </div>
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                  {localize('com_ui_report_in_progress')}
                </span>
              </div>
            )}

            {/* Failed entry for the most recent run */}
            {!running && streamStatus === 'error' && (
              <div className="flex items-center justify-between px-6 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-2.5 w-2.5 flex-shrink-0 items-center justify-center">
                    <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {localize('com_ui_report_generation_failed')}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      {localize('com_ui_report_no_report_was_saved')}
                    </p>
                  </div>
                </div>
                <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-700 dark:bg-red-900/30 dark:text-red-400">
                  {localize('com_ui_report_failed')}
                </span>
              </div>
            )}

            {/* Historical runs from GCS */}
            {history.length === 0 && !running ? (
              <div className="px-6 py-10 text-center">
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  {historyLoading ? 'Loading…' : 'No reports generated yet.'}
                </p>
              </div>
            ) : (
              history.map((run) => {
                const isCompleted = run.status === 'completed';
                const isFailed = run.status === 'failed';
                const isStaleInProgress = run.status === 'in_progress';
                const pdfUrl =
                  isCompleted && run.pdf_filename
                    ? `${apiBase}/reports/${encodedUserId}/${encodeURIComponent(run.pdf_filename)}`
                    : null;
                return (
                  <div
                    key={run.run_id}
                    className="flex items-center justify-between gap-4 px-6 py-4"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-2.5 w-2.5 flex-shrink-0 items-center justify-center">
                        {isCompleted && <div className="h-2.5 w-2.5 rounded-full bg-emerald-400" />}
                        {isFailed && <div className="h-2.5 w-2.5 rounded-full bg-red-400" />}
                        {isStaleInProgress && (
                          <span className="relative flex h-2.5 w-2.5">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" />
                          </span>
                        )}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {run.title ?? formatReportDate(run.started_at)}
                        </p>
                        {run.title && (
                          <p className="text-xs text-gray-400 dark:text-gray-500">
                            {formatReportDate(run.started_at)}
                          </p>
                        )}
                        {isFailed && run.error && (
                          <p
                            className="mt-0.5 truncate text-xs text-red-400 dark:text-red-500"
                            title={run.error}
                          >
                            {run.error}
                          </p>
                        )}
                        {isStaleInProgress && (
                          <p className="text-xs text-gray-400 dark:text-gray-500">
                            {run.message ?? 'Starting...'}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-2">
                      {isCompleted && (
                        <>
                          <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                            {localize('com_ui_report_completed')}
                          </span>
                          {pdfUrl && (
                            <a
                              href={pdfUrl}
                              onClick={(event) => {
                                event.preventDefault();
                                void downloadReport(pdfUrl, run.pdf_filename ?? 'report.pdf');
                              }}
                              className="flex items-center gap-1.5 rounded-lg bg-[#A89968] px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-[#958b5e]"
                            >
                              <svg
                                className="h-3.5 w-3.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                strokeWidth={1.5}
                                stroke="currentColor"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
                                />
                              </svg>
                              {localize('com_ui_report_pdf')}
                            </a>
                          )}
                        </>
                      )}
                      {isFailed && (
                        <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-700 dark:bg-red-900/30 dark:text-red-400">
                          {localize('com_ui_report_failed')}
                        </span>
                      )}
                      {isStaleInProgress && (
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                          {localize('com_ui_report_in_progress')}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
