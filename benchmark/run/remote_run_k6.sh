#!/usr/bin/env bash
# Compatibility wrapper: delegates to the canonical `benchmark/remote_run_k6.sh`.
# Keep this wrapper only for backward compatibility callers.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/../remote_run_k6.sh" "$@"
