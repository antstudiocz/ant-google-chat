#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v uv >/dev/null 2>&1 || {
  echo "Install uv first: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
}
uv sync --project "$repo_dir" --locked
printf 'Environment ready. Add your Desktop OAuth JSON outside this repository, then run:\n'
printf '  uv run --project "%s" --frozen google-chat-plugin login --credentials /path/to/client_secret.json\n' "$repo_dir"
