#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
staging=$(mktemp -d "${TMPDIR:-/tmp}/google-chat-plugin-mcpb.XXXXXX")
trap 'rm -rf "$staging"' EXIT HUP INT TERM
mkdir -p "$repo_dir/dist"
if command -v mcpb >/dev/null 2>&1; then
  "$repo_dir/scripts/stage-mcpb.sh" "$repo_dir" "$staging"
  mcpb pack "$staging" "$repo_dir/dist/google-chat-plugin.mcpb"
else
  echo "Install the MCPB CLI first: npm install --global @anthropic-ai/mcpb" >&2
  exit 1
fi
