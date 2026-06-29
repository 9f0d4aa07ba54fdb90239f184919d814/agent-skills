#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -lt 2 ]; then
    echo "Usage: ./run.sh <url> <task> [options]"
    echo ""
    echo "Examples:"
    echo "  ./run.sh https://duckduckgo.com \"search for python tutorials\""
    echo "  ./run.sh https://example.com/contact \"fill the form\" --visible"
    exit 1
fi

URL="$1"
TASK="$2"
shift 2

python3 "$DIR/scripts/browser_agent.py" --url "$URL" --task "$TASK" "$@"
