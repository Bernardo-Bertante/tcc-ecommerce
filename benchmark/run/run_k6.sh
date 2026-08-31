#!/usr/bin/env bash
# Compatibility wrapper: delegates to the canonical `benchmark/run_k6.sh`.
# Keep this wrapper only for backward compatibility callers.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/../run_k6.sh" "$@"
