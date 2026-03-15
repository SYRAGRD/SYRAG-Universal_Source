# SYRAG™ universal source 1.1

SYRAG™ universal source 1.1 is a standalone desktop scanner (PyQt5) designed to be **SYRAG-agnostic**:

First-release motivation:

- stimulate the use of LLMs to go beyond open source
- make programming languages more universal and accessible across ecosystems

- no dependency on SYRAG internal modules
- user-provided API keys and model providers
- local and cloud LLM providers
- multi-language scanning (not only Python)
- distributable as AppImage

## ⚠️ LEGAL DISCLAIMER (VERY IMPORTANT)

This software is provided **for didactic/educational purposes only**.

- You must not use it on proprietary software, private repositories, or closed-source codebases without explicit written consent from the legal owner.
- The user is fully responsible for legal compliance, authorization, and applicable policy constraints.
- SYRAG™ universal source 1.1 does not grant any right to inspect or process third-party code without permission.

## Principles

1. Provider-agnostic LLM integration (Ollama, OpenRouter, OpenAI-compatible, custom adapters)
2. User-owned configuration in local home directory
3. Optional anchoring pipeline (can be enabled/disabled by user)
4. Zero hardcoded project roots

## Local config

Default config path:

- `~/.codescan/config.json`

See `config/config.example.json`.

## Quick start

```bash
cd forks/codescan
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 src/main.py
```

## Cross-platform distribution

Important: **one single AppImage cannot target every OS**.

- AppImage = Linux only
- Windows requires native `.exe`/portable bundle
- macOS requires native `.app` bundle

This repository includes a CI workflow to produce native artifacts for Linux, Windows and macOS:

- `.github/workflows/build-multi-os.yml`
- `.github/workflows/release-draft.yml` (creates draft GitHub Release with attached artifacts)

Trigger it with a tag (`v*`) or manually via `workflow_dispatch`.

CLI bootstrap test:

```bash
python3 src/main.py --cli
```

End-to-end self test:

```bash
python3 src/main.py --self-test
python3 src/main.py --self-test --strict
python3 src/main.py --self-test --self-test-llm-timeout 120
./SYRAG_universal_source_1.1-x86_64.AppImage --self-test
```

Linux/Kodachi compatibility launcher:

```bash
chmod +x run_appimage_compat.sh
./run_appimage_compat.sh
```

It automatically retries with `APPIMAGE_EXTRACT_AND_RUN=1` and handles `noexec` mounts.

Self-test modes:

- Default (`--self-test`): validates core portability (scan + hash), integration checks are reported.
- Strict (`--self-test --strict`): requires integration checks (LLM + OTS) as mandatory.
- Timeout override (`--self-test-llm-timeout N`): hard-stop for LLM self-test request in seconds.

## LLM providers (agnostic)

- `ollama`: local models via `base_url` + selected model
- `openrouter`: cloud provider via `OPENROUTER_API_KEY`
- `openai_compatible`: generic compatible endpoint via `OPENAI_API_KEY`

Local model scan:

- Use `Scan Local LLMs` in the GUI to scan the system for local runtimes/models (currently Ollama models via API tags).
- Select a detected model from `Local models` dropdown to auto-fill provider and model fields.

Configure provider/model in UI and in `~/.codescan/config.json`.

## Hashing

- SHA256 hash is always available locally



