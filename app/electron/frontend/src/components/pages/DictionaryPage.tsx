import { useCallback, useEffect, useState } from 'react';
import type { DictionaryEntry } from '../../types/api';
import { RENDERER_STRINGS } from '../../strings/en';

type DictionaryPageProps = {
  request: <T>(path: string, options?: RequestInit) => Promise<T>;
  enabled: boolean;
};

type ScopeTab = 'all' | 'personal' | 'shared' | 'team';

export function DictionaryPage({ request, enabled }: DictionaryPageProps) {
  const text = RENDERER_STRINGS.pages.dictionary;
  const scopeTabs: Array<{ key: ScopeTab; label: string }> = [
    { key: 'all', label: text.tabs.all },
    { key: 'personal', label: text.tabs.personal },
    { key: 'shared', label: text.tabs.shared },
    { key: 'team', label: text.tabs.team },
  ];
  const [entries, setEntries] = useState<DictionaryEntry[]>([]);
  const [search, setSearch] = useState('');
  const [scope, setScope] = useState<ScopeTab>('all');
  const [phrase, setPhrase] = useState('');
  const [replacement, setReplacement] = useState('');
  const [previewInput, setPreviewInput] = useState('');
  const [previewOutput, setPreviewOutput] = useState('');

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (scope !== 'all') {
      params.set('scope', scope);
    }
    if (search.trim()) {
      params.set('search', search.trim());
    }
    const path = `/api/dictionary${params.toString() ? `?${params}` : ''}`;
    const response = await request<{ entries: DictionaryEntry[] }>(path);
    setEntries(response.entries);
  }, [request, scope, search]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleCreate() {
    if (!phrase.trim()) return;
    await request('/api/dictionary', {
      method: 'POST',
      body: JSON.stringify({
        phrase,
        replacement,
        scope: scope === 'all' ? 'personal' : scope,
        enabled: true,
      }),
    });
    setPhrase('');
    setReplacement('');
    await load();
  }

  async function handleDelete(entryId: string) {
    await request(`/api/dictionary/${encodeURIComponent(entryId)}`, { method: 'DELETE' });
    await load();
  }

  async function handlePreview() {
    const response = await request<{ output_text: string }>('/api/dictionary/preview-apply', {
      method: 'POST',
      body: JSON.stringify({ text: previewInput }),
    });
    setPreviewOutput(response.output_text);
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-4">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-3xl uppercase tracking-tight text-lawn-border">{text.title}</h2>
          <p className="text-xs font-bold text-lawn-muted">{text.subtitle}</p>
        </div>
        <div className="text-xs font-black uppercase tracking-[0.1em] text-lawn-muted">
          {enabled ? text.enabled : text.disabled}
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {scopeTabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setScope(tab.key)}
            className={[
              'border-2 px-3 py-2 text-xs font-black uppercase tracking-[0.1em]',
              scope === tab.key ? 'border-lawn-accent bg-lawn-accent text-lawn-bg' : 'border-lawn-border bg-lawn-panel text-lawn-border',
            ].join(' ')}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={text.searchPlaceholder}
          className="min-w-[280px] flex-1 border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        />
        <button
          type="button"
          onClick={() => void load()}
          className="border-2 border-lawn-border bg-lawn-panel px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-border"
        >
          {text.searchButton}
        </button>
      </div>

      <section className="mb-4 border-2 border-lawn-border bg-lawn-panel p-3">
        <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.addTitle}</h3>
        <div className="mt-2 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <input
            value={phrase}
            onChange={(event) => setPhrase(event.target.value)}
            placeholder={text.phrasePlaceholder}
            className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          />
          <input
            value={replacement}
            onChange={(event) => setReplacement(event.target.value)}
            placeholder={text.replacementPlaceholder}
            className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          />
          <button
            type="button"
            onClick={() => void handleCreate()}
            className="border-2 border-lawn-accent bg-lawn-accent px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
          >
            {text.addButton}
          </button>
        </div>
      </section>

      <section className="mb-4 border-2 border-lawn-border bg-lawn-panel p-3">
        <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.previewTitle}</h3>
        <div className="mt-2 grid gap-2 md:grid-cols-[1fr_auto]">
          <input
            value={previewInput}
            onChange={(event) => setPreviewInput(event.target.value)}
            placeholder={text.previewPlaceholder}
            className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          />
          <button
            type="button"
            onClick={() => void handlePreview()}
            className="border-2 border-lawn-border bg-lawn-dark px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
          >
            {text.previewButton}
          </button>
        </div>
        <p className="mt-2 text-sm font-bold text-lawn-border">{previewOutput || text.noPreview}</p>
      </section>

      <section className="min-h-0 flex-1 overflow-hidden border-2 border-lawn-border bg-lawn-panel">
        <div className="h-full overflow-y-auto p-3 custom-scrollbar">
          <div className="space-y-2">
            {entries.map((entry) => (
              <article key={entry.id} className="flex flex-wrap items-center justify-between gap-3 border-2 border-lawn-border bg-lawn-bg p-3">
                <div>
                  <p className="text-sm font-black text-lawn-border">{entry.phrase} → {entry.replacement}</p>
                  <p className="text-[11px] font-bold text-lawn-muted">{entry.scope} · {entry.usage_count} {text.usesSuffix}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDelete(entry.id)}
                  className="border-2 border-lawn-border bg-lawn-panel px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-border"
                >
                  {text.deleteButton}
                </button>
              </article>
            ))}
            {entries.length === 0 ? <p className="text-sm font-bold text-lawn-muted">{text.noEntries}</p> : null}
          </div>
        </div>
      </section>
    </div>
  );
}
