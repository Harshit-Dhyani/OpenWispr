"""
Audio Capture Diagnostic Script

Tests if audio capture is actually working by:
1. Initializing LoopbackAudioSource with AppSettings
2. Capturing audio for 5 seconds
3. Printing real-time statistics (queue size, RMS level, dropped frames)
4. Attempting to read from queue and showing what data flows through

Usage:
    python test_audio_capture.py

Requirements:
    - Virtual audio cable or loopback device configured
    - Audio playing (music, video, etc.) to capture
"""

import sys
import time
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np

from app.audio.capture import LoopbackAudioSource
from app.core.config import AppSettings


def main():
    print("=" * 60)
    print("Transcripta Audio Capture Diagnostic")
    print("=" * 60)

    # Load settings from .env or defaults
    settings = AppSettings()
    print(f"\nConfiguration (from AppSettings):")
    print(f"  Sample Rate: {settings.sample_rate} Hz")
    print(f"  Channels: {settings.channels}")
    print(
        f"  Block Size: {int(settings.capture_block_seconds * settings.sample_rate)} samples ({settings.capture_block_seconds}s)"
    )
    print(f"  Max Queue Items: {settings.max_queue_items}")
    print(f"  Device: {settings.device}")

    # Calculate block size from settings
    block_size = int(settings.capture_block_seconds * settings.sample_rate)

    print("\n" + "-" * 60)
    print("Make sure you have audio playing (music, video, etc.)")
    print("Press Ctrl+C to stop early")
    print("-" * 60)

    # Create audio source
    source = LoopbackAudioSource(
        device_id=settings.device if settings.device != "auto" else None,
        sample_rate=settings.sample_rate,
        channels=settings.channels,
        block_size=block_size,
        max_queue_items=settings.max_queue_items,
    )

    # Stats tracking
    frames_read = 0
    total_samples_read = 0
    rms_values = []
    read_attempts = 0
    read_successes = 0

    # Error handler
    capture_error = None

    def on_error(exc: Exception):
        nonlocal capture_error
        capture_error = exc
        print(f"\n[ERROR] Capture error: {exc}")

    source.on_error = on_error

    # Start capture
    print("\n[1/4] Starting audio capture...")
    source.start()
    time.sleep(0.5)  # Give it time to initialize

    if capture_error:
        print(f"[FAIL] Failed to start capture: {capture_error}")
        return 1

    print("[OK] Capture started successfully")

    # Capture duration
    duration = 5.0  # seconds
    start_time = time.monotonic()
    last_stats_time = start_time
    stats_interval = 0.5  # Print stats every 0.5s

    print(f"\n[2/4] Capturing for {duration} seconds...")
    print(f"{'Time':>6} {'Queue':>6} {'RMS':>10} {'Dropped':>8} {'Status':>12}")
    print("-" * 50)

    try:
        while time.monotonic() - start_time < duration:
            now = time.monotonic()
            elapsed = now - start_time

            # Try to read from queue
            read_attempts += 1
            data = source.read(timeout=0.1)

            if data is not None:
                read_successes += 1
                frames_read += 1
                total_samples_read += len(data)
                rms = float(np.sqrt(np.mean(np.square(data)) + 1e-12))
                rms_values.append(rms)

            # Print stats periodically
            if now - last_stats_time >= stats_interval:
                status = "FLOWING" if source.queue.qsize() > 0 else "EMPTY"
                if source.level_rms > 1e-4:
                    status = "ACTIVE"
                print(
                    f"{elapsed:6.2f} {source.queue.qsize():6d} {source.level_rms:10.6f} "
                    f"{source.dropped_frames:8d} {status:>12}"
                )
                last_stats_time = now

            if capture_error:
                break

    except KeyboardInterrupt:
        print("\n[STOPPED] Interrupted by user")

    actual_duration = time.monotonic() - start_time

    print("\n[3/4] Stopping capture...")
    source.stop()
    print("[OK] Capture stopped")

    # Final statistics
    print("\n" + "=" * 60)
    print("CAPTURE STATISTICS")
    print("=" * 60)

    print(f"\nDuration: {actual_duration:.2f} seconds")
    print(f"\nQueue Statistics:")
    print(f"  Final queue size: {source.queue.qsize()}")
    print(f"  Max queue size: {source.queue.maxsize}")
    print(f"  Queue utilization: {source.queue.qsize() / source.queue.maxsize * 100:.1f}%")

    print(f"\nAudio Flow:")
    print(f"  Read attempts: {read_attempts}")
    print(f"  Successful reads: {read_successes}")
    print(
        f"  Read success rate: {read_successes / read_attempts * 100:.1f}%"
        if read_attempts > 0
        else "  Read success rate: N/A"
    )
    print(f"  Frames read: {frames_read}")
    print(f"  Total samples: {total_samples_read:,}")
    print(f"  Duration captured: {total_samples_read / settings.sample_rate:.2f} seconds")

    print(f"\nLevel/Drop Statistics:")
    print(f"  Final RMS level: {source.level_rms:.6f}")
    print(f"  Dropped frames: {source.dropped_frames}")
    if rms_values:
        print(f"  Min RMS: {min(rms_values):.6f}")
        print(f"  Max RMS: {max(rms_values):.6f}")
        print(f"  Avg RMS: {sum(rms_values) / len(rms_values):.6f}")

    # Analysis
    print("\n" + "=" * 60)
    print("DIAGNOSIS")
    print("=" * 60)

    if capture_error:
        print(f"\n[FAIL] Capture encountered an error:")
        print(f"       {capture_error}")
        return 1

    issues = []

    if source.dropped_frames > 0:
        issues.append(f"- {source.dropped_frames} frames were dropped (queue overflow)")

    if read_successes == 0:
        issues.append("- No data was read from the queue")

    if source.level_rms < 1e-4 and not rms_values:
        issues.append("- No audio signal detected (RMS level is near zero)")
        issues.append("  Make sure audio is playing and loopback device is configured")

    if source.queue.qsize() == 0 and frames_read == 0:
        issues.append("- Queue remained empty - audio may not be flowing")

    if not issues:
        print("\n[PASS] Audio capture appears to be working correctly!")
        print(f"       Captured {total_samples_read:,} samples in {actual_duration:.1f}s")
        if source.level_rms > 1e-4 or (rms_values and max(rms_values) > 1e-4):
            print(f"       Audio signal detected (RMS: {source.level_rms:.6f})")
        return 0
    else:
        print("\n[WARNING] Potential issues detected:")
        for issue in issues:
            print(f"  {issue}")
        print("\nTroubleshooting:")
        print("  1. Ensure VB-Cable or similar virtual audio cable is installed")
        print("  2. Set Windows playback device to the virtual cable")
        print("  3. Play audio (music, video, etc.)")
        print("  4. Run 'python scripts/check_audio_setup.py' to verify device setup")
        return 1


if __name__ == "__main__":
    sys.exit(main())
