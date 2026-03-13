import { describe, expect, it } from 'vitest';

import { getEligibleDevices, resolveRequestedDeviceId } from './sessionStart';
import type { Device } from '../types/api';

const DEVICES: Device[] = [
  {
    id: 'mic-1',
    name: 'Primary Mic',
    kind: 'microphone',
    is_loopback: false,
    supports_loopback: false,
    backend_candidates: [],
    is_input: true,
    is_output: false,
  },
  {
    id: 'loopback-1',
    name: 'Speakers (WASAPI loopback)',
    kind: 'speaker',
    is_loopback: true,
    supports_loopback: true,
    backend_candidates: [],
    is_input: true,
    is_output: true,
  },
];

describe('sessionStart helpers', () => {
  it('filters devices by capture source', () => {
    expect(getEligibleDevices(DEVICES, 'microphone').map((device) => device.id)).toEqual(['mic-1']);
    expect(getEligibleDevices(DEVICES, 'system').map((device) => device.id)).toEqual([
      'loopback-1',
    ]);
  });

  it('resolves an explicit eligible device id', () => {
    expect(resolveRequestedDeviceId(DEVICES, 'microphone', 'mic-1')).toBe('mic-1');
  });

  it('falls back to the first eligible device when requested id is default or invalid', () => {
    expect(resolveRequestedDeviceId(DEVICES, 'microphone', 'default')).toBe('mic-1');
    expect(resolveRequestedDeviceId(DEVICES, 'system', '')).toBe('loopback-1');
    expect(resolveRequestedDeviceId(DEVICES, 'system', 'mic-1')).toBe('loopback-1');
  });
});
