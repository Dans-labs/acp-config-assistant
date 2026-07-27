#!/bin/bash
set -e

seed_runtime_dir() {
  local source_dir="$1"
  local target_dir="$2"

  mkdir -p "$target_dir"
  if [ -z "$(ls -A "$target_dir" 2>/dev/null)" ]; then
    echo "Seeding $target_dir from $source_dir"
    cp -R "$source_dir"/. "$target_dir"/
  fi
}

sync_missing_files() {
  local source_dir="$1"
  local target_dir="$2"

  find "$source_dir" -type f | while read -r source_file; do
    local rel_path="${source_file#$source_dir/}"
    local target_file="$target_dir/$rel_path"
    if [ ! -f "$target_file" ]; then
      mkdir -p "$(dirname "$target_file")"
      cp "$source_file" "$target_file"
    fi
  done
}

seed_runtime_dir /bootstrap/aca/conf /home/akmi/aca/conf
seed_runtime_dir /bootstrap/aca/resources /home/akmi/aca/resources
seed_runtime_dir /bootstrap/aca/resources/frontend /home/akmi/aca/resources/frontend
sync_missing_files /bootstrap/aca/resources /home/akmi/aca/resources

# Create .secrets.toml from sample if it doesn't exist
if [ ! -f /home/akmi/aca/conf/.secrets.toml ]; then
  echo "Creating .secrets.toml from .secrets.toml.sample"
  cp /home/akmi/aca/conf/.secrets.toml.sample /home/akmi/aca/conf/.secrets.toml
fi

# Start the application
python -m src.main
