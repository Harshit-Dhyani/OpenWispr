---
title: Documentation Home
audience: all
last_verified: 2026-03-05
source_of_truth:
  - docs/
  - README.md
---

# Transcripta Documentation Hub

> Complete documentation for the Transcripta desktop transcription application.  
> **Last Updated:** March 5, 2026  
> **Version:** 1.0.0

---

## Quick Start Paths

Choose your path based on your role:

### New Users
📖 [Main README](../README.md) → 🚀 [Deployment Guide](./deployment/DEPLOYMENT.md) → 🔧 [Troubleshooting](./troubleshooting.md)

**Start here if you're new to Transcripta.** Learn what the app does, install it, and resolve common issues.

### Developers
🏗️ [Architecture Overview](./engineering/architecture-overview.md) → 🔌 [API Reference](./api/endpoints.md) → 🤝 [Contributing Guidelines](../CONTRIBUTING.md)

**For contributors and developers.** Understand the codebase, extend functionality, and submit improvements.

### Operators
🚀 [Deployment Guide](./deployment/DEPLOYMENT.md) → ⚙️ [Operations Guide](./operations/OPERATIONS.md) → 🔧 [Troubleshooting](./troubleshooting.md)

**For system administrators.** Deploy, monitor, and maintain Transcripta in production.

---

## Documentation Index

### Getting Started

| Document | Status | Description | Keywords |
|----------|--------|-------------|----------|
| 📘 [Main README](../README.md) | ✅ Complete | Project overview, features, and quick intro | overview, features, introduction |
| 🚀 [Deployment Guide](./deployment/DEPLOYMENT.md) | ✅ Complete | Windows installation and setup instructions | install, setup, windows, configuration |

### Architecture

| Document | Status | Description | Keywords |
|----------|--------|-------------|----------|
| 🏗️ [Model System](./architecture/MODEL_SYSTEM.md) | ✅ Complete | Model catalog and management architecture | models, whisper, catalog, registry |
| 📐 [Architecture Overview](./engineering/architecture-overview.md) | ✅ Complete | High-level system design and components | design, components, structure |
| 🔌 [Electron-Backend Contract](./engineering/architecture-electron-backend-contract.md) | ✅ Complete | IPC and WebSocket API contract | electron, ipc, websocket, contract |

### API Documentation

| Document | Status | Description | Keywords |
|----------|--------|-------------|----------|
| 🔌 [Endpoints](./api/endpoints.md) | ✅ Complete | REST API and WebSocket reference | rest, websocket, api, endpoints |

### Operations

| Document | Status | Description | Keywords |
|----------|--------|-------------|----------|
| ⚙️ [Operations Guide](./operations/OPERATIONS.md) | ✅ Complete | Running, monitoring, and maintenance | monitoring, maintenance, production |
| 🔧 [Troubleshooting](./troubleshooting.md) | ✅ Complete | Common issues and solutions | errors, issues, debug, fix |

### Reference

| Document | Status | Description | Keywords |
|----------|--------|-------------|----------|
| 📋 [Features](./reference/features.md) | ✅ Complete | Feature documentation and capabilities | features, modes, dictation |
| ⚙️ [Configuration](./reference/config.md) | ✅ Complete | Configuration reference and environment variables | config, settings, env |
| 🎨 [Style Guide](./_style.md) | ✅ Complete | Documentation standards and conventions | style, standards, frontmatter |

### Project Documentation

| Document | Status | Description | Keywords |
|----------|--------|-------------|----------|
| 📁 [Project Structure](./project/project-structure.md) | ✅ Complete | Repository organization and conventions | structure, organization, folders |
| 🤝 [Contributing](../CONTRIBUTING.md) | ✅ Complete | How to contribute to the project | contribute, pr, guidelines |
| 📝 [Contributing to Docs](./engineering/contributing-docs.md) | ✅ Complete | Documentation contribution guide | docs, documentation, style |

### Engineering Guides

| Document | Status | Description | Keywords |
|----------|--------|-------------|----------|
| 🧪 [Testing Guide](./engineering/testing.md) | ✅ Complete | Testing procedures and best practices | tests, testing, pytest, vitest |
| 🚀 [Model Runtime](./engineering/model-runtime.md) | ✅ Complete | Model runtime and routing | models, runtime, routing, download |
| ⚡ [Performance](./engineering/performance.md) | ✅ Complete | Performance tuning and optimization | performance, speed, latency |
| ⏱️ [Latency Playbook](./engineering/latency-playbook.md) | ✅ Complete | Diagnostic guide for lag issues | latency, diagnostics, remediation |
| 🔒 [Security](./engineering/security.md) | ✅ Complete | Security documentation | security, threats, mitigations |
| 🎙️ [Audio Capture](./engineering/audio-capture.md) | ✅ Complete | Audio capture system architecture | audio, capture, microphone, system |
| 📝 [Dictation Pipeline](./engineering/dictation-pipeline.md) | ✅ Complete | STT pipeline and streaming flow | stt, streaming, transcription |
| 🎯 [English Coach](./engineering/english-coach.md) | ✅ Complete | LLM-powered transcript refinement | coach, llm, refinement, grammar |
| 📡 [Events & Streaming](./engineering/events-streaming.md) | ✅ Complete | SSE and WebSocket streaming | events, sse, websocket, realtime |
| ⚙️ [Settings System](./engineering/settings.md) | ✅ Complete | Settings management and sync | settings, persistence, sync |

---

## Documentation Status Legend

| Status | Icon | Meaning |
|--------|------|---------|
| **Complete** | ✅ | Fully documented and up-to-date |
| **Draft** | 📝 | In progress, content may be incomplete |
| **Outdated** | ⚠️ | Needs review, information may be stale |
| **Planned** | 📋 | Scheduled for creation |

---

## Quick Search by Topic

### 🔧 Configuration & Setup
- [Deployment Guide](./deployment/DEPLOYMENT.md) - Installation
- [Configuration Reference](./reference/config.md) - Settings
- [Project Structure](./project/project-structure.md) - Organization

### ⚡ Performance
- [Performance Guide](./engineering/performance.md) - Tuning
- [Latency Playbook](./engineering/latency-playbook.md) - Diagnostics
- [Model Runtime](./engineering/model-runtime.md) - Model routing

### 🔒 Security
- [Security Documentation](./engineering/security.md) - Security review

### 🏗️ Architecture & Design
- [Architecture Overview](./engineering/architecture-overview.md) - System design
- [Model System](./architecture/MODEL_SYSTEM.md) - Models
- [Electron-Backend Contract](./engineering/architecture-electron-backend-contract.md) - IPC contract
- [Audio Capture](./engineering/audio-capture.md) - Audio system
- [Dictation Pipeline](./engineering/dictation-pipeline.md) - STT flow
- [Events & Streaming](./engineering/events-streaming.md) - Realtime events

### 🤝 Contributing
- [Contributing](../CONTRIBUTING.md) - Guidelines
- [Contributing to Docs](./engineering/contributing-docs.md) - Documentation
- [Testing Guide](./engineering/testing.md) - Testing
- [Style Guide](./_style.md) - Documentation standards

---

## Need Help?

- 🐛 **Found a bug?** Check [Troubleshooting](./troubleshooting.md) first
- 💡 **Have an idea?** See [Contributing](../CONTRIBUTING.md) for how to propose features
- 📝 **Docs issue?** Review [Contributing to Docs](./engineering/contributing-docs.md)

---

*This documentation hub is maintained by the Transcripta team.*
