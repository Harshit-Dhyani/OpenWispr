# Security Policy

## Supported Versions

The following versions of OpenWispr are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| 0.0.x   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within OpenWispr, please send an email to openwispr-security@proton.me

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please include:

1. Description of the vulnerability
2. Steps to reproduce the issue
3. Potential impact of the vulnerability
4. Any suggested fixes (optional)

We aim to respond within 48 hours to acknowledge your report and provide a timeline for the fix.

## Security Considerations

OpenWispr is a local-first desktop application. Please note:

- **Local Processing**: Audio transcription happens locally on your machine. No audio data is sent to external servers unless you explicitly configure cloud-based models.
- **Local LLM**: If using the coach/refiner feature with a local LLM, ensure your model server is properly secured.
- **Hotkey Security**: Global hotkeys can trigger actions system-wide. Be aware of this when using the application in shared environments.
- **File Access**: OpenWispr requires access to your microphone and file system for transcription. Grant permissions only to trusted applications.

## Dependency Security

We regularly update dependencies to address security vulnerabilities. For production use:

1. Keep your installation updated
2. Review third-party model downloads from HuggingFace
3. Use official release builds only
4. Verify checksums when possible

## Scope

This security policy applies to:
- The main OpenWispr application
- Official plugins and extensions
- The Electron renderer process
- The Python backend API

This policy does NOT cover:
- Third-party STT models you download separately
- Local LLM setups (your local LLM server security is your responsibility)
- Unmodified forks of OpenWispr
