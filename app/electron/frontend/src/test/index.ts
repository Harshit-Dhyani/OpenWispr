// Test utilities exports
export * from './factories';
export { flushPromises, actAndFlush, waitForPromises, sleep, waitFor as waitForCondition } from './utils';

// Re-export for convenience
export { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
export { vi, describe, it, expect, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

// Type exports for convenience
export type { MockElectronAPI, MockFloatingAPI } from './utils';
