#!/usr/bin/env bash
# Deploy the app with the project's existing Compose stack, including headless Chromium.
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    compose=(docker-compose)
else
    echo 'Docker with Compose is required. CentOS does not need a desktop or a host browser.' >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    echo 'Missing .env: copy .env.example to .env and set production configuration first.' >&2
    exit 1
fi

# Build failure stops deployment before replacing the running app.
"${compose[@]}" build app
"${compose[@]}" up -d app
"${compose[@]}" exec -T app python -m kinggo_token check-browser --browser chromium
