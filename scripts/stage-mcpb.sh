#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "${1:?source directory required}" && pwd)
destination=${2:?staging destination required}
mkdir -p "$destination/src"
cp "$source_dir/manifest.json" "$source_dir/pyproject.toml" "$source_dir/uv.lock" "$source_dir/README.md" "$source_dir/LICENSE" "$destination/"
mkdir -p "$destination/src/google_chat_plugin"
cp "$source_dir/src/google_chat_plugin/__init__.py" "$source_dir/src/google_chat_plugin/server.py" "$destination/src/google_chat_plugin/"
