/**
 * Test Utilities - Mock factories and test helpers
 * 
 * Provides mock implementations for WebSocket, Electron API, AudioContext,
 * media devices, and various test helper functions.
 */
import { vi } from 'vitest';
import type { Mock } from 'vitest';

// ============================================
// Mock WebSocket Server for Testing
// ============================================

export type WebSocketMessage = {
  type: string;
  payload: unknown;
  timestamp?: string;
  id?: string;
};

export class MockWebSocketServer {
  private listeners: Map<string, ((data: unknown) => void)[]> = new Map();
  private isOpen = false;
  private messageQueue: WebSocketMessage[] = [];
  private simulateErrors = false;

  constructor(private url: string) {}

  connect(): void {
    this.isOpen = true;
    this.emit('open', {});
  }

  disconnect(): void {
    this.isOpen = false;
    this.emit('close', { code: 1000, reason: 'Normal closure' });
  }

  on(event: string, callback: (data: unknown) => void): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);

    // Return unsubscribe function
    return () => this.off(event, callback);
  }

  off(event: string, callback: (data: unknown) => void): void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  emit(event: string, data: unknown): void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in event listener:', error);
        }
      });
    }
  }

  send(message: WebSocketMessage): void {
    if (!this.isOpen) {
      this.messageQueue.push(message);
      return;
    }
    this.emit('message', { data: JSON.stringify(message) });
  }

  sendToClient(message: WebSocketMessage): void {
    this.send(message);
  }

  flushQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        this.send(message);
      }
    }
  }

  simulateError(error: Error): void {
    this.simulateErrors = true;
    this.emit('error', error);
  }

  simulateConnectionFailure(): void {
    this.isOpen = false;
    this.emit('close', { code: 1006, reason: 'Abnormal closure' });
  }

  get isConnected(): boolean {
    return this.isOpen;
  }

  get queuedMessages(): WebSocketMessage[] {
    return [...this.messageQueue];
  }
}

// ============================================
// Mock Electron API Helpers
// ============================================

export type MockElectronAPI = {
  fetchJson: Mock<(...args: unknown[]) => Promise<unknown>>;
  chooseDirectory: Mock<() => Promise<string | null>>;
  choosePdf: Mock<() => Promise<string | null>>;
  onBackendExit: Mock<() => () => void>;
  onOpenSettings: Mock<() => () => void>;
  getApiOrigin: Mock<() => Promise<string>>;
  hotkey: {
    getState: Mock<() => Promise<unknown>>;
    toggle: Mock<(enabled: boolean) => Promise<void>>;
    updateConfig: Mock<(config: unknown) => Promise<void>>;
    onStateChange: Mock<() => () => void>;
    removeStateChangeListener: Mock<() => void>;
  };
  models: {
    download: Mock<(modelId: string) => Promise<void>>;
    cancel: Mock<(modelId: string) => Promise<void>>;
    remove: Mock<(modelId: string) => Promise<void>>;
    onDownloadEvent: Mock<() => () => void>;
  };
  floatingWindow: {
    show: Mock<() => Promise<void>>;
    hide: Mock<() => Promise<void>>;
  };
};

export function createMockElectronAPI(): MockElectronAPI {
  return {
    fetchJson: vi.fn().mockResolvedValue({}),
    chooseDirectory: vi.fn().mockResolvedValue('/mock/directory'),
    choosePdf: vi.fn().mockResolvedValue('/mock/file.pdf'),
    onBackendExit: vi.fn().mockReturnValue(vi.fn()),
    onOpenSettings: vi.fn().mockReturnValue(vi.fn()),
    getApiOrigin: vi.fn().mockResolvedValue('http://127.0.0.1:8765'),
    hotkey: {
      getState: vi.fn().mockResolvedValue({ config: { enabled: false } }),
      toggle: vi.fn().mockResolvedValue(undefined),
      updateConfig: vi.fn().mockResolvedValue(undefined),
      onStateChange: vi.fn().mockReturnValue(vi.fn()),
      removeStateChangeListener: vi.fn(),
    },
    models: {
      download: vi.fn().mockResolvedValue(undefined),
      cancel: vi.fn().mockResolvedValue(undefined),
      remove: vi.fn().mockResolvedValue(undefined),
      onDownloadEvent: vi.fn().mockReturnValue(vi.fn()),
    },
    floatingWindow: {
      show: vi.fn().mockResolvedValue(undefined),
      hide: vi.fn().mockResolvedValue(undefined),
    },
  };
}

export type MockFloatingAPI = {
  onRecordingState: Mock<() => () => void>;
  onTranscription: Mock<() => () => void>;
  onAudioVisualizer: Mock<() => () => void>;
};

export function createMockFloatingAPI(): MockFloatingAPI {
  return {
    onRecordingState: vi.fn().mockReturnValue(vi.fn()),
    onTranscription: vi.fn().mockReturnValue(vi.fn()),
    onAudioVisualizer: vi.fn().mockReturnValue(vi.fn()),
  };
}

// ============================================
// Mock Audio Context for Testing
// ============================================

export class MockAudioContext {
  state: AudioContextState = 'suspended';
  sampleRate = 48000;
  currentTime = 0;
  destination = { maxChannelCount: 2 };
  onstatechange: ((this: AudioContext, ev: Event) => void) | null = null;

  private eventListeners: Map<string, EventListener[]> = new Map();

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

  addEventListener(event: string, callback: EventListener): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)!.push(callback);
  }

  removeEventListener(event: string, callback: EventListener): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }
}

interface MockAnalyserNode {
  fftSize: number;
  frequencyBinCount: number;
  getByteFrequencyData: Mock;
  getFloatFrequencyData: Mock;
  connect: Mock;
  disconnect: Mock;
}

interface MockGainNode {
  gain: { value: number; setTargetAtTime: Mock };
  connect: Mock;
  disconnect: Mock;
}

interface MockMediaStreamAudioSourceNode {
  connect: Mock;
  disconnect: Mock;
}

interface MockAudioBuffer {
  duration: number;
  length: number;
  numberOfChannels: number;
  sampleRate: number;
  getChannelData: Mock;
}

// ============================================
// Mock Media Devices API
// ============================================

export type MockMediaDevice = {
  deviceId: string;
  kind: MediaDeviceKind;
  label: string;
  groupId?: string;
};

export function createMockMediaDevices(devices: MockMediaDevice[] = []) {
  const defaultDevices: MockMediaDevice[] = [
    { deviceId: 'default', kind: 'audioinput', label: 'Default Microphone' },
    { deviceId: 'usb-mic', kind: 'audioinput', label: 'USB Microphone' },
  ];

  const allDevices = devices.length > 0 ? devices : defaultDevices;

  return {
    getUserMedia: vi.fn().mockResolvedValue({
      getTracks: () => [
        {
          stop: vi.fn(),
          kind: 'audio',
          label: 'Mock Microphone',
          enabled: true,
        },
      ],
      getAudioTracks: () => [
        {
          getSettings: () => ({
            sampleRate: 48000,
            channelCount: 2,
            echoCancellation: true,
            noiseSuppression: true,
          }),
        },
      ],
    }),
    getDisplayMedia: vi.fn().mockResolvedValue({
      getTracks: () => [
        {
          stop: vi.fn(),
          kind: 'video',
          label: 'Screen',
        },
      ],
    }),
    enumerateDevices: vi.fn().mockResolvedValue(allDevices),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
}

// ============================================
// Timing Utilities
// ============================================

export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export async function waitFor(
  callback: () => boolean | void,
  timeout = 5000,
  interval = 10
): Promise<void> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    try {
      const result = callback();
      if (result !== false) {
        return;
      }
    } catch {
      // Ignore errors during polling
    }
    await sleep(interval);
  }

  throw new Error(`waitFor timeout after ${timeout}ms`);
}

// ============================================
// Async Test Helpers
// ============================================

export function flushPromises(): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, 0));
}

export async function actAndFlush(callback: () => void | Promise<void>): Promise<void> {
  await callback();
  await flushPromises();
}

export async function waitForPromises(count = 1): Promise<void> {
  for (let i = 0; i < count; i++) {
    await flushPromises();
  }
}

// ============================================
// Event Simulation Helpers
// ============================================

export function createMockKeyboardEvent(init: Partial<KeyboardEventInit> = {}): KeyboardEvent {
  return new KeyboardEvent('keydown', {
    key: 'Space',
    code: 'Space',
    ctrlKey: true,
    shiftKey: true,
    altKey: false,
    metaKey: false,
    bubbles: true,
    cancelable: true,
    ...init,
  });
}

export function createMockMouseEvent(type: string, init: Partial<MouseEventInit> = {}): MouseEvent {
  return new MouseEvent(type, {
    bubbles: true,
    cancelable: true,
    clientX: 0,
    clientY: 0,
    ...init,
  });
}

export function createMockChangeEvent(value: string): Event {
  const event = new Event('change', { bubbles: true });
  Object.defineProperty(event, 'target', {
    writable: false,
    value: { value },
  });
  return event;
}

export function createMockInputEvent(value: string): Event {
  const event = new Event('input', { bubbles: true });
  Object.defineProperty(event, 'target', {
    writable: false,
    value: { value },
  });
  return event;
}

// ============================================
// Assert Helpers
// ============================================

export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${value}`);
}

export function isDefined<T>(value: T | undefined | null): value is T {
  return value !== undefined && value !== null;
}

export function expectToBeDefined<T>(value: T | undefined | null): asserts value is T {
  if (value === undefined || value === null) {
    throw new Error('Expected value to be defined');
  }
}

// ============================================
// Mock Response Helpers
// ============================================

export function createMockResponse<T>(
  data: T,
  status = 200,
  statusText = 'OK'
): Response {
  return new Response(JSON.stringify(data), {
    status,
    statusText,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function createMockErrorResponse(
  message: string,
  status = 500,
  statusText = 'Internal Server Error'
): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    statusText,
    headers: { 'Content-Type': 'application/json' },
  });
}

// ============================================
// Storage Helpers
// ============================================

export function mockLocalStorage(data: Record<string, string>): void {
  Object.keys(data).forEach(key => {
    localStorage.setItem(key, data[key]);
  });
}

export function clearMockStorage(): void {
  localStorage.clear();
  sessionStorage.clear();
}

// ============================================
// Network Helpers
// ============================================

export function mockFetch(response: Response | ((url: string, init?: RequestInit) => Response)): void {
  global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    if (typeof response === 'function') {
      return Promise.resolve(response(url, init));
    }
    return Promise.resolve(response);
  });
}

export function resetFetch(): void {
  vi.restoreAllMocks();
}

// ============================================
// Component Testing Helpers
// ============================================

export function createMockIntersectionObserver(options: {
  isIntersecting?: boolean;
  intersectionRatio?: number;
} = {}) {
  const { isIntersecting = true, intersectionRatio = 1 } = options;

  return class {
    root: Element | null = null;
    rootMargin = '0px';
    thresholds = [0];

    observe = vi.fn((element: Element) => {
      // Simulate immediate intersection
      setTimeout(() => {
        const entries = [{
          boundingClientRect: element.getBoundingClientRect(),
          intersectionRatio,
          intersectionRect: element.getBoundingClientRect(),
          isIntersecting,
          rootBounds: null,
          target: element,
          time: Date.now(),
        }];
        // Find and call callback
        const callback = (this as unknown as { callback?: (entries: IntersectionObserverEntry[]) => void }).callback;
        if (callback) {
          callback(entries as IntersectionObserverEntry[]);
        }
      }, 0);
    });

    unobserve = vi.fn();
    disconnect = vi.fn();
    takeRecords = vi.fn().mockReturnValue([]);
  };
}

// ============================================
// Export Everything
// ============================================

export { vi };
