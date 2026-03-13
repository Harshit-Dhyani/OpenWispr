import { MainContent } from './MainContent';
import { ModeCardsRow } from './ModeCardsRow';
import type { Device, SessionSummary, Segment, Formula, Health } from '../types/api';

type Snapshot = {
  session: SessionSummary | null;
  transcript: Segment[];
  suppressed_transcript: Segment[];
  formulas: Formula[];
  needs_review: Segment[];
  health: Health;
  available_languages: string[];
};

type LiveDraftState = {
  sessionId: string | null;
  committedText: string;
  draftSuffix: string;
  revision: number;
  source: string;
} | null;

type TranscriptDebugEvent = {
  id: number;
  type: string;
  sessionId: string | null;
  segmentId: string | null;
  correlationId?: string | null;
  detail?: string | null;
  textLength: number;
};

type SessionsViewProps = {
  snapshot: Snapshot;
  liveLatency: number | null;
  liveDraft: LiveDraftState;
  transcriptDebugEvents: TranscriptDebugEvent[];
  form: {
    sessionTitle: string;
    captureMode: 'system' | 'microphone';
    deviceId: string;
    modelName: string;
    languageMode: string;
    liveMode: string;
    executionMode: string;
    exportRoot: string;
  };
  sessionDevices: Device[];
  sessionModelId: string;
  isStarting: boolean;
  isStopping: boolean;
  preloadStatus: {
    loading: boolean;
    progress: number;
    message: string;
    stage?: 'idle' | 'preparing' | 'loading' | 'warming' | 'ready' | 'downloading' | 'failed';
    model_name?: string;
  };
  preloadHeadline: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onFieldChange: (key: any, value: any) => void;
  onStartSession: () => void;
  onStopSession: () => void;
  onPreloadModel: () => void;
  onAttachPdf: () => void;
  onOpenQuickSettings: () => void;
};

export function SessionsView({
  snapshot,
  liveLatency,
  liveDraft,
  transcriptDebugEvents,
  form,
  sessionDevices,
  sessionModelId,
  isStarting,
  isStopping,
  preloadStatus,
  preloadHeadline,
  onFieldChange,
  onStartSession,
  onStopSession,
  onPreloadModel,
  onAttachPdf,
  onOpenQuickSettings,
}: SessionsViewProps) {
  const busy = isStarting || isStopping;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="border-b-2 border-lawn-border bg-lawn-panel p-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_auto]">
          <div className="space-y-4">
            <div className="border-2 border-lawn-border bg-lawn-bg/60 p-4 shadow-brutal-sm">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-lawn-muted">
                Session workspace
              </p>
              <h2 className="mt-2 font-display text-4xl uppercase tracking-tight text-lawn-border">
                Long-form transcription
              </h2>
              <p className="mt-3 text-sm leading-6 text-lawn-muted">
                System audio is the default here. Use the session controls for meetings, videos, exports, and review.
              </p>
            </div>
            <ModeCardsRow
              cards={[
                {
                  title: 'Session Workspace',
                  description: `${form.sessionTitle || 'Untitled session'} · ${snapshot.session?.status ?? 'ready'}`,
                  controls: (
                    <input
                      value={form.sessionTitle}
                      onChange={(event) => onFieldChange('sessionTitle', event.target.value)}
                      className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                    />
                  ),
                },
                {
                  title: 'Long-form Transcription',
                  description: `${form.captureMode === 'system' ? 'System audio' : 'Microphone'} · ${sessionModelId}`,
                  controls: (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <select
                        value={form.captureMode}
                        onChange={(event) => onFieldChange('captureMode', event.target.value as typeof form.captureMode)}
                        className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                      >
                        <option value="system">System Audio</option>
                        <option value="microphone">Microphone</option>
                      </select>
                      <select
                        value={form.deviceId}
                        onChange={(event) => onFieldChange('deviceId', event.target.value)}
                        className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                      >
                        {sessionDevices.map((device) => (
                          <option key={device.id} value={device.id}>
                            {device.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ),
                },
                {
                  title: 'Session Export + Notes',
                  description: `${form.exportRoot || 'sessions'} · PDF context and exports stay attached to this session`,
                  controls: (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <select
                        value={form.languageMode}
                        onChange={(event) => onFieldChange('languageMode', event.target.value)}
                        className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                      >
                        {snapshot.available_languages.map((language) => (
                          <option key={language} value={language}>
                            {language}
                          </option>
                        ))}
                      </select>
                      <div className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border">
                        {form.exportRoot || 'sessions'}
                      </div>
                    </div>
                  ),
                },
              ]}
            />
          </div>
          <div className="flex flex-wrap gap-3 xl:flex-col xl:items-stretch">
            <button
              type="button"
              onClick={() => void (snapshot.session?.status === 'running' ? onStopSession() : onStartSession())}
              disabled={busy}
              className="border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg disabled:cursor-not-allowed disabled:opacity-60"
            >
              {snapshot.session?.status === 'running' ? 'Stop Session' : 'Start Session'}
            </button>
            <button
              type="button"
              onClick={onOpenQuickSettings}
              className="border-2 border-lawn-border bg-lawn-bg px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-border"
            >
              Quick settings
            </button>
            <button
              type="button"
              onClick={() => void onPreloadModel()}
              className="border-2 border-lawn-border bg-lawn-dark px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
            >
              {preloadStatus.loading ? preloadHeadline : 'Prepare model'}
            </button>
            <button
              type="button"
              onClick={() => void onAttachPdf()}
              className="border-2 border-lawn-border bg-lawn-bg px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-border"
            >
              Attach PDF context
            </button>
          </div>
        </div>
      </div>
      <div className="min-h-0 flex-1 p-4">
        <MainContent
          scope="session"
          snapshot={snapshot}
          liveLatency={liveLatency}
          liveDraft={liveDraft}
          transcriptDebugEvents={transcriptDebugEvents}
          workspaceLabel="Sessions"
          workspaceTitle={form.sessionTitle || 'System Audio Session'}
          workspaceDescription={`Source: ${form.captureMode === 'system' ? 'system audio' : 'microphone'} · Model: ${sessionModelId} · Execution: ${form.executionMode}`}
        />
      </div>
    </div>
  );
}
