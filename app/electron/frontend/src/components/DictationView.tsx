import type { CoachResult, Device, SessionSummary, Segment, Formula, Health } from '../types/api';
import { MainContent } from './MainContent';
import { ActivityFeed } from './ActivityFeed';

type Snapshot = {
  session: SessionSummary | null;
  transcript: Segment[];
  suppressed_transcript: Segment[];
  formulas: Formula[];
  needs_review: Segment[];
  health: Health;
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

type DictationViewProps = {
  liveLatency: number | null;
  dictationSnapshot: Snapshot;
  dictationLiveDraft: LiveDraftState;
  transcriptDebugEvents: TranscriptDebugEvent[];
  dictationCoachResult: CoachResult | null | undefined;
  dictationCoachStatus: 'disabled' | 'queued' | 'running' | 'failed' | 'fallback' | 'cache_hit' | 'generated' | 'success' | null | undefined;
  dictationCoachDisplaySource: 'coach' | 'fallback' | 'faithful' | null | undefined;
  dictationCoachError: string | null;
  dictationAggregatedText: string;
  dictationPasteText: string;
  dictationPostprocessedText: string;
  showCoachDiff: boolean;
  isDictationRecording: boolean;
  isDictationTransitioning: boolean;
  dictationLifecycleState: string;
  dictationLanguage: string;
  dictationModelId: string;
  dictationDevices: Device[];
  settingsHotkey: {
    finish_mode_default: string;
    device_id: string;
    enable_refiner_on_stop: boolean;
  };
  connectionStatus: string;
  gpuStatus: string;
  dictationHotkeyLabel: string;
  onStartDictation: () => void;
  onStopDictation: () => void;
  onOpenQuickSettings: () => void;
  onOpenSettings: () => void;
};

export function DictationView({
  liveLatency,
  dictationSnapshot,
  dictationLiveDraft,
  transcriptDebugEvents,
  dictationCoachResult,
  dictationCoachStatus,
  dictationCoachDisplaySource,
  dictationCoachError,
  dictationAggregatedText,
  dictationPasteText,
  dictationPostprocessedText,
  showCoachDiff,
  isDictationRecording,
  isDictationTransitioning,
  dictationLifecycleState,
  dictationLanguage,
  dictationModelId,
  dictationDevices,
  settingsHotkey,
  connectionStatus,
  gpuStatus,
  dictationHotkeyLabel,
  onStartDictation,
  onStopDictation,
  onOpenQuickSettings,
  onOpenSettings,
}: DictationViewProps) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="border-b-2 border-lawn-border bg-lawn-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl border-2 border-lawn-border bg-lawn-bg/60 p-4 shadow-brutal-sm">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-lawn-muted">
              Dictation workspace
            </p>
            <h2 className="mt-2 font-display text-4xl uppercase tracking-tight text-lawn-border">
              Talk, clean up, paste
            </h2>
            <p className="mt-3 text-sm leading-6 text-lawn-muted">
              Mic and hotkey dictation stay lightweight here. Use the quick drawer for language, finish action,
              and source-aware model choices without opening the full settings panel.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                if (isDictationTransitioning) {
                  return;
                }
                void (isDictationRecording ? onStopDictation() : onStartDictation());
              }}
              disabled={isDictationTransitioning}
              className="border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
            >
              {dictationLifecycleState === 'starting'
                ? 'Starting…'
                : dictationLifecycleState === 'stopping'
                  ? 'Stopping…'
                  : isDictationRecording
                    ? 'Stop Dictation'
                    : 'Start Dictation'}
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
              onClick={onOpenSettings}
              className="border-2 border-lawn-border bg-lawn-dark px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg"
            >
              Open settings
            </button>
          </div>
        </div>
        <div className="mt-4 border-2 border-lawn-border bg-lawn-bg p-3">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Language</span>
              <p className="mt-1 text-xs font-bold uppercase text-lawn-border">{dictationLanguage || 'auto'}</p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Model</span>
              <p className="mt-1 text-xs font-bold text-lawn-border">{dictationModelId}</p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Finish</span>
              <p className="mt-1 text-xs font-bold uppercase text-lawn-border">
                {settingsHotkey.finish_mode_default.replace(/_/g, ' ')}
              </p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Device</span>
              <p className="mt-1 text-xs font-bold text-lawn-border">
                {dictationDevices.find((device) => device.id === settingsHotkey.device_id)?.name ||
                  dictationDevices[0]?.name ||
                  'Default device'}
              </p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Source</span>
              <p className="mt-1 text-xs font-bold uppercase text-lawn-border">Microphone / Hotkey</p>
            </div>
            <div className="border border-lawn-border bg-lawn-panel px-3 py-2">
              <span className="text-[9px] font-black uppercase tracking-[0.14em] text-lawn-muted">Refiner</span>
              <p className="mt-1 text-xs font-bold uppercase text-lawn-border">
                {settingsHotkey.enable_refiner_on_stop ? 'Enabled' : 'Disabled'}
              </p>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="border border-lawn-border px-2 py-1 text-[10px] font-black uppercase text-lawn-border">
              {connectionStatus}
            </span>
            <span className="border border-lawn-border px-2 py-1 text-[10px] font-black uppercase text-lawn-border">
              {gpuStatus}
            </span>
            <span className="border border-lawn-border px-2 py-1 text-[10px] font-black uppercase text-lawn-border">
              {dictationHotkeyLabel || 'No hotkey set'}
            </span>
          </div>
        </div>
      </div>
      <div className="grid min-h-0 flex-1 gap-4 p-4 2xl:grid-cols-[minmax(0,1.1fr)_340px]">
        <div className="min-h-0 overflow-hidden">
          <MainContent
            scope="dictation"
            snapshot={dictationSnapshot}
            liveLatency={liveLatency}
            liveDraft={dictationLiveDraft}
            transcriptDebugEvents={transcriptDebugEvents}
            coachResult={dictationCoachResult ?? null}
            coachStatus={dictationCoachStatus ?? null}
            coachDisplaySource={dictationCoachDisplaySource ?? null}
            coachError={dictationCoachError}
            originalText={dictationAggregatedText}
            pasteText={dictationPasteText || dictationPostprocessedText}
            showCoachDiff={showCoachDiff}
            workspaceLabel="Dictation"
            workspaceTitle="Mic / hotkey timeline"
            workspaceDescription="Quick dictation, low-latency feedback, and one shared timeline for recent spoken text."
          />
        </div>
        <div className="min-h-0 overflow-hidden">
          <div className="h-full min-h-0 overflow-hidden">
            <ActivityFeed
              session={dictationSnapshot.session}
              transcript={dictationSnapshot.transcript}
              health={dictationSnapshot.health}
              variant="sidebar"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
