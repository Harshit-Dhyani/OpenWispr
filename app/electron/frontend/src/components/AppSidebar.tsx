import { Activity, BookText, Cpu, Home, Mic, RefreshCw, ScissorsSquareDashedBottom, Settings, Volume2, Wifi, WifiOff } from 'lucide-react';
import { RENDERER_STRINGS } from '../strings/en';
import openWisprLogo from '../assets/openwispr-logo.png';

type AppPage = 'home' | 'microphone' | 'systemAudio' | 'dictionary' | 'snippets' | 'settings';
type ConnectionStatus = 'sse-connected' | 'sse-reconnecting' | 'polling-fallback';
type GpuStatus = 'gpu-active' | 'cpu-fallback' | 'gpu-only-failed';

type AppSidebarProps = {
  activePage: AppPage;
  onNavigate: (page: AppPage) => void;
  onRefreshDevices: () => void;
  appName: string;
  statusMessage: string;
  connectionStatus: ConnectionStatus;
  gpuStatus: GpuStatus;
  sessionStatus: string;
};

const SIDEBAR_STRINGS = RENDERER_STRINGS.appSidebar;
const pageMeta: Array<{ page: AppPage; label: string; eyebrow: string }> = [
  { page: 'home', ...SIDEBAR_STRINGS.pageMeta.home },
  { page: 'microphone', ...SIDEBAR_STRINGS.pageMeta.microphone },
  { page: 'systemAudio', ...SIDEBAR_STRINGS.pageMeta.systemAudio },
  { page: 'dictionary', ...SIDEBAR_STRINGS.pageMeta.dictionary },
  { page: 'snippets', ...SIDEBAR_STRINGS.pageMeta.snippets },
  { page: 'settings', ...SIDEBAR_STRINGS.pageMeta.settings },
];

export function AppSidebar({
  activePage,
  onNavigate,
  onRefreshDevices,
  appName,
  statusMessage,
  connectionStatus,
  gpuStatus,
  sessionStatus,
}: AppSidebarProps) {
  const connectionLabel =
    connectionStatus === 'sse-connected'
      ? SIDEBAR_STRINGS.connection.liveStream
      : connectionStatus === 'sse-reconnecting'
        ? SIDEBAR_STRINGS.connection.reconnecting
        : SIDEBAR_STRINGS.connection.pollingFallback;
  const ConnectionIcon =
    connectionStatus === 'sse-connected'
      ? Wifi
      : connectionStatus === 'sse-reconnecting'
        ? WifiOff
        : Activity;

  const gpuLabel =
    gpuStatus === 'gpu-active'
      ? SIDEBAR_STRINGS.gpu.active
      : gpuStatus === 'gpu-only-failed'
        ? SIDEBAR_STRINGS.gpu.failed
        : SIDEBAR_STRINGS.gpu.fallback;
  const GpuIcon = Cpu;

  return (
    <aside className="flex h-full w-full shrink-0 flex-col border-b-2 border-lawn-border bg-lawn-dark p-4 text-white xl:w-[280px] xl:border-b-0 xl:border-r-2">
      <div className="border-2 border-lawn-bg/15 bg-black/20 p-4 shadow-brutal-sm">
        <img
          src={openWisprLogo}
          alt={`${appName} logo`}
          className="mb-4 h-14 w-14 rounded-2xl border border-lawn-bg/10 bg-lawn-bg/5 object-cover shadow-brutal-sm"
        />
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-lawn-accent">
          {SIDEBAR_STRINGS.heroEyebrow}
        </p>
        <h1 className="mt-2 font-display text-3xl uppercase tracking-tight text-lawn-bg">
          {appName}
        </h1>
        <p className="mt-3 text-[11px] font-bold leading-5 text-stone-300">
          {SIDEBAR_STRINGS.heroBody}
        </p>
      </div>

      <nav className="mt-4 space-y-2">
        {pageMeta.map(({ page, label, eyebrow }) => {
          const active = activePage === page;
          const Icon =
            page === 'home'
              ? Home
              : page === 'microphone'
                ? Mic
              : page === 'systemAudio'
                ? Volume2
              : page === 'dictionary'
                ? BookText
              : page === 'snippets'
                ? ScissorsSquareDashedBottom
                : Settings;
          return (
            <button
              key={page}
              type="button"
              onClick={() => onNavigate(page)}
              title={page === 'settings' ? 'Open Settings' : undefined}
              aria-label={page === 'settings' ? 'Open Settings' : undefined}
              className={[
                'w-full border-2 px-4 py-3 text-left shadow-brutal-sm transition-all',
                active
                  ? 'border-lawn-accent bg-lawn-accent text-lawn-bg'
                  : 'border-lawn-bg/20 bg-lawn-bg/10 text-lawn-bg hover:-translate-y-0.5 hover:bg-lawn-bg/20',
              ].join(' ')}
            >
              <div className="flex items-start gap-3">
                <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                <div className="min-w-0">
                  <div className="text-[9px] font-black uppercase tracking-[0.16em] opacity-70">
                    {eyebrow}
                  </div>
                  <div className="mt-1 text-sm font-black uppercase tracking-[0.08em]">{label}</div>
                </div>
              </div>
            </button>
          );
        })}
      </nav>

      <div className="mt-4 space-y-3 border-2 border-lawn-bg/15 bg-black/20 p-4 shadow-brutal-sm">
        <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-lawn-accent">
          <ConnectionIcon className="h-3.5 w-3.5" />
          {connectionLabel}
        </div>
        <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.14em] text-stone-200">
          <GpuIcon className="h-3.5 w-3.5" />
          {gpuLabel}
        </div>
        <div className="border-t border-lawn-bg/10 pt-3">
          <div className="text-[9px] font-black uppercase tracking-[0.16em] text-stone-400">
            {SIDEBAR_STRINGS.sessionStatus}
          </div>
          <div className="mt-1 text-sm font-black uppercase text-lawn-bg">{sessionStatus}</div>
        </div>
        <div className="border-t border-lawn-bg/10 pt-3">
          <div className="text-[9px] font-black uppercase tracking-[0.16em] text-stone-400">
            {SIDEBAR_STRINGS.runtime}
          </div>
          <div className="mt-1 text-[11px] font-bold leading-5 text-stone-300">{statusMessage}</div>
        </div>
        <button
          type="button"
          title={SIDEBAR_STRINGS.controls.refreshDevices}
          aria-label={SIDEBAR_STRINGS.controls.refreshDevices}
          onClick={onRefreshDevices}
          className="flex items-center justify-center gap-2 border-2 border-lawn-bg/20 bg-lawn-bg/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.14em] text-lawn-bg transition-all hover:-translate-y-0.5 hover:bg-lawn-bg/20"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {SIDEBAR_STRINGS.controls.refreshDevices}
        </button>
      </div>
    </aside>
  );
}


