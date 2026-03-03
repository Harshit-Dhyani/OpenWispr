# Transcripta

Transcripta is a Windows 11 desktop app for privacy-first transcription of live system audio. It keeps capture, inference, transcript storage, and STEM-aware review local on the machine using an Electron desktop shell over a local Python backend, faster-whisper for speech recognition, and WASAPI loopback-style capture through `soundcard`.

## Product Goals

- Capture system audio directly from the default Windows output device.
- Run transcription locally with no cloud dependency.
- Prefer GPU inference when CUDA is available, with CPU fallback.
- Keep transcripts and logs on-device under user control.
- Continuously save transcript, notes, formulas, highlights, and logs per session.
- Flag low-confidence or suspicious STEM segments for manual review instead of claiming correctness.
- Package into a single desktop-friendly Windows distribution.

## Stack

- Python 3.11
- FastAPI + Uvicorn local backend
- Electron desktop shell
- faster-whisper
- CTranslate2
- PyAudioWPatch WASAPI capture with soundcard fallback
- Electron packaging flow on top of the Python runtime

## Quick Start

Desktop entrypoint: `app/desktop/`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -e .[dev]
cd app/desktop
npm install
npm run dev
```

If PowerShell script execution is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## GPU Verification

Check that CTranslate2 can see a CUDA device:

```powershell
python -c "import ctranslate2; print('cuda_devices=', ctranslate2.get_cuda_device_count())"
```

Expected result on a working GPU machine:

```text
cuda_devices= 1
```

Verify that faster-whisper can initialize on the GPU:

```powershell
python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cuda', compute_type='float16'); print('faster-whisper cuda ok')"
```

If that fails, force CPU mode:

```powershell
python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('faster-whisper cpu ok')"
```

## Session Artifacts

Each session writes a dedicated folder under `sessions\<session-slug>\`:

- `transcript.jsonl`
- `transcript.txt`
- `notes.md`
- `formulas.json`
- `highlights.txt`
- `session.json`
- `logs\app.log`

## Model Manager

Transcripta now separates local models into two categories:

- `Speech-to-Text (ASR)`
- `Transcript Refiner`

Current ASR catalog:

- `whisper-tiny`
- `whisper-small`
- `whisper-medium`
- `whisper-large-v3`
- `whisper-turbo`

Current refiner catalog:

- `qwen2.5-7b-instruct`
- `mistral-7b-instruct-v0.3`
- `phi-3-mini-4k-instruct`

Use `Full Settings > Models` to:

- inspect installed status
- download models
- cancel active downloads
- remove local models
- choose the default ASR model
- choose the default refiner model
- choose `Refinement Mode: Off | Strict | Polished`

The UI is explicit about installation state. If a model is not installed, it is shown as `Not Installed`.

### ASR model guidance

- `whisper-tiny`: fastest option for weak CPUs and quick smoke tests
- `whisper-small`: strong fast local option for modest GPUs and dictation
- `whisper-medium`: best default balance for most Windows desktops
- `whisper-large-v3`: best quality for stronger GPUs and long-form sessions
- `whisper-turbo`: cataloged fast option, but only selectable when runtime support is available

### Refiner model guidance

- `qwen2.5-7b-instruct`: default balanced local refiner choice
- `mistral-7b-instruct-v0.3`: stronger quality-oriented cleanup option
- `phi-3-mini-4k-instruct`: smaller refiner for lower-memory systems

### Refiner runtime status

Refiner selection, download, and persistence are implemented. If the local refiner runtime is not enabled yet, Transcripta will say so explicitly and continue using built-in cleanup only.

## Where Models Are Stored

Downloaded models are stored under the Electron user-data directory, not inside the repo working tree.

Typical Windows location:

```text
%APPDATA%\Transcripta\models\
```

Layout:

```text
models\
  asr\
    whisper-medium\
  refiner\
    qwen2.5-7b-instruct\
```

The app verifies downloaded files using a minimum-size check and will use SHA-256 verification when catalog metadata provides it.

## Switching Models

Change the default ASR model in `Full Settings > Models`. The new selection is applied to the next session. Transcripta does not silently hot-swap ASR models in the middle of an active session.

If you want to use the selected model immediately:

1. stop the current session
2. select the new model
3. optionally preload it
4. start a new session

## Local Run Commands

Development run:

```powershell
.\.venv\Scripts\Activate.ps1
cd app/desktop
npm install
npm run dev
```

The Electron shell starts the local Python API automatically. The backend attempts CUDA first and falls back to CPU `int8` if GPU initialization fails.

Run only the backend API:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.api_main
```

Recommended lower-memory run:

```powershell
.\.venv\Scripts\Activate.ps1
$env:TRANSCRIPTA_DEFAULT_MODEL='base'
$env:TRANSCRIPTA_COMPUTE_TYPE='float16'
cd app/desktop
npm run dev
```

Recommended NVIDIA run:

```powershell
.\.venv\Scripts\Activate.ps1
$env:TRANSCRIPTA_DEFAULT_MODEL='small'
$env:TRANSCRIPTA_COMPUTE_TYPE='float16'
cd app/desktop
npm run dev
```

## Packaging For Windows

Current repository support:

- Python backend is package-ready via `pyproject.toml`.
- Electron shell is ready for local development via `app/desktop/package.json`.
- Full Windows installer packaging for Electron is the next step and not yet wired to `electron-builder`.

Manual desktop build flow right now:

```powershell
.\.venv\Scripts\Activate.ps1
cd app/desktop
npm install
npm run dev
```

Recommended release flow:

1. Validate the Electron shell against the Python backend locally.
2. Add `electron-builder` with a bundled backend launch strategy.
3. Produce a Windows installer after the backend path is frozen.
4. Verify loopback capture, transcript generation, and GPU/CPU fallback on the packaged build.

## Testing

Run the current unit suite:

```powershell
.\.venv\Scripts\Activate.ps1
pytest tests -q
```

## Privacy Model

- Audio capture is local-only.
- Transcription is local-only.
- No cloud upload is required for core functionality.
- Transcript retention should default to local storage that the user can inspect and delete.

## Troubleshooting

### No system audio is captured

- Confirm Windows 11 is using the expected playback device.
- Disable exclusive mode on the playback device in `Sound > More sound settings > Playback > Properties > Advanced`.
- Make sure the app is targeting the default output device for WASAPI loopback.
- Test with known audio playing through speakers or headphones, not a muted session.

### Headphones not captured (Stereo Mix issue)

If audio plays through your headphones but Transcripta captures nothing:

**The Problem:** Stereo Mix only captures from speakers, not headphones. When headphones are connected, Windows switches output, and Stereo Mix becomes silent.

**The Solution:** Use WASAPI loopback capture on the specific headphone device.

1. Run the diagnostic tool to identify your headphone device:
   ```powershell
   python fix_headphone_capture.py
   ```

2. Test capture from your headphone device (replace `<device_id>` with the ID from step 1):
   ```powershell
   python fix_headphone_capture.py --test <device_id>
   ```

3. Configure the device in your `.env` file:
   ```env
   TRANSCRIPTA_CAPTURE_DEVICE_ID=<device_id>
   ```

Or set via environment variable before starting:
```powershell
$env:TRANSCRIPTA_CAPTURE_DEVICE_ID="<device_id>"
npm run dev
```

For more details about WASAPI loopback capture:
```powershell
python fix_headphone_capture.py --explain
```

### GPU is not detected

- Run the CUDA verification command above.
- Confirm the NVIDIA driver is installed and current.
- Confirm the installed `ctranslate2` wheel matches the local CUDA runtime expectations.
- The app will fall back to CPU automatically if CUDA model initialization fails.

### Transcription is slow

- Use `device='cuda'` with `compute_type='float16'` on supported NVIDIA hardware.
- Drop to a smaller model such as `small` or `base`.
- Avoid running other GPU-heavy apps during live transcription.
- On CPU, prefer `compute_type='int8'`.

### Loopback works but text is poor

- Reduce desktop output distortion and clipping.
- Avoid spatial audio or enhancement filters during capture.
- Use a cleaner playback source when possible.
- Test another model size to improve recognition quality.
- Review `Needs Review` items before trusting formulas, units, or derivation steps.

### The packaged app fails to start

- Test the same machine from an activated virtual environment first.
- Confirm `app/desktop` can spawn `.venv\Scripts\python.exe`.
- Run `python -m app.api_main` directly to verify the backend separately from Electron.
- Check whether port `8765` is already in use.

## Legal Note

Use Transcripta only where you have the legal right to capture and transcribe audio. Consent, notice, workplace policy, platform terms, and recording laws vary by jurisdiction. This project should not be treated as legal advice.

## V2 Roadmap

- Per-device input selection instead of default-device-only capture.
- Real-time transcript segmentation with speaker-change heuristics where feasible.
- Persistent transcript search and export.
- Configurable hotkeys and background tray mode.
- Rolling buffer with retroactive save.
- Word timestamps and subtitle export.
- Electron packaging and installer generation.
- Optional local summarization pipeline after transcription completes.
- PDF ingestion and retrieval-backed correction for later session verification.
- LaTeX export for extracted formulas and structured notes.
