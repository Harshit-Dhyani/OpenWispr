import { useCallback, useEffect, useState, type ChangeEvent } from 'react';
import type { SnippetEntry } from '../types/api';
import { RENDERER_STRINGS } from '../strings/en';
import { FeaturePageShell } from './FeaturePageShell';

type SnippetsPageProps = {
  request: <T>(path: string, options?: RequestInit) => Promise<T>;
  enabled: boolean;
};

type ScopeTab = 'all' | 'personal' | 'shared' | 'team';

export function SnippetsPage({ request, enabled }: SnippetsPageProps) {
  const text = RENDERER_STRINGS.pages.snippets;
  const [scope, setScope] = useState<ScopeTab>('all');
  const [entries, setEntries] = useState<SnippetEntry[]>([]);
  const [trigger, setTrigger] = useState('');
  const [expansion, setExpansion] = useState('');
  const [previewInput, setPreviewInput] = useState('');
  const [previewOutput, setPreviewOutput] = useState('');

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (scope !== 'all') params.set('scope', scope);
    const response = await request<{ entries: SnippetEntry[] }>(`/api/snippets${params.toString() ? `?${params}` : ''}`);
    setEntries(response.entries);
  }, [request, scope]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createEntry() {
    if (!trigger.trim()) return;
    await request('/api/snippets', {
      method: 'POST',
      body: JSON.stringify({
        trigger,
        expansion,
        scope: scope === 'all' ? 'personal' : scope,
        enabled: true,
      }),
    });
    setTrigger('');
    setExpansion('');
    await load();
  }

  async function deleteEntry(id: string) {
    await request(`/api/snippets/${encodeURIComponent(id)}`, { method: 'DELETE' });
    await load();
  }

  async function previewExpand() {
    const response = await request<{ output_text: string }>('/api/snippets/preview-expand', {
      method: 'POST',
      body: JSON.stringify({ text: previewInput }),
    });
    setPreviewOutput(response.output_text);
  }

  async function exportJson() {
    const response = await fetch('/api/snippets/export');
    if (!response.ok) return;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'snippets.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function importJson(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const raw = await file.text();
    const parsed = JSON.parse(raw) as SnippetEntry[];
    await request('/api/snippets/import', {
      method: 'POST',
      body: JSON.stringify({ entries: parsed, replace_existing: true }),
    });
    event.target.value = '';
    await load();
  }

  return (
    <FeaturePageShell
      eyebrow="Trigger expansions"
      title={text.title}
      subtitle={text.subtitle}
      enabledLabel={enabled ? text.enabled : text.disabled}
      actions={
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void exportJson()}
            className="border-2 border-lawn-border bg-lawn-bg px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-border"
          >
            {text.exportButton}
          </button>
          <label className="cursor-pointer border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-[11px] font-black uppercase tracking-[0.14em] text-lawn-bg">
            {text.importButton}
            <input type="file" accept="application/json" className="hidden" onChange={(event) => void importJson(event)} />
          </label>
        </div>
      }
      summary={
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {(['all', 'personal', 'shared', 'team'] as ScopeTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setScope(tab)}
                className={[
                  'border-2 px-3 py-2 text-xs font-black uppercase tracking-[0.1em]',
                  scope === tab ? 'border-lawn-accent bg-lawn-accent text-lawn-bg' : 'border-lawn-border bg-lawn-panel text-lawn-border',
                ].join(' ')}
              >
                {tab === 'all' ? text.tabs.all : tab === 'personal' ? text.tabs.personal : tab === 'shared' ? text.tabs.shared : text.tabs.team}
              </button>
            ))}
          </div>
          <p className="text-xs font-bold text-lawn-muted">
            Snippet expansion runs deterministically after dictionary cleanup so frequent phrases stay portable and predictable.
          </p>
        </div>
      }
    >
      <div className="grid h-full min-h-0 gap-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <div className="flex min-h-0 flex-col gap-4 overflow-hidden">
          <section className="border-2 border-lawn-border bg-lawn-panel p-3 shadow-brutal-sm">
            <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.addTitle}</h3>
            <div className="mt-3 grid gap-2">
              <input
                value={trigger}
                onChange={(event) => setTrigger(event.target.value)}
                placeholder={text.triggerPlaceholder}
                className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
              />
              <input
                value={expansion}
                onChange={(event) => setExpansion(event.target.value)}
                placeholder={text.expansionPlaceholder}
                className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
              />
              <button
                type="button"
                onClick={() => void createEntry()}
                className="border-2 border-lawn-accent bg-lawn-accent px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
              >
                {text.addButton}
              </button>
            </div>
          </section>

          <section className="border-2 border-lawn-border bg-lawn-panel p-3 shadow-brutal-sm">
            <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.previewTitle}</h3>
            <div className="mt-3 grid gap-2">
              <input
                value={previewInput}
                onChange={(event) => setPreviewInput(event.target.value)}
                placeholder={text.previewPlaceholder}
                className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
              />
              <button
                type="button"
                onClick={() => void previewExpand()}
                className="border-2 border-lawn-border bg-lawn-dark px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
              >
                {text.previewButton}
              </button>
            </div>
            <p className="mt-3 text-sm font-bold text-lawn-border">{previewOutput || text.noPreview}</p>
          </section>
        </div>

        <section className="min-h-0 overflow-hidden border-2 border-lawn-border bg-lawn-panel shadow-brutal-sm">
          <div className="flex items-center justify-between border-b-2 border-lawn-border bg-lawn-bg p-3">
            <div>
              <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">Snippet library</h3>
              <p className="mt-1 text-xs font-bold text-lawn-muted">{entries.length} saved snippet{entries.length === 1 ? '' : 's'}</p>
            </div>
          </div>
          <div className="h-full overflow-y-auto p-3 custom-scrollbar">
            <div className="space-y-2">
              {entries.map((entry) => (
                <article key={entry.id} className="flex flex-wrap items-center justify-between gap-3 border-2 border-lawn-border bg-lawn-bg p-3">
                  <div>
                    <p className="text-sm font-black text-lawn-border">{entry.trigger} → {entry.expansion}</p>
                    <p className="text-[11px] font-bold text-lawn-muted">{entry.scope} · {entry.usage_count} {text.usesSuffix}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void deleteEntry(entry.id)}
                    className="border-2 border-lawn-border bg-lawn-panel px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-border"
                  >
                    {text.deleteButton}
                  </button>
                </article>
              ))}
              {!entries.length ? (
                <p className="border-2 border-dashed border-lawn-border bg-lawn-bg/60 p-4 text-sm font-bold text-lawn-muted">
                  {text.noEntries}
                </p>
              ) : null}
            </div>
          </div>
        </section>
      </div>
    </FeaturePageShell>
  );
}

