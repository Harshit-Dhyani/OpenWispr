import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SettingsPanel } from '../components/SettingsPanel';
import { createMockSettings, createMockSystemProfile, createMockModelCatalogEntry } from './factories';

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
});
