"""Run from the project root: python -m kinggo_token --help."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .generator import generate, inspect_token, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Kinggo oOr6SIhu tools (Python 3.10)")
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Extract config from a HAR entirely offline")
    extract.add_argument("har_path")
    extract.add_argument("url")
    extract.add_argument("--method", default="POST")
    extract.add_argument("--body")
    extract.add_argument("--output", default="kinggo_token/config-from-har.json")
    extract.add_argument("--browser", choices=["auto", "msedge", "chromium"], default="auto",
                         help="auto (default): Edge on Windows, Chromium on Linux/macOS")
    extract.add_argument("--executable-path")
    generate_parser = commands.add_parser("generate", help="Generate a fresh parameter")
    generate_parser.add_argument("url")
    generate_parser.add_argument("--config", required=True)
    generate_parser.add_argument("--timestamp-ms", type=int)
    generate_parser.add_argument("--random-high", type=int)
    decode = commands.add_parser("decode", help="Decode and inspect a parameter")
    decode.add_argument("token")
    decode.add_argument("--config", required=True)
    verify = commands.add_parser("verify", help="Reproduce every HAR parameter exactly")
    verify.add_argument("har_path")
    verify.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        if args.command == "extract":
            from .har import replay_offline
            result = asyncio.run(replay_offline(
                args.har_path, args.url, args.method, args.body,
                channel=None if args.browser == "chromium" else args.browser,
                executable_path=args.executable_path,
            ))
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            # Write only after verification, then replace atomically.
            temporary = output.with_suffix(output.suffix + ".tmp")
            temporary.write_text(json.dumps(result["config"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(output)
            result["configPath"] = str(output.resolve())
        elif args.command == "generate":
            result = generate(args.url, load_config(args.config),
                              timestamp_ms=args.timestamp_ms, random_high=args.random_high)
        elif args.command == "decode":
            result = inspect_token(args.token, load_config(args.config))
        else:
            from .har import verify_har
            count = verify_har(args.har_path, load_config(args.config))
            result = {"status": "PASS", "samples": count, "exactMatches": count}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, ImportError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
