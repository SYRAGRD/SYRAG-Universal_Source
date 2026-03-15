from __future__ import annotations

import argparse
from pathlib import Path

from config_manager import ensure_user_config, load_config
from self_test import run_self_test, format_self_test_report


DISCLAIMER = (
    "⚠️  DIDACTIC USE ONLY — DO NOT USE ON PROPRIETARY SOFTWARE "
    "WITHOUT EXPLICIT CONSENT FROM THE OWNER"
)


def run_cli_bootstrap() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    example = repo_root / "config" / "config.example.json"
    user_cfg = ensure_user_config(example)
    cfg = load_config(user_cfg)

    print("=" * 86)
    print("SYRAG™ universal source 1.1")
    print(DISCLAIMER)
    print("=" * 86)
    print("universal source bootstrap OK")
    print(
        "Motivation: stimulate the use of LLMs to go beyond open source and make programming languages universal."
    )
    print(f"Config: {user_cfg}")
    print(f"Default LLM provider: {cfg.get('llm', {}).get('default_provider', 'n/a')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SYRAG™ universal source 1.1")
    parser.add_argument("--cli", action="store_true", help="Run CLI bootstrap instead of GUI")
    parser.add_argument("--self-test", action="store_true", help="Run end-to-end self-test suite")
    parser.add_argument("--strict", action="store_true", help="Use strict mode for self-test (requires OTS too)")
    parser.add_argument(
        "--self-test-llm-timeout",
        type=int,
        default=None,
        help="Max seconds for Ollama self-test request (default from config self_test.llm_timeout_s)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    example = repo_root / "config" / "config.example.json"
    ensure_user_config(example)

    if args.self_test:
        cfg = load_config()
        report = run_self_test(
            cfg,
            strict=args.strict,
            llm_timeout_s=args.self_test_llm_timeout,
        )
        print(format_self_test_report(report))
        raise SystemExit(0 if report.get("ok") else 1)
    elif args.cli:
        run_cli_bootstrap()
    else:
        from codescan_gui import run_gui

        run_gui()


if __name__ == "__main__":
    main()
