import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { vi } from 'vitest';

// ============================================
// Global Test Configuration
// ============================================

// Global test timeout
vi.setConfig({ testTimeout: 10000 });

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// ============================================
// Electron API Mocks
// ============================================

export type MockElectronAPI = {
  fetchJson: ReturnType<typeof vi.fn>;
  chooseDirectory: ReturnType<typeof vi.fn>;
  choosePdf: ReturnType<typeof vi.fn>;
  onBackendExit: ReturnType<typeof vi.fn>;
  onOpenSettings: ReturnType<typeof vi.fn>;
  getApiOrigin: ReturnType<typeof vi.fn>;
  hotkey: {
    getState: ReturnType<typeof vi.fn>;
    toggle: ReturnType<typeof vi.fn>;
    updateConfig: ReturnType<typeof vi.fn>;
    onStateChange: ReturnType<typeof vi.fn>;
    removeStateChangeListener: ReturnType<typeof vi.fn>;
  };
  models: {
    download: ReturnType<typeof vi.fn>;
    cancel: ReturnType<typeof vi.fn>;
    remove: ReturnType<typeof vi.fn>;
    onDownloadEvent: ReturnType<typeof vi.fn>;
  };
  floatingWindow: {
    show: ReturnType<typeof vi.fn>;
    hide: ReturnType<typeof vi.fn>;
  };
};

export type MockFloatingAPI = {
  onRecordingState: ReturnType<typeof vi.fn>;
  onTranscription: ReturnType<typeof vi.fn>;
  onAudioVisualizer: ReturnType<typeof vi.fn>;
};

declare global {
  interface Window {
    transcriptaDesktop: MockElectronAPI;
    transcriptaFloating: MockFloatingAPI;
  }
}

// Create mock implementations
function createMockElectronAPI(): MockElectronAPI {
  return {
    fetchJson: vi.fn(),
    chooseDirectory: vi.fn(),
    choosePdf: vi.fn(),
    onBackendExit: vi.fn(() => vi.fn()),
    onOpenSettings: vi.fn(() => vi.fn()),
    getApiOrigin: vi.fn(() => Promise.resolve('http://127.0.0.1:8765')),
    hotkey: {
      getState: vi.fn(),
      toggle: vi.fn(),
      updateConfig: vi.fn(),
      onStateChange: vi.fn(() => vi.fn()),
      removeStateChangeListener: vi.fn(),
    },
    models: {
      download: vi.fn(),
      cancel: vi.fn(),
      remove: vi.fn(),
      onDownloadEvent: vi.fn(() => vi.fn()),
    },
    floatingWindow: {
      show: vi.fn(),
      hide: vi.fn(),
    },
  };
}

function createMockFloatingAPI(): MockFloatingAPI {
  return {
    onRecordingState: vi.fn(() => vi.fn()),
    onTranscription: vi.fn(() => vi.fn()),
    onAudioVisualizer: vi.fn(() => vi.fn()),
  };
}

// Setup mock implementations on window
Object.defineProperty(window, 'transcriptaDesktop', {
  writable: true,
  value: createMockElectronAPI(),
});

Object.defineProperty(window, 'transcriptaFloating', {
  writable: true,
  value: createMockFloatingAPI(),
});

// ============================================
// Browser API Mocks
// ============================================

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(),
  length: 0,
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock sessionStorage
const sessionStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(),
  length: 0,
};
Object.defineProperty(window, 'sessionStorage', {
  value: sessionStorageMock,
});

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock ResizeObserver
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
window.ResizeObserver = ResizeObserverMock;

// Mock IntersectionObserver
class IntersectionObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
window.IntersectionObserver = IntersectionObserverMock;

// Mock requestAnimationFrame and cancelAnimationFrame
window.requestAnimationFrame = vi.fn((callback: FrameRequestCallback) => {
  return setTimeout(callback, 16) as unknown as number;
}) as typeof window.requestAnimationFrame;

window.cancelAnimationFrame = vi.fn((id: number) => {
  clearTimeout(id);
}) as typeof window.cancelAnimationFrame;

// Mock MutationObserver
class MutationObserverMock {
  observe = vi.fn();
  disconnect = vi.fn();
  takeRecords = vi.fn().mockReturnValue([]);
}
window.MutationObserver = MutationObserverMock;

// Mock navigator APIs
Object.defineProperty(window.navigator, 'mediaDevices', {
  writable: true,
  value: {
    getUserMedia: vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }],
      getAudioTracks: () => [{
        getSettings: () => ({
          sampleRate: 48000,
          channelCount: 2,
        }),
      }],
    }),
    getDisplayMedia: vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }],
    }),
    enumerateDevices: vi.fn().mockResolvedValue([
      { deviceId: 'default', kind: 'audioinput', label: 'Default Microphone' },
      { deviceId: 'usb-mic', kind: 'audioinput', label: 'USB Microphone' },
    ]),
  },
});

// Mock AudioContext
class MockAudioContext {
  state: AudioContextState = 'suspended';
  sampleRate = 48000;
  currentTime = 0;
  destination = { maxChannelCount: 2 };
  onstatechange: ((this: AudioContext, ev: Event) => void) | null = null;

  resume = vi.fn().mockImplementation(() => {
    this.state = 'running';
    return Promise.resolve();
  });

  suspend = vi.fn().mockImplementation(() => {
    this.state = 'suspended';
    return Promise.resolve();
  });

  close = vi.fn().mockImplementation(() => {
    this.state = 'closed';
    return Promise.resolve();
  });

  createAnalyser = vi.fn().mockReturnValue({
    fftSize: 2048,
    frequencyBinCount: 1024,
    getByteFrequencyData: vi.fn(),
    getFloatFrequencyData: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  });

  createGain = vi.fn().mockReturnValue({
    gain: { value: 1, setTargetAtTime: vi.fn() },
    connect: vi.fn(),
    disconnect: vi.fn(),
  });

  createMediaStreamSource = vi.fn().mockReturnValue({
    connect: vi.fn(),
    disconnect: vi.fn(),
  });

  decodeAudioData = vi.fn().mockImplementation(() =>
    Promise.resolve({
      duration: 5,
      length: 240000,
      numberOfChannels: 2,
      sampleRate: 48000,
      getChannelData: vi.fn().mockReturnValue(new Float32Array(240000)),
    })
  );
}
window.AudioContext = MockAudioContext as unknown as typeof AudioContext;

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url = '';
  protocol = '';
  extensions = '';
  bufferedAmount = 0;
  binaryType: BinaryType = 'blob';

  onopen: ((this: WebSocket, ev: Event) => void) | null = null;
  onclose: ((this: WebSocket, ev: CloseEvent) => void) | null = null;
  onmessage: ((this: WebSocket, ev: MessageEvent) => void) | null = null;
  onerror: ((this: WebSocket, ev: Event) => void) | null = null;

  constructor(url: string | URL, protocols?: string | string[]) {
    this.url = url.toString();
    if (protocols) {
      this.protocol = Array.isArray(protocols) ? protocols[0] : protocols;
    }

    // Auto-connect after a short delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close(code = 1000, reason = ''): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code, reason }));
  }
}
window.WebSocket = MockWebSocket as unknown as typeof WebSocket;

// Mock EventSource
class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  readyState = MockEventSource.CONNECTING;
  url = '';
  withCredentials = false;

  onopen: ((this: EventSource, ev: Event) => void) | null = null;
  onmessage: ((this: EventSource, ev: MessageEvent) => void) | null = null;
  onerror: ((this: EventSource, ev: Event) => void) | null = null;

  constructor(url: string | URL) {
    this.url = url.toString();

    // Auto-connect after a short delay
    setTimeout(() => {
      this.readyState = MockEventSource.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  close(): void {
    this.readyState = MockEventSource.CLOSED;
  }

  addEventListener(type: string, listener: EventListener): void {
    // Simplified mock
  }

  removeEventListener(type: string, listener: EventListener): void {
    // Simplified mock
  }
}
window.EventSource = MockEventSource as unknown as typeof EventSource;

// ============================================
// Performance API Mock
// ============================================

Object.defineProperty(window, 'performance', {
  writable: true,
  value: {
    now: vi.fn().mockReturnValue(Date.now()),
    mark: vi.fn(),
    measure: vi.fn(),
    getEntriesByType: vi.fn().mockReturnValue([]),
    clearMarks: vi.fn(),
    clearMeasures: vi.fn(),
  },
});

// ============================================
// Console Suppression (optional)
// ============================================

const originalConsoleError = console.error;
console.error = (...args: unknown[]) => {
  const message = String(args[0]);
  // Suppress React 19 act() warnings and common test noise
  if (
    message.includes('act(') ||
    message.includes('Warning:') ||
    message.includes('ReactDOM.render is no longer supported') ||
    message.includes('not wrapped in act')
  ) {
    return;
  }
  originalConsoleError.apply(console, args);
};

const originalConsoleWarn = console.warn;
console.warn = (...args: unknown[]) => {
  const message = String(args[0]);
  // Suppress specific warnings during tests
  if (
    message.includes('React.createFactory') ||
    message.includes('componentWillReceiveProps')
  ) {
    return;
  }
  originalConsoleWarn.apply(console, args);
};

// ============================================
// Error Handlers
// ============================================

process.on('unhandledRejection', (reason) => {
  console.error('Unhandled Promise Rejection:', reason);
});

// ============================================
// Test Environment Helpers
// ============================================

// Helper to reset all mocks
export function resetAllMocks() {
  vi.clearAllMocks();

  // Reset Electron API mocks
  const electronApi = createMockElectronAPI();
  Object.assign(window.transcriptaDesktop, electronApi);

  // Reset Floating API mocks
  const floatingApi = createMockFloatingAPI();
  Object.assign(window.transcriptaFloating, floatingApi);

  // Clear storage
  localStorageMock.getItem.mockReturnValue(null);
  localStorageMock.setItem.mockClear();
  sessionStorageMock.getItem.mockReturnValue(null);
  sessionStorageMock.setItem.mockClear();
}

// Helper to simulate Electron API responses
export function mockElectronResponse(
  method: keyof MockElectronAPI,
  response: unknown,
  shouldReject = false
) {
  const api = window.transcriptaDesktop;

  if (method === 'fetchJson') {
    api.fetchJson.mockImplementation(() =>
      shouldReject ? Promise.reject(response) : Promise.resolve(response)
    );
  } else if (method === 'chooseDirectory') {
    api.chooseDirectory.mockResolvedValue(response);
  } else if (method === 'choosePdf') {
    api.choosePdf.mockResolvedValue(response);
  }
}

// Export setup utilities for test files
export { createMockElectronAPI, createMockFloatingAPI };
