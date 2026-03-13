import { useEffect, useState } from 'react';
import { RefreshCw, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { SettingCard } from './SettingCard';
import { RENDERER_STRINGS } from '../../strings/en';

type ProviderStatus = {
  available: boolean;
  error: string | null;
  response_time_ms: number | null;
};

type ProviderHealth = Record<string, ProviderStatus>;

export function ProviderHealthDisplay() {
  const text = RENDERER_STRINGS.settings.provider;
  const [health, setHealth] = useState<ProviderHealth | null>(null);
  const [loading, setLoading] = useState(false);

  async function checkHealth() {
    setLoading(true);
    try {
      const response = await window.openwisprDesktop.fetchJson('/api/providers/health');
      setHealth(response as ProviderHealth);
    } catch (error) {
      console.error('Failed to check provider health:', error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void checkHealth();
  }, []);

  const providers = [
    { key: 'ollama', label: text.ollama },
    { key: 'lm_studio', label: text.lmStudio },
    { key: 'llamacpp', label: text.llamaCpp },
  ];

  return (
    <SettingCard
      title={text.statusTitle}
      description={text.statusDescription}
    >
      <div className="space-y-3">
        {providers.map((provider) => {
          const status = health?.[provider.key];
          const isLoading = loading && !status;

          return (
            <div key={provider.key} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-stone-400" />
                ) : status?.available ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                <span className="text-sm font-medium">{provider.label}</span>
              </div>
              <div className="flex items-center gap-3">
                {status?.available && status.response_time_ms !== null && (
                  <span className="text-xs text-stone-500">
                    {text.responseTime}: {status.response_time_ms}ms
                  </span>
                )}
                {status?.error && !status.available && (
                  <span className="text-xs text-red-500 max-w-[150px] truncate" title={status.error}>
                    {status.error}
                  </span>
                )}
              </div>
            </div>
          );
        })}
        <button
          onClick={() => void checkHealth()}
          disabled={loading}
          className="mt-2 flex items-center gap-1 text-xs text-stone-500 hover:text-stone-700 disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          {text.refreshButton}
        </button>
      </div>
    </SettingCard>
  );
}
