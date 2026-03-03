// Auto-generated from config/python/constants.py
// Do not edit manually - run `python config/generate_ts.py` to regenerate

export const SampleRates = [8000, 16000, 22050, 44100, 48000] as const;

export const CommonFillerWords = ["ah", "er", "hmm", "mmm", "uh", "uhh", "um"] as const;

export const HallucinationPhrases = ["thank you for watching", "thanks for watching", "subscribe to", "like and subscribe", "click the link", "check out my"] as const;

export const GpuFallbackKeywords = ["cuda", "out of memory", "gpu", "cudnn"] as const;

export const LiveModeProfiles = {"ultra": {"chunk_seconds": 0.1, "overlap_seconds": 0.02}, "realtime": {"chunk_seconds": 0.2, "overlap_seconds": 0.04}, "low_latency": {"chunk_seconds": 0.5, "overlap_seconds": 0.1}, "balanced": {"chunk_seconds": 1.0, "overlap_seconds": 0.2}, "high_accuracy": {"chunk_seconds": 2.0, "overlap_seconds": 0.4}} as const;

export type LiveModeProfile = keyof typeof LiveModeProfiles;

export const AudioConstants = {
  defaultSampleRate: 16000,
  defaultChannels: 1,
  defaultChunkSeconds: 1.0,
  defaultOverlapSeconds: 0.2,
  defaultBlockSeconds: 0.1,
  defaultMeterDecay: 0.3,
  maxQueueItems: 100,
} as const;

export const VadConstants = {
  defaultThresholdDb: -40.0,
  defaultMinSilenceMs: 200,
  defaultSpeechPadMs: 200,
  defaultFilterEnabled: true,
} as const;

export const ModelConstants = {
  defaultModelName: 'small',
  defaultComputeType: 'float16',
  defaultConfidenceThreshold: 0.6,
  defaultBeamSize: 5,
  defaultBestOf: 5,
  defaultTemperature: 0.0,
  minSegmentLength: 0.5,
} as const;

export const ServerConstants = {
  defaultHost: '127.0.0.1',
  defaultPort: 8765,
  defaultLogLevel: 'INFO',
} as const;
