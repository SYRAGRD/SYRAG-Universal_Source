from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

import requests

from anchoring import compute_sha256, stamp_with_ots, AnchoringError
from scanner import discover_files


def _mk_fixture(base: Path) -> Path:
    fixture = base / "_selftest_fixture"
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / "a.py").write_text("def f(x):\n    return x+1\n", encoding="utf-8")
    (fixture / "b.js").write_text("function g(){ return 1 }\n", encoding="utf-8")
    (fixture / "c.ts").write_text("export const n:number=42\n", encoding="utf-8")
    (fixture / "README.md").write_text("md\n", encoding="utf-8")
    return fixture


def run_self_test(
    config: Dict[str, Any],
    strict: bool = False,
    llm_timeout_s: int | None = None,
) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "scan": {"ok": False, "details": ""},
        "hash": {"ok": False, "details": ""},
        "ots": {"ok": False, "details": ""},
        "llm_ollama": {"ok": False, "details": ""},
    }

    root = Path.cwd()
    fixture = _mk_fixture(root)

    try:
        files = discover_files(fixture, [".py", ".js", ".ts"])
        results["scan"]["ok"] = len(files) == 3
        results["scan"]["details"] = f"found={len(files)}"
    except Exception as e:
        results["scan"]["details"] = str(e)

    try:
        digest = compute_sha256(fixture / "a.py")
        results["hash"]["ok"] = len(digest) == 64
        results["hash"]["details"] = digest
    except Exception as e:
        results["hash"]["details"] = str(e)

    if shutil.which("ots") is None:
        results["ots"]["ok"] = not strict
        results["ots"]["details"] = "ots not installed"
    else:
        try:
            out = stamp_with_ots(fixture / "a.py")
            results["ots"]["ok"] = out.exists()
            results["ots"]["details"] = str(out)
        except AnchoringError as e:
            results["ots"]["details"] = str(e)

    try:
        cfg_timeout = int(config.get("self_test", {}).get("llm_timeout_s", 45))
        env_timeout = os.getenv("SYRAG_SELF_TEST_LLM_TIMEOUT_S", "").strip()
        if llm_timeout_s is not None:
            effective_llm_timeout = int(llm_timeout_s)
        elif env_timeout:
            effective_llm_timeout = int(env_timeout)
        else:
            effective_llm_timeout = cfg_timeout
        effective_llm_timeout = max(5, min(300, effective_llm_timeout))

        ollama_base = config.get("llm", {}).get("providers", {}).get("ollama", {}).get("base_url", "http://localhost:11434")
        selected_model = config.get("llm", {}).get("providers", {}).get("ollama", {}).get("model", "").strip()

        try:
            tags = requests.get(f"{ollama_base.rstrip('/')}/api/tags", timeout=8)
            if tags.status_code < 400:
                models = [m.get("name", "").strip() for m in tags.json().get("models", []) if m.get("name")]
                if models and selected_model not in models:
                    selected_model = models[0]
                elif not selected_model and models:
                    selected_model = models[0]
        except Exception:
            pass

        if not selected_model:
            selected_model = "llama3.1:8b"

        payload = {
            "model": selected_model,
            "prompt": "Reply with exactly: OK",
            "stream": False,
            "options": {
                "num_predict": 16,
                "num_ctx": 1024,
            },
        }
        response = requests.post(
            f"{ollama_base.rstrip('/')}/api/generate",
            json=payload,
            timeout=effective_llm_timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Ollama HTTP {response.status_code}: {response.text[:180]}")
        data = response.json()
        text = str(data.get("response", ""))
        results["llm_ollama"]["ok"] = isinstance(text, str) and len(text.strip()) > 0
        results["llm_ollama"]["details"] = (
            f"model={selected_model} timeout_s={effective_llm_timeout} | "
            f"{text[:120].replace(chr(10), ' ')}"
        )
    except requests.Timeout:
        results["llm_ollama"]["details"] = (
            f"LLM self-test timed out. Increase self-test timeout via "
            f"--self-test-llm-timeout or config self_test.llm_timeout_s"
        )
    except Exception as e:
        results["llm_ollama"]["details"] = f"unexpected: {e}"

    core_keys: List[str] = ["scan", "hash"]
    integration_keys: List[str] = ["llm_ollama", "ots"]

    mandatory_keys = list(core_keys)
    if strict:
        mandatory_keys.extend(integration_keys)

    overall_ok = all(results[k]["ok"] for k in mandatory_keys)
    integration_ok = all(results[k]["ok"] for k in integration_keys)

    return {
        "ok": overall_ok,
        "core_ok": all(results[k]["ok"] for k in core_keys),
        "integration_ok": integration_ok,
        "strict": strict,
        "mandatory": mandatory_keys,
        "core_checks": core_keys,
        "integration_checks": integration_keys,
        "results": results,
    }


def format_self_test_report(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("SYRAG™ universal source 1.1 — Self-Test")
    lines.append("=" * 40)
    lines.append(f"overall_ok: {report.get('ok')}")
    lines.append(f"core_ok: {report.get('core_ok')}")
    lines.append(f"integration_ok: {report.get('integration_ok')}")
    lines.append(f"strict: {report.get('strict')}")
    lines.append(f"mandatory: {', '.join(report.get('mandatory', []))}")
    lines.append("-")
    for key, item in report.get("results", {}).items():
        lines.append(f"[{key}] ok={item.get('ok')} details={item.get('details')}")
    lines.append("-")
    lines.append(json.dumps(report, indent=2, ensure_ascii=False))
    return "\n".join(lines)
