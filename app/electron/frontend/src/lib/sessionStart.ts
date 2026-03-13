import type { Device } from '../types/api';

export type CaptureSource = 'microphone' | 'system';

export function getEligibleDevices(
  devices: Device[],
  captureSource: CaptureSource,
): Device[] {
  return devices.filter((device) =>
    captureSource === 'system'
      ? Boolean(device.is_loopback || device.supports_loopback)
      : !Boolean(device.is_loopback || device.supports_loopback),
  );
}

export function resolveRequestedDeviceId(
  devices: Device[],
  captureSource: CaptureSource,
  requestedDeviceId: string | null | undefined,
): string | null {
  const eligibleDevices = getEligibleDevices(devices, captureSource);
  const normalizedRequestedId =
    requestedDeviceId && requestedDeviceId !== 'default' ? requestedDeviceId : null;
  if (normalizedRequestedId) {
    const explicitMatch = eligibleDevices.find((device) => device.id === normalizedRequestedId);
    if (explicitMatch) {
      return explicitMatch.id;
    }
  }
  return eligibleDevices[0]?.id ?? null;
}
