#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export BOT_PROFILE=prod
exec python3 bot.py --profile prod
