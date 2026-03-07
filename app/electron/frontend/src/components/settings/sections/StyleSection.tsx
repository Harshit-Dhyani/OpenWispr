import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, Paintbrush, Sparkles } from 'lucide-react';
import { SectionHeader } from '../SectionHeader';
import { SettingCard } from '../SettingCard';
import { Select, Toggle } from '../controls';
import type { SectionProps } from '../types';
import type { StyleAssignments, StyleProfile } from '../../../types/api';
import { RENDERER_STRINGS } from '../../../strings/en';

type StyleContext = 'personal' | 'work' | 'email' | 'other';

function serializeRules(rules: Record<string, unknown>) {
  return JSON.stringify(rules, null, 2);
}

export function StyleSection({ settings, isChanged, updateSetting, resetSetting, request }: SectionProps) {
  const text = RENDERER_STRINGS.settings.style;
  const [profiles, setProfiles] = useState<StyleProfile[]>([]);
  const [assignments, setAssignments] = useState<StyleAssignments>({});
  const [context, setContext] = useState<StyleContext>('personal');
  const [previewInput, setPreviewInput] = useState<string>(text.defaultPreviewInput);
  const [previewOutput, setPreviewOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [newName, setNewName] = useState('');
  const [newKey, setNewKey] = useState('custom');
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editStyleKey, setEditStyleKey] = useState('custom');
  const [editEnabled, setEditEnabled] = useState(true);
  const [editRules, setEditRules] = useState('{}');
  const [editMessage, setEditMessage] = useState<string | null>(null);

  const backendRequest = useCallback(
    async <T,>(path: string, options?: RequestInit): Promise<T> => {
      if (request) {
        return request<T>(path, options);
      }
      return window.openwisprDesktop.fetchJson(path, options) as Promise<T>;
    },
    [request],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await backendRequest<{ profiles: StyleProfile[]; assignments: StyleAssignments }>('/api/style/profiles');
      setProfiles(response.profiles);
      setAssignments(response.assignments);
      setSelectedProfileId((current) => current ?? response.profiles[0]?.id ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : text.loadError);
    } finally {
      setLoading(false);
    }
  }, [backendRequest, text.loadError]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeProfileId = assignments[context];
  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.id === activeProfileId) ?? null,
    [activeProfileId, profiles],
  );
  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId],
  );

  useEffect(() => {
    if (!selectedProfile) {
      setEditName('');
      setEditDescription('');
      setEditStyleKey('custom');
      setEditEnabled(true);
      setEditRules('{}');
      setEditMessage(null);
      return;
    }
    setEditName(selectedProfile.name);
    setEditDescription(selectedProfile.description);
    setEditStyleKey(selectedProfile.style_key);
    setEditEnabled(selectedProfile.enabled);
    setEditRules(serializeRules(selectedProfile.rules));
    setEditMessage(null);
  }, [selectedProfile]);

  async function assignProfile(profileId: string) {
    try {
      const response = await backendRequest<{ assignments: StyleAssignments }>('/api/style/assignments', {
        method: 'POST',
        body: JSON.stringify({ context, profile_id: profileId }),
      });
      setAssignments(response.assignments);
      setError(null);
    } catch (assignError) {
      setError(assignError instanceof Error ? assignError.message : text.assignmentError);
    }
  }

  async function runPreview(profileId?: string) {
    try {
      const response = await backendRequest<{ output_text: string }>('/api/style/preview', {
        method: 'POST',
        body: JSON.stringify({
          text: previewInput,
          context,
          profile_id: profileId,
        }),
      });
      setPreviewOutput(response.output_text);
      setError(null);
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : text.previewError);
    }
  }

  async function createProfile() {
    if (!newName.trim()) {
      return;
    }
    try {
      await backendRequest('/api/style/profiles', {
        method: 'POST',
        body: JSON.stringify({
          name: newName,
          style_key: newKey,
          description: text.customDescription(newName),
          rules: {},
          enabled: true,
        }),
      });
      setNewName('');
      setNewKey('custom');
      await load();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : text.createError);
    }
  }

  async function saveProfile() {
    if (!selectedProfileId) {
      return;
    }
    try {
      const parsedRules = JSON.parse(editRules || '{}') as Record<string, unknown>;
      await backendRequest(`/api/style/profiles/${encodeURIComponent(selectedProfileId)}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: editName,
          description: editDescription,
          style_key: editStyleKey,
          enabled: editEnabled,
          rules: parsedRules,
        }),
      });
      setEditMessage(text.savedMessage);
      setError(null);
      await load();
    } catch (saveError) {
      setEditMessage(saveError instanceof Error ? saveError.message : text.invalidRules);
    }
  }

  async function deleteProfile(profileId: string) {
    try {
      await backendRequest(`/api/style/profiles/${encodeURIComponent(profileId)}`, { method: 'DELETE' });
      await load();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : text.deleteError);
    }
  }

  const toneEnabled = settings.style.style_apply_enabled;

  return (
    <div className="space-y-6">
      <SectionHeader title={text.title} icon={Paintbrush} description={text.description} />

      <div className="grid gap-4">
        <SettingCard
          title={text.enableTitle}
          description={text.enableDescription}
          changed={isChanged('style', 'style_apply_enabled')}
          onReset={() => resetSetting('style', 'style_apply_enabled')}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs text-stone-500">{toneEnabled ? text.enableHint : text.disabledHint}</div>
            <Toggle
              checked={toneEnabled}
              onChange={(value) => updateSetting('style', 'style_apply_enabled', value)}
            />
          </div>
        </SettingCard>

        <SettingCard
          title={text.defaultProfileTitle}
          description={text.defaultProfileDescription}
          changed={isChanged('style', 'style_default_profile')}
          onReset={() => resetSetting('style', 'style_default_profile')}
        >
          <Select
            value={settings.style.style_default_profile}
            options={[...text.defaultProfileOptions]}
            onChange={(value) => updateSetting('style', 'style_default_profile', value)}
          />
        </SettingCard>

        <SettingCard title={text.contextTitle} description={text.contextDescription}>
          <div className="flex flex-wrap gap-2">
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
                {text.contextOptions[item]}
              </button>
            ))}
          </div>
          <div className="mt-3 text-sm font-bold text-lawn-border">
            {text.activeProfileLabel}: {activeProfile?.name || text.none}
          </div>
        </SettingCard>

        <SettingCard title={text.previewTitle} description={text.previewDescription}>
          <textarea
            value={previewInput}
            onChange={(event) => setPreviewInput(event.target.value)}
            rows={4}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none focus:border-lawn-accent"
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void runPreview(activeProfileId)}
              className="border-2 border-lawn-border bg-lawn-dark px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
            >
              {text.previewButton}
            </button>
            {loading ? <span className="text-xs font-bold text-stone-500">{text.loading}</span> : null}
            {error ? <span className="text-xs font-bold text-theme-error">{error}</span> : null}
          </div>
          <div className="mt-3 border-2 border-lawn-border bg-lawn-panel px-3 py-3 text-sm font-bold text-lawn-border">
            {previewOutput || text.noPreview}
          </div>
        </SettingCard>

        <SettingCard title={text.libraryTitle} description={text.libraryDescription}>
          <div className="space-y-2">
            {profiles.map((profile) => (
              <article key={profile.id} className="flex flex-wrap items-center justify-between gap-3 border-2 border-lawn-border bg-lawn-bg p-3">
                <button
                  type="button"
                  onClick={() => setSelectedProfileId(profile.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <p className="text-sm font-black text-lawn-border">{profile.name}</p>
                  <p className="text-[11px] font-bold text-lawn-muted">{profile.style_key} · {profile.description}</p>
                </button>
                <div className="flex flex-wrap gap-2">
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
            {!profiles.length && !loading ? (
              <p className="text-sm font-bold text-stone-500">{text.emptyLibrary}</p>
            ) : null}
          </div>
        </SettingCard>

        <div className="border-2 border-lawn-border bg-lawn-panel p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="flex items-center gap-2 text-sm font-bold text-lawn-border">
                <Sparkles className="h-4 w-4 text-lawn-accent" />
                {text.advancedTitle}
              </h4>
              <p className="mt-1 text-xs text-stone-500">{text.advancedDescription}</p>
            </div>
            <button
              type="button"
              onClick={() => setShowAdvanced((value) => !value)}
              className="border-2 border-lawn-border bg-lawn-bg px-3 py-1 text-xs font-bold uppercase text-lawn-border hover:bg-lawn-accent hover:text-lawn-bg"
            >
              <span className="inline-flex items-center gap-2">
                {showAdvanced ? text.hideAdvanced : text.showAdvanced}
                {showAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </span>
            </button>
          </div>
        </div>

        {showAdvanced ? (
          <>
            <SettingCard title={text.createTitle} description={text.createDescription}>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_180px_auto]">
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
                  className="border-2 border-lawn-accent bg-lawn-accent px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-lawn-bg"
                >
                  {text.addButton}
                </button>
              </div>
            </SettingCard>

            <SettingCard title={text.editorTitle} description={text.editorDescription}>
              {selectedProfile ? (
                <div className="grid gap-3">
                  <input
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                    className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                  />
                  <input
                    value={editDescription}
                    onChange={(event) => setEditDescription(event.target.value)}
                    className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                  />
                  <select
                    value={editStyleKey}
                    onChange={(event) => setEditStyleKey(event.target.value)}
                    className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold text-lawn-border outline-none"
                  >
                    <option value="formal">formal</option>
                    <option value="casual">casual</option>
                    <option value="very_casual">very_casual</option>
                    <option value="custom">custom</option>
                  </select>
                  <label className="flex items-center gap-2 text-sm font-bold text-lawn-border">
                    <input type="checkbox" checked={editEnabled} onChange={(event) => setEditEnabled(event.target.checked)} />
                    {text.enabledCheckbox}
                  </label>
                  <textarea
                    value={editRules}
                    onChange={(event) => setEditRules(event.target.value)}
                    rows={10}
                    className="border-2 border-lawn-border bg-lawn-bg px-3 py-2 font-mono text-xs font-bold text-lawn-border outline-none"
                  />
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={() => void saveProfile()}
                      className="border-2 border-lawn-accent bg-lawn-accent px-3 py-2 text-xs font-black uppercase tracking-[0.1em] text-lawn-bg"
                    >
                      {text.saveButton}
                    </button>
                    {editMessage ? <span className="text-xs font-bold text-stone-500">{editMessage}</span> : null}
                  </div>
                </div>
              ) : (
                <p className="text-sm font-bold text-stone-500">{text.selectProfile}</p>
              )}
            </SettingCard>
          </>
        ) : null}
      </div>
    </div>
  );
}

