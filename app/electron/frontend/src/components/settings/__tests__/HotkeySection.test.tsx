import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HotkeySection } from '../sections/HotkeySection';
import { createMockSettings, MOCK_DEVICES } from '../../../test/factories';

describe('HotkeySection', () => {
  it('hides unsupported record-on-start and stop-on-release toggles', () => {
    render(
      <HotkeySection
        settings={createMockSettings({
          hotkey: {
            enabled: true,
          },
        })}
        originalSettings={createMockSettings()}
        availableModels={[]}
        audioDevices={MOCK_DEVICES}
        availableLanguages={[]}
        isChanged={() => false}
        updateSetting={vi.fn()}
        resetSetting={vi.fn()}
      />,
    );

    expect(screen.queryByText('Record on Start')).not.toBeInTheDocument();
    expect(screen.queryByText('Stop on Release')).not.toBeInTheDocument();
    expect(screen.getByText('Hold Mode')).toBeInTheDocument();
  });
});
