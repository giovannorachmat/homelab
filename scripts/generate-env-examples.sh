#!/usr/bin/env bash
#
# generate-env-examples.sh
# Generates .env.example files from .env files in runtime/
#
# Usage:
#   ./scripts/generate-env-examples.sh           # Update all .env.example files
#   ./scripts/generate-env-examples.sh --help    # Show usage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUNTIME_DIR="$PROJECT_DIR/runtime"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- Help ---
usage() {
    echo "Usage: $0 [--help]"
    echo ""
    echo "Generates .env.example files from .env files in runtime/"
    echo "Replaces all values with placeholders (your-<key>-here)"
    echo ""
    echo "Examples:"
    echo "  $0                    # Update all .env.example files"
    echo "  $0 --help             # Show this help"
    exit 0
}

# --- Convert KEY_NAME to key-name ---
key_to_kebab() {
    local key="$1"
    echo "$key" | tr '[:upper:]' '[:lower:]' | tr '_' '-'
}

# --- Generate .env.example from .env ---
generate_example() {
    local env_file="$1"
    local dir
    dir="$(dirname "$env_file")"
    local example_file="$dir/.env.example"

    echo -e "${YELLOW}Processing:${NC} $env_file"

    {
        while IFS= read -r line || [[ -n "$line" ]]; do
            # Empty line — keep as-is
            if [[ -z "$line" ]]; then
                echo ""
                continue
            fi

            # Comment — keep as-is
            if [[ "$line" =~ ^[[:space:]]*# ]]; then
                echo "$line"
                continue
            fi

            # KEY=VALUE line
            if [[ "$line" =~ ^([A-Za-z0-9_]+)=(.*) ]]; then
                local key="${BASH_REMATCH[1]}"
                local kebab
                kebab="$(key_to_kebab "$key")"
                echo "${key}=your-${kebab}-here"
                continue
            fi

            # Anything else — keep as-is
            echo "$line"

        done < "$env_file"
    } > "$example_file"

    echo -e "${GREEN}Generated:${NC} $example_file"
}

# --- Main ---
main() {
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        usage
    fi

    if [[ ! -d "$RUNTIME_DIR" ]]; then
        echo -e "${RED}Error:${NC} runtime/ directory not found at $RUNTIME_DIR"
        exit 1
    fi

    local count=0

    # Find all .env files in runtime/
    while IFS= read -r -d '' env_file; do
        generate_example "$env_file"
        count=$((count + 1))
    done < <(find "$RUNTIME_DIR" -name ".env" -type f -print0 | sort -z)

    echo ""
    echo -e "${GREEN}Done!${NC} Generated $count .env.example file(s)."
}

main "$@"
