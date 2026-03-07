import { useCallback, useEffect, useMemo, useState } from 'react';
import type { HistoryAnalytics, HistorySession } from '../types/api';
import { RENDERER_STRINGS } from '../strings/en';

type RangeOption = '7' | '30' | '90' | 'all';

type HomePageProps = {
  request: <T>(path: string, options?: RequestInit) => Promise<T>;
  onOpenSettings: () => void;
  onStatus: (message: string) => void;
  defaultRangeDays: number | 'all';
  allowRetry: boolean;
  persistAudio: boolean;
  variant?: 'full' | 'compact';
};

function toRangeOption(value: number | 'all'): RangeOption {
  if (value === 'all') return 'all';
  if (value === 30) return '30';
  if (value === 90) return '90';
  return '7';
}

function fmtHour(hour: number | null): string {
  if (hour === null || hour === undefined) return '--';
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const normalized = hour % 12 === 0 ? 12 : hour % 12;
  return `${normalized}:00 ${suffix}`;
}

export function HomePage({
  request,
  onOpenSettings,
  onStatus,
  defaultRangeDays,
  allowRetry,
  persistAudio,
  variant = 'full',
}: HomePageProps) {
  const text = RENDERER_STRINGS.pages.home;
  const [range, setRange] = useState<RangeOption>(toRangeOption(defaultRangeDays));
  const [analytics, setAnalytics] = useState<HistoryAnalytics | null>(null);
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [loading, setLoading] = useState(false);
  const [processingSessionId, setProcessingSessionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [analyticsRes, sessionsRes] = await Promise.all([
        request<HistoryAnalytics>(`/api/history/analytics?range_days=${range}`),
        request<{ sessions: HistorySession[] }>(`/api/history/sessions?range_days=${range}&limit=250`),
      ]);
      setAnalytics({
        range_days: analyticsRes?.range_days ?? range,
        timezone: analyticsRes?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
        summary: {
          days_used: analyticsRes?.summary?.days_used ?? 0,
          total_words: analyticsRes?.summary?.total_words ?? 0,
          avg_wpm: analyticsRes?.summary?.avg_wpm ?? 0,
          peak_usage_hour: analyticsRes?.summary?.peak_usage_hour ?? null,
        },
        daily: analyticsRes?.daily ?? [],
        hourly: analyticsRes?.hourly ?? [],
      });
      setSessions(sessionsRes?.sessions ?? []);
    } catch (error) {
      onStatus(error instanceof Error ? error.message : text.status.failedLoad);
    } finally {
      setLoading(false);
    }
  }, [onStatus, range, request, text.status.failedLoad]);

  useEffect(() => {
    void load();
  }, [load]);

  const hourlyMax = useMemo(() => {
    if (!analytics?.hourly?.length) return 1;
    return Math.max(1, ...analytics.hourly.map((item) => item.count));
  }, [analytics?.hourly]);

  async function handleCopy(session: HistorySession) {
    const transcriptText = session.active_text || '';
    await navigator.clipboard.writeText(transcriptText);
    onStatus(text.status.copied);
  }

  async function updateFromAction(path: string, method: string, sessionId: string, status: string) {
    setProcessingSessionId(sessionId);
    try {
      await request(path, { method });
      onStatus(status);
      await load();
    } catch (error) {
      onStatus(error instanceof Error ? error.message : text.status.failedAction);
    } finally {
      setProcessingSessionId(null);
    }
  }

  async function handleDownload(sessionId: string, asset: 'audio' | 'transcript') {
    setProcessingSessionId(sessionId);
    try {
      const response = await fetch(`/api/history/sessions/${encodeURIComponent(sessionId)}/download?asset=${asset}`);
      if (!response.ok) {
        throw new Error(text.status.failedDownload);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const disposition = response.headers.get('Content-Disposition');
      const fallbackName = `${sessionId}.${asset === 'audio' ? 'wav' : 'txt'}`;
      const parsedName = disposition?.split('filename=')[1]?.replace(/"/g, '');
      link.href = url;
      link.download = parsedName || fallbackName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      onStatus(asset === 'audio' ? text.status.downloadedAudio : text.status.downloadedTranscript);
    } catch (error) {
      onStatus(error instanceof Error ? error.message : text.status.failedDownload);
    } finally {
      setProcessingSessionId(null);
    }
  }

  return (
    <div className={variant === 'compact' ? 'flex h-full min-h-0 flex-col overflow-hidden' : 'flex h-full min-h-0 flex-col overflow-hidden p-4'}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-3xl uppercase tracking-tight text-lawn-border">
            {variant === 'compact' ? text.compactTitle : text.title}
          </h2>
          <p className="text-xs font-bold text-lawn-muted">
            {variant === 'compact' ? text.compactSubtitle : text.subtitle}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={range}
            onChange={(event) => setRange(event.target.value as RangeOption)}
            className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-border"
          >
            <option value="7">{text.rangeOptions.last7}</option>
            <option value="30">{text.rangeOptions.last30}</option>
            <option value="90">{text.rangeOptions.last90}</option>
            <option value="all">{text.rangeOptions.all}</option>
          </select>
          <button
            type="button"
            onClick={onOpenSettings}
            className="border-2 border-lawn-border bg-lawn-dark px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
          >
            {text.settingsButton}
          </button>
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <Metric label={text.metrics.daysUsed} value={String(analytics?.summary.days_used ?? 0)} />
        <Metric label={text.metrics.totalWords} value={String(analytics?.summary.total_words ?? 0)} />
        <Metric label={text.metrics.avgWpm} value={String(analytics?.summary.avg_wpm ?? 0)} />
        <Metric label={text.metrics.peakHour} value={fmtHour(analytics?.summary.peak_usage_hour ?? null)} />
      </div>

      {variant === 'full' ? (
        <div className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
          <section className="border-2 border-lawn-border bg-lawn-panel p-3">
            <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.dailyUsage}</h3>
            <div className="mt-3 space-y-2">
              {(analytics?.daily ?? []).map((item) => (
                <div key={item.day} className="grid grid-cols-[120px_1fr_40px] items-center gap-2 text-xs font-bold">
                  <span className="text-lawn-muted">{item.day}</span>
                  <div className="h-2 overflow-hidden border border-lawn-border bg-lawn-bg">
                    <div
                      className="h-full bg-lawn-accent"
                      style={{ width: `${Math.min(100, (item.count / Math.max(1, sessions.length)) * 100)}%` }}
                    />
                  </div>
                  <span className="text-right text-lawn-border">{item.count}</span>
                </div>
              ))}
              {!analytics?.daily?.length ? <p className="text-xs font-bold text-lawn-muted">{text.noData}</p> : null}
            </div>
          </section>
          <section className="border-2 border-lawn-border bg-lawn-panel p-3">
            <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.hourHeat}</h3>
            <div className="mt-3 grid grid-cols-6 gap-2">
              {(analytics?.hourly ?? []).map((item) => (
                <div
                  key={item.hour}
                  className="border border-lawn-border bg-lawn-bg px-2 py-1 text-center text-[10px] font-black"
                  style={{ opacity: 0.25 + (item.count / hourlyMax) * 0.75 }}
                  title={`${item.hour}:00 - ${item.count}`}
                >
                  {item.hour}
                </div>
              ))}
            </div>
          </section>
        </div>
      ) : null}

      <section className="min-h-0 flex-1 overflow-hidden border-2 border-lawn-border bg-lawn-panel">
        <div className="border-b-2 border-lawn-border bg-lawn-bg px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-lawn-muted">
          {text.sessionsTitle}
        </div>
        <div className="h-full overflow-y-auto p-3 custom-scrollbar">
          {loading ? <p className="text-sm font-bold text-lawn-muted">{text.loading}</p> : null}
          {!loading && sessions.length === 0 ? <p className="text-sm font-bold text-lawn-muted">{text.noSessions}</p> : null}
          <div className={variant === 'compact' ? 'space-y-2' : 'space-y-3'}>
            {sessions.map((session) => {
              const busy = processingSessionId === session.session_id;
              const canRetry = allowRetry && session.audio_available;
              const canDownloadAudio = persistAudio && session.audio_available;
              return (
                <article key={session.session_id} className="border-2 border-lawn-border bg-lawn-bg p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs font-black uppercase tracking-[0.08em] text-lawn-border">
                        {session.source_workflow} {text.sourceSeparator} {session.capture_source}
                      </p>
                      <p className="text-[11px] font-bold text-lawn-muted">
                        {session.started_at} {text.sourceSeparator} {session.model_id || session.model_name || text.modelUnknown}
                      </p>
                    </div>
                    <div className="text-xs font-black text-lawn-border">{session.word_count} {text.wordsSuffix}</div>
                  </div>
                  <p className="mb-3 line-clamp-3 text-sm font-bold leading-6 text-lawn-border">{session.active_text || '-'}</p>
                  <div className="flex flex-wrap gap-2">
                    <ActionButton disabled={busy} onClick={() => void handleCopy(session)} label={text.actions.copy} primary />
                    <ActionButton
                      disabled={busy}
                      onClick={() => void updateFromAction(`/api/history/sessions/${encodeURIComponent(session.session_id)}/undo-ai-edit`, 'POST', session.session_id, text.status.aiUndone)}
                      label={text.actions.undoAiEdit}
                    />
                    <ActionButton
                      disabled={busy || !canRetry}
                      onClick={() => void updateFromAction(`/api/history/sessions/${encodeURIComponent(session.session_id)}/retry`, 'POST', session.session_id, text.status.retryStarted)}
                      label={text.actions.retry}
                    />
                    <ActionButton
                      disabled={busy || !canDownloadAudio}
                      onClick={() => void handleDownload(session.session_id, 'audio')}
                      label={text.actions.downloadAudio}
                    />
                    <ActionButton
                      disabled={busy}
                      onClick={() => void handleDownload(session.session_id, 'transcript')}
                      label={text.actions.downloadTranscript}
                    />
                    <ActionButton
                      disabled={busy}
                      onClick={() => void updateFromAction(`/api/history/sessions/${encodeURIComponent(session.session_id)}`, 'DELETE', session.session_id, text.status.deleted)}
                      label={text.actions.delete}
                    />
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-2 border-lawn-border bg-lawn-panel p-3">
      <p className="text-[10px] font-black uppercase tracking-[0.12em] text-lawn-muted">{label}</p>
      <p className="mt-2 text-2xl font-black text-lawn-border">{value}</p>
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  primary = false,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        'border-2 px-3 py-2 text-[10px] font-black uppercase tracking-[0.1em] disabled:cursor-not-allowed disabled:opacity-50',
        primary ? 'border-lawn-accent bg-lawn-accent text-lawn-bg' : 'border-lawn-border bg-lawn-panel text-lawn-border',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

