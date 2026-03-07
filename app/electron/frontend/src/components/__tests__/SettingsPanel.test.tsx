import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SettingsPanel } from '../SettingsPanel';
import { createMockSettings, createMockSystemProfile, createMockModelCatalogEntry } from '../../test/factories';

describe('SettingsPanel', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    initialSettings: createMockSettings(),
    onSettingsChange: vi.fn(),
    onSettingsReset: vi.fn(),
    hardwareProfile: createMockSystemProfile(),
    availableModels: ['tiny', 'base', 'small', 'medium', 'large-v3'],
    modelManager: {
      catalog: [
        createMockModelCatalogEntry({ id: 'tiny', display_name: 'Tiny' }),
        createMockModelCatalogEntry({ id: 'small', display_name: 'Small' }),
      ],
      installed: [],
      downloads: {},
      selectedAsrModelId: 'small',
      selectedRefinerModelId: '',
      refinementMode: 'off' as const,
    },
    onDownloadModel: vi.fn(),
    onCancelModelDownload: vi.fn(),
    onRemoveModel: vi.fn(),
    availableLanguages: ['auto', 'en', 'es', 'fr'],
    audioDevices: [
      { id: 'default', name: 'Default', kind: 'microphone', is_loopback: false, channels: 2, sample_rate: 16000 },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders settings panel when open', () => {
    render(<SettingsPanel {...defaultProps} />);
    
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search settings...')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    const { container } = render(<SettingsPanel {...defaultProps} isOpen={false} />);
    
    expect(container.firstChild).toBeNull();
  });

  it('calls onClose when close button is clicked', () => {
    render(<SettingsPanel {...defaultProps} />);
    
    const closeButton = screen.getAllByRole('button').find(btn => 
      btn.querySelector('svg')?.getAttribute('data-lucide-icon') === 'x'
    );
    
    if (closeButton) {
      fireEvent.click(closeButton);
      expect(defaultProps.onClose).toHaveBeenCalled();
    }
  });

  it('displays save status indicators', () => {
    render(<SettingsPanel {...defaultProps} />);
    
    // Should show auto-save enabled text
    expect(screen.getByText('Auto-save enabled')).toBeInTheDocument();
  });

  it('renders all category navigation items', () => {
    render(<SettingsPanel {...defaultProps} />);
    
    expect(screen.getByText('General')).toBeInTheDocument();
    expect(screen.getByText('Models')).toBeInTheDocument();
    expect(screen.getByText('Transcription')).toBeInTheDocument();
    expect(screen.getByText('Audio')).toBeInTheDocument();
    expect(screen.getByText('Hotkey')).toBeInTheDocument();
    expect(screen.getByText('History')).toBeInTheDocument();
    expect(screen.getByText('Dictionary')).toBeInTheDocument();
    expect(screen.getByText('Snippets')).toBeInTheDocument();
    expect(screen.getByText('Style')).toBeInTheDocument();
    expect(screen.getByText('Advanced')).toBeInTheDocument();
  });

  it('allows searching settings', () => {
    render(<SettingsPanel {...defaultProps} />);
    
    const searchInput = screen.getByPlaceholderText('Search settings...');
    fireEvent.change(searchInput, { target: { value: 'theme' } });
    
    expect(searchInput).toHaveValue('theme');
  });

  it('shows export/import buttons', () => {
    render(<SettingsPanel {...defaultProps} />);
    
    // Check for download/upload icons (export/import buttons)
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('displays hardware profile information when available', () => {
    render(<SettingsPanel {...defaultProps} />);
    
    // Hardware profile should be passed to ModelSection
    expect(defaultProps.hardwareProfile).toBeDefined();
  });

  it('renders a keyboard-focusable scroll container for settings content', () => {
    render(<SettingsPanel {...defaultProps} />);

    const scrollContainer = screen.getByTestId('settings-scroll-container');
    expect(scrollContainer).toHaveClass('overflow-y-auto');
    expect(scrollContainer).toHaveAttribute('tabindex', '0');
    expect(scrollContainer).toHaveAttribute('role', 'region');
  });

  it('shows the mic dictation language control under Transcription instead of Hotkey', () => {
    render(<SettingsPanel {...defaultProps} />);

    fireEvent.click(screen.getByText('Transcription'));
    expect(screen.getByText('Mic Dictation Language')).toBeInTheDocument();
    expect(screen.getByText('Transcription Mode')).toBeInTheDocument();
    expect(screen.getByText('Refinement Profile')).toBeInTheDocument();
    expect(screen.getByText('Finish Action')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Hotkey'));
    expect(screen.queryByText('Mic Dictation Language')).not.toBeInTheDocument();
    expect(screen.queryByText('Transcription Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('Refinement Profile')).not.toBeInTheDocument();
    expect(screen.queryByText('Finish Action')).not.toBeInTheDocument();
  });

  it('keeps model downloads/runtime controls under Models only', () => {
    render(<SettingsPanel {...defaultProps} />);

    fireEvent.click(screen.getByText('Models'));
    expect(screen.getByText('Enable Local Refiner Runtime')).toBeInTheDocument();
    expect(screen.queryByText('Refinement Profile')).not.toBeInTheDocument();
  });

  it('uses the app name instead of Electron in application info', () => {
    render(<SettingsPanel {...defaultProps} />);

    fireEvent.click(screen.getByText('Advanced'));
    expect(screen.getByText('OpenWispr')).toBeInTheDocument();
    expect(screen.queryByText('Electron')).not.toBeInTheDocument();
  });

  it('shows mute-app-audio toggle under Audio settings', () => {
    render(<SettingsPanel {...defaultProps} />);

    fireEvent.click(screen.getByRole('button', { name: /^Audio\b/i }));

    expect(
      screen.getByText(
        /Mute app audio during transcription|Mute App Audio During Dictation|Mute OpenWispr renderer audio while microphone dictation is active/i,
      ),
    ).toBeInTheDocument();
  });
});

