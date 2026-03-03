"""
Microphone Diagnostic Tool for Transcripta
Tests if microphone is working and detects conflicts
"""
import sys
import time
import numpy as np

print("=" * 60)
print("TRANSCRIPTA MICROPHONE DIAGNOSTIC")
print("=" * 60)

# Check for soundcard
try:
    import soundcard as sc
    print("✓ soundcard module installed")
except ImportError:
    print("✗ soundcard module not found")
    sys.exit(1)

# List all microphones
print("\n1. DETECTING MICROPHONES:")
print("-" * 60)
mics = sc.all_microphones(include_loopback=True)
if not mics:
    print("✗ No microphones detected!")
    sys.exit(1)

for i, mic in enumerate(mics):
    print(f"  [{i}] {mic.name}")
    print(f"       ID: {mic.id}")
    print(f"       Channels: {mic.channels}")
    print(f"       Loopback: {mic.isloopback}")
    print()

# Test default microphone
print("\n2. TESTING DEFAULT MICROPHONE:")
print("-" * 60)
try:
    default_mic = sc.default_microphone()
    print(f"Default: {default_mic.name}")
    
    # Record 3 seconds of audio
    print("\nRecording 3 seconds of audio...")
    print("Please speak into your microphone now!")
    
    with default_mic.recorder(samplerate=16000) as mic:
        time.sleep(0.5)  # Let it initialize
        data = mic.record(numframes=16000 * 3)  # 3 seconds
        
    # Analyze audio
    if data is None or len(data) == 0:
        print("✗ No audio data captured!")
        sys.exit(1)
    
    # Calculate metrics
    mono = data[:, 0] if len(data.shape) > 1 else data
    rms = np.sqrt(np.mean(mono**2))
    peak = np.max(np.abs(mono))
    db = 20 * np.log10(rms + 1e-10)
    
    print(f"\n✓ Audio captured successfully!")
    print(f"  Samples: {len(mono)}")
    print(f"  RMS Level: {rms:.4f}")
    print(f"  Peak Level: {peak:.4f}")
    print(f"  dB: {db:.1f} dB")
    
    if db < -50:
        print("\n⚠ WARNING: Audio level is very low!")
        print("   - Check if microphone is muted")
        print("   - Check Windows sound settings")
        print("   - Try speaking louder or closer to mic")
        print("   - Another app (like Vistaflow) might be using the mic")
    elif db < -40:
        print("\n⚠ Audio level is low but usable")
    else:
        print("\n✓ Audio level is good!")
    
    # Check for signal
    if peak < 0.01:
        print("\n✗ CRITICAL: No audio signal detected!")
        print("   Your microphone may be in use by another application.")
        print("   Try closing Vistaflow or other voice apps.")
    
except Exception as e:
    print(f"✗ Error: {e}")
    print("\nPossible causes:")
    print("  - Microphone is being used by another app (Vistaflow?)")
    print("  - Microphone permissions denied")
    print("  - No default microphone set")
    sys.exit(1)

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
