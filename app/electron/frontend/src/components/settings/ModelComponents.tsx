import { cn, formatBytes, normalizeProgressPercent } from './utils';
import type { ModelCatalogEntry, ModelManagerState } from './types';

interface ModelStatusBadgeProps {
  installed: boolean;
  verified: boolean;
  recommended: boolean;
}

export function ModelStatusBadge({ installed, verified, recommended }: ModelStatusBadgeProps) {
  return (
    <div className="flex flex-wrap gap-1">
      <span
        className={cn(
          'text-[9px] px-1.5 py-0.5 font-bold uppercase',
          installed ? 'bg-theme-success text-lawn-bg' : 'bg-stone-300 text-stone-700'
        )}
      >
        {installed ? 'Installed' : 'Not Installed'}
      </span>
      {verified && (
        <span className="text-[9px] px-1.5 py-0.5 bg-theme-info text-lawn-bg font-bold uppercase">
          Verified
        </span>
      )}
      {recommended && (
        <span className="text-[9px] px-1.5 py-0.5 bg-lawn-accent text-lawn-bg font-bold uppercase">
          Recommended
        </span>
      )}
    </div>
  );
}

interface ModelCatalogBlockProps {
  title: string;
  description: string;
  category: 'asr' | 'refiner';
  models: ModelCatalogEntry[];
  selectedModelId: string;
  modelManager?: ModelManagerState;
  runtimeEnabled: boolean;
  onSelect: (modelId: string) => void;
  onDownload?: (modelId: string) => void | Promise<void>;
  onCancelDownload?: (modelId: string) => void | Promise<void>;
  onRemove?: (modelId: string) => void | Promise<void>;
}

export function ModelCatalogBlock({
  title,
  description,
  category,
  models,
  selectedModelId,
  modelManager,
  runtimeEnabled,
  onSelect,
  onDownload,
  onCancelDownload,
  onRemove,
}: ModelCatalogBlockProps) {
  const installStateById = new Map((modelManager?.installed ?? []).map((entry) => [entry.model_id, entry]));

  return (
    <div className="border-2 border-lawn-border bg-lawn-panel p-4">
      <div className="mb-4">
        <h4 className="text-sm font-bold">{title}</h4>
        <p className="text-xs text-stone-500 mt-1">{description}</p>
      </div>

      <div className="mb-4">
        <select
          value={selectedModelId}
          onChange={(e) => onSelect(e.target.value)}
          className="w-full h-10 px-3 pr-10 border-2 border-lawn-border bg-lawn-bg text-sm font-bold focus:border-lawn-accent focus:outline-none appearance-none cursor-pointer text-lawn-border"
        >
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.display_name}{model.installed ? '' : ' (not installed)'}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-3">
        {models.map((model) => {
          const installState = installStateById.get(model.id);
          const downloadState = modelManager?.downloads[model.id];
          const isSelected = selectedModelId === model.id;
          const isDownloading = downloadState && ['downloading', 'retrying', 'verifying'].includes(downloadState.status);
          const canActivate = model.installed && model.enabled_runtime;
          const hasKnownTotal = Boolean(
            downloadState?.total_bytes_known && downloadState.total_bytes > 0,
          );
          const progressPercent =
            downloadState && hasKnownTotal
              ? normalizeProgressPercent(downloadState.progress)
              : 0;

          return (
            <div
              key={model.id}
              className={cn(
                'border-2 p-3',
                isSelected ? 'border-lawn-accent bg-lawn-accent/5' : 'border-lawn-border bg-lawn-bg'
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold">{model.display_name}</span>
                    <ModelStatusBadge
                      installed={model.installed}
                      verified={model.verified}
                      recommended={model.recommended}
                    />
                    {!model.enabled_runtime && (
                      <span className="text-[9px] px-1.5 py-0.5 bg-theme-warning text-lawn-bg font-bold uppercase">
                        Runtime Stub
                      </span>
                    )}
                    {isSelected && (
                      <span className="text-[9px] px-1.5 py-0.5 bg-lawn-border text-lawn-bg font-bold uppercase">
                        Selected
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-stone-500">{model.description_short}</p>
                  <p className="mt-2 text-xs text-lawn-border">
                    <span className="font-bold">Why choose this:</span> {model.why_choose_this}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-stone-500">
                    <span>{model.size_gb_estimate.toFixed(1)} GB</span>
                    <span>{model.speed_tier}</span>
                    <span>{model.engine}</span>
                    <span>VRAM {model.recommended_vram_gb}+ GB</span>
                    {installState?.size_bytes ? <span>{formatBytes(installState.size_bytes)}</span> : null}
                  </div>
                  {downloadState ? (
                    <div className="mt-3">
                      <div className="mb-1 flex items-center justify-between text-[10px] font-bold">
                        <span className="uppercase text-stone-500">
                          {downloadState.status === 'retrying' ? 'Retrying' : downloadState.status}
                        </span>
                        <span>
                          {hasKnownTotal
                            ? `${progressPercent.toFixed(progressPercent >= 10 ? 0 : 1)}%`
                            : 'Calculating…'}
                        </span>
                      </div>
                      <div className="h-2 border border-lawn-border bg-lawn-bg overflow-hidden">
                        <div
                          className="h-full bg-lawn-accent transition-all"
                          style={{
                            width: hasKnownTotal ? `${progressPercent}%` : '100%',
                            opacity: hasKnownTotal ? 1 : 0.35,
                          }}
                        />
                      </div>
                      <div className="mt-1 text-[10px] text-stone-500">
                        {hasKnownTotal
                          ? `${formatBytes(downloadState.bytes_downloaded)} / ${formatBytes(downloadState.total_bytes)}`
                          : `${formatBytes(downloadState.bytes_downloaded)} downloaded`}
                        {' · '}
                        {formatBytes(downloadState.speed_bytes_per_sec)}/s
                      </div>
                      {downloadState.error ? (
                        <div className="mt-1 text-[10px] font-bold text-theme-error">{downloadState.error}</div>
                      ) : null}
                    </div>
                  ) : null}
                  {category === 'refiner' && isSelected && !runtimeEnabled ? (
                    <div className="mt-2 text-[10px] font-bold text-theme-warning">
                      Installed and configurable, but local refiner runtime is not enabled yet.
                    </div>
                  ) : null}
                  {category === 'asr' && isSelected && !canActivate ? (
                    <div className="mt-2 text-[10px] font-bold text-theme-warning">
                      This model is selected as the default but cannot run until it is installed.
                    </div>
                  ) : null}
                </div>

                <div className="flex shrink-0 flex-col gap-2">
                  {!model.installed && onDownload ? (
                    <button
                      onClick={() => void onDownload(model.id)}
                      disabled={Boolean(isDownloading)}
                      className="px-3 py-2 border-2 border-lawn-border bg-lawn-accent text-lawn-bg text-xs font-bold disabled:opacity-50"
                    >
                      {isDownloading ? 'Downloading…' : 'Download'}
                    </button>
                  ) : null}

                  {isDownloading && onCancelDownload ? (
                    <button
                      onClick={() => void onCancelDownload(model.id)}
                      className="px-3 py-2 border-2 border-lawn-border bg-lawn-bg text-xs font-bold"
                    >
                      Cancel
                    </button>
                  ) : null}

                  {model.installed && onRemove ? (
                    <button
                      onClick={() => void onRemove(model.id)}
                      className="px-3 py-2 border-2 border-lawn-border bg-lawn-bg text-xs font-bold"
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
