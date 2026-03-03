import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Sidebar } from '../Sidebar';
import { createMockDevice, createMockHealth, createMockModelCatalogEntry } from '../../test/factories';
import type { Device } from '../../types/api';

describe('Sidebar', () => {
  const mockDevices: Device[] = [
    createMockDevice({ id: 'mic-1', name: 'Built-in Microphone', is_loopback: false }),
    createMockDevice({ id: 'loopback-1', name: 'System Audio', is_loopback: true, supports_loopback: true }),
  ];

  const defaultProps = {
    form: {
      sessionTitle: 'Test Session',
      captureMode: 'system' as const,
      deviceId: 'loopback-1',
      modelName: 'small',
      languageMode: 'en',
      liveMode: 'balanced',
      executionMode: 'auto',
      exportRoot: 'sessions',
    },
    devices: mockDevices,
    models: [
      createMockModelCatalogEntry({ id: 'tiny', display_name: 'Tiny', installed: true }),
      createMockModelCatalogEntry({ id: 'small', display_name: 'Small', installed: true, recommended: true }),
    ],
    languages: ['auto', 'en', 'es', 'fr'],
    liveModes: ['realtime', 'low_latency', 'balanced', 'high_accuracy'],
    executionModes: ['auto', 'gpu_only', 'cpu_only'],
    backendReady: true,
    sessionStatus: 'idle',
    health: createMockHealth(),
    meterValue: 0.5,
    statusMessage: 'Ready',
    busy: false,
    modelLoading: false,
    preloadStatus: { loading: false, progress: 0, message: '' },
    connectionStatus: 'sse-connected' as const,
    gpuStatus: 'gpu-active' as const,
    onFieldChange: vi.fn(),
    onRefreshDevices: vi.fn(),
    onChooseDirectory: vi.fn(),
    onPreloadModel: vi.fn(),
    onStart: vi.fn(),
    onStop: vi.fn(),
    onAttachPdf: vi.fn(),
    onOpenSettings: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders sidebar with session setup section', () => {
    render(<Sidebar {...defaultProps} />);
    
    expect(screen.getByText('Session Setup')).toBeInTheDocument();
    expect(screen.getByText('Local Transcription')).toBeInTheDocument();
    expect(screen.getByText('Transcripta')).toBeInTheDocument();
  });

  it('displays ready status when backend is ready', () => {
    render(<Sidebar {...defaultProps} />);
    
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });

  it('displays error status when health has error', () => {
    render(<Sidebar {...defaultProps} health={createMockHealth({ last_error: 'Test error' })} />);
    
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('calls onOpenSettings when settings button is clicked', () => {
    render(<Sidebar {...defaultProps} />);
    
    const settingsButton = screen.getByTitle('Open Settings');
    fireEvent.click(settingsButton);
    
    expect(defaultProps.onOpenSettings).toHaveBeenCalled();
  });

  it('calls onFieldChange when session title is changed', () => {
    render(<Sidebar {...defaultProps} />);
    
    const titleInput = screen.getByPlaceholderText('Study Session');
    fireEvent.change(titleInput, { target: { value: 'New Session' } });
    
    expect(defaultProps.onFieldChange).toHaveBeenCalledWith('sessionTitle', 'New Session');
  });

  it('switches capture mode when buttons are clicked', () => {
    render(<Sidebar {...defaultProps} />);
    
    const micButton = screen.getByText('Microphone');
    fireEvent.click(micButton);
    
    expect(defaultProps.onFieldChange).toHaveBeenCalledWith('captureMode', 'microphone');
  });

  it('calls onRefreshDevices when refresh button is clicked', () => {
    render(<Sidebar {...defaultProps} />);
    
    const refreshButton = screen.getByTitle('Refresh devices');
    fireEvent.click(refreshButton);
    
    expect(defaultProps.onRefreshDevices).toHaveBeenCalled();
  });

  it('calls onStart when start button is clicked', () => {
    render(<Sidebar {...defaultProps} />);
    
    const startButton = screen.getByText('Start');
    fireEvent.click(startButton);
    
    expect(defaultProps.onStart).toHaveBeenCalled();
  });

  it('calls onStop when stop button is clicked', () => {
    render(<Sidebar {...defaultProps} sessionStatus="running" />);
    
    const stopButton = screen.getByText('Stop');
    fireEvent.click(stopButton);
    
    expect(defaultProps.onStop).toHaveBeenCalled();
  });

  it('disables start button when session is running', () => {
    render(<Sidebar {...defaultProps} sessionStatus="running" />);
    
    const startButton = screen.getByText('Start');
    expect(startButton).toBeDisabled();
  });

  it('disables stop button when session is idle', () => {
    render(<Sidebar {...defaultProps} sessionStatus="idle" />);
    
    const stopButton = screen.getByText('Stop');
    expect(stopButton).toBeDisabled();
  });

  it('shows model loading state', () => {
    render(<Sidebar {...defaultProps} modelLoading={true} />);
    
    expect(screen.getByText('Loading Model...')).toBeInTheDocument();
  });

  it('shows preload progress when preloading', () => {
    render(<Sidebar {...defaultProps} preloadStatus={{ loading: true, progress: 50, message: 'Loading...' }} />);
    
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('calls onPreloadModel when preload button is clicked', () => {
    render(<Sidebar {...defaultProps} />);
    
    const preloadButton = screen.getByText('Preload');
    fireEvent.click(preloadButton);
    
    expect(defaultProps.onPreloadModel).toHaveBeenCalled();
  });

  it('displays connection badge correctly', () => {
    render(<Sidebar {...defaultProps} connectionStatus="sse-connected" />);
    
    expect(screen.getByText('SSE Connected')).toBeInTheDocument();
  });

  it('displays GPU badge correctly', () => {
    render(<Sidebar {...defaultProps} gpuStatus="gpu-active" />);
    
    expect(screen.getByText('GPU Active')).toBeInTheDocument();
  });

  it('shows device test button', () => {
    render(<Sidebar {...defaultProps} />);
    
    expect(screen.getByText('Device Test')).toBeInTheDocument();
  });

  it('displays runtime metrics', () => {
    render(<Sidebar {...defaultProps} />);
    
    expect(screen.getByText('Runtime')).toBeInTheDocument();
    expect(screen.getByText('GPU')).toBeInTheDocument();
    expect(screen.getByText('Queue')).toBeInTheDocument();
  });

  it('calls onAttachPdf when attach PDF button is clicked', () => {
    render(<Sidebar {...defaultProps} />);
    
    const attachButton = screen.getByText('Attach PDF Context');
    fireEvent.click(attachButton);
    
    expect(defaultProps.onAttachPdf).toHaveBeenCalled();
  });

  it('displays input level meter', () => {
    render(<Sidebar {...defaultProps} meterValue={0.75} />);
    
    expect(screen.getByText('Input Level')).toBeInTheDocument();
  });

  it('displays backpressure information', () => {
    render(<Sidebar {...defaultProps} />);
    
    expect(screen.getByText('Backpressure')).toBeInTheDocument();
    expect(screen.getByText('normal')).toBeInTheDocument();
  });

  it('shows warning when health has warning', () => {
    render(<Sidebar {...defaultProps} health={createMockHealth({ last_warning: 'Test warning' })} />);
    
    expect(screen.getByText('Warning')).toBeInTheDocument();
    expect(screen.getByText('Test warning')).toBeInTheDocument();
  });
});
