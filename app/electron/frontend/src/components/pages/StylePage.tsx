import { useCallback, useEffect, useMemo, useState } from 'react';
import type { StyleAssignments, StyleProfile } from '../../types/api';
import { RENDERER_STRINGS } from '../../strings/en';

type StylePageProps = {
  request: <T>(path: string, options?: RequestInit) => Promise<T>;
  enabled: boolean;
};

type StyleContext = 'personal' | 'work' | 'email' | 'other';

export function StylePage({ request, enabled }: StylePageProps) {
  const text = RENDERER_STRINGS.pages.style;
  const [profiles, setProfiles] = useState<StyleProfile[]>([]);
  const [assignments, setAssignments] = useState<StyleAssignments>({});
  const [context, setContext] = useState<StyleContext>('personal');
  const [previewInput, setPreviewInput] = useState<string>(text.defaultPreviewInput);
  const [previewOutput, setPreviewOutput] = useState('');
  const [newName, setNewName] = useState('');
  const [newKey, setNewKey] = useState('custom');

  const load = useCallback(async () => {
    const response = await request<{ profiles: StyleProfile[]; assignments: StyleAssignments }>('/api/style/profiles');
    setProfiles(response.profiles);
    setAssignments(response.assignments);
  }, [request]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeProfileId = assignments[context];
  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.id === activeProfileId) ?? null,
    [activeProfileId, profiles],
  );

  async function assignProfile(profileId: string) {
    const response = await request<{ assignments: StyleAssignments }>('/api/style/assignments', {
      method: 'POST',
      body: JSON.stringify({ context, profile_id: profileId }),
    });
    setAssignments(response.assignments);
  }

  async function runPreview(profileId?: string) {
    const response = await request<{ output_text: string }>('/api/style/preview', {
      method: 'POST',
      body: JSON.stringify({
        text: previewInput,
        context,
        profile_id: profileId,
      }),
    });
    setPreviewOutput(response.output_text);
  }

  async function createProfile() {
    if (!newName.trim()) return;
    await request('/api/style/profiles', {
      method: 'POST',
      body: JSON.stringify({
        name: newName,
        style_key: newKey,
        description: `${newName} profile`,
        rules: {},
        enabled: true,
      }),
    });
    setNewName('');
    setNewKey('custom');
    await load();
  }

  async function deleteProfile(profileId: string) {
    await request(`/api/style/profiles/${encodeURIComponent(profileId)}`, { method: 'DELETE' });
    await load();
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden p-4">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-3xl uppercase tracking-tight text-lawn-border">{text.title}</h2>
          <p className="text-xs font-bold text-lawn-muted">{text.subtitle}</p>
        </div>
        <div className="text-xs font-black uppercase tracking-[0.1em] text-lawn-muted">
          {enabled ? text.enabled : text.disabled}
        </div>
      </div>

      <section className="mb-3 border-2 border-lawn-border bg-lawn-panel p-3">
        <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.contextTitle}</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {(['personal', 'work', 'email', 'other'] as StyleContext[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setContext(item)}
              className={[
                'border-2 px-3 py-2 text-xs font-black uppercase tracking-[0.1em]',
                context === item ? 'border-lawn-accent bg-lawn-accent text-lawn-bg' : 'border-lawn-border bg-lawn-bg text-lawn-border',
              ].join(' ')}
            >
              {item}
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm font-bold text-lawn-border">
          {text.activeProfile}: {activeProfile?.name || text.none}
        </p>
      </section>

      <section className="mb-3 border-2 border-lawn-border bg-lawn-panel p-3">
        <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.previewTitle}</h3>
        <textarea
          value={previewInput}
          onChange={(event) => setPreviewInput(event.target.value)}
          rows={4}
          className="mt-2 w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
        />
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={() => void runPreview(activeProfileId)}
            className="border-2 border-lawn-border bg-lawn-dark px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
          >
            {text.previewButton}
          </button>
        </div>
        <p className="mt-2 text-sm font-bold text-lawn-border">{previewOutput || text.noPreview}</p>
      </section>

      <section className="mb-3 border-2 border-lawn-border bg-lawn-panel p-3">
        <h3 className="text-[10px] font-black uppercase tracking-[0.14em] text-lawn-muted">{text.createTitle}</h3>
        <div className="mt-2 grid gap-2 md:grid-cols-[1fr_180px_auto]">
          <input
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder={text.profileNamePlaceholder}
            className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          />
          <select
            value={newKey}
            onChange={(event) => setNewKey(event.target.value)}
            className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
          >
            <option value="formal">formal</option>
            <option value="casual">casual</option>
            <option value="very_casual">very_casual</option>
            <option value="custom">custom</option>
          </select>
          <button
            type="button"
            onClick={() => void createProfile()}
            className="border-2 border-lawn-accent bg-lawn-accent px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
          >
            {text.addButton}
          </button>
        </div>
      </section>

      <section className="min-h-0 flex-1 overflow-hidden border-2 border-lawn-border bg-lawn-panel">
        <div className="h-full overflow-y-auto p-3 custom-scrollbar">
          <div className="space-y-2">
            {profiles.map((profile) => (
              <article key={profile.id} className="flex flex-wrap items-center justify-between gap-3 border-2 border-lawn-border bg-lawn-bg p-3">
                <div>
                  <p className="text-sm font-black text-lawn-border">{profile.name}</p>
                  <p className="text-[11px] font-bold text-lawn-muted">{profile.style_key} · {profile.description}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => void assignProfile(profile.id)}
                    className="border-2 border-lawn-border bg-lawn-panel px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-border"
                  >
                    {text.setActiveButton}
                  </button>
                  {!profile.built_in ? (
                    <button
                      type="button"
                      onClick={() => void deleteProfile(profile.id)}
                      className="border-2 border-lawn-border bg-lawn-panel px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-border"
                    >
                      {text.deleteButton}
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
