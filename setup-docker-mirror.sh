#!/usr/bin/env bash
set -euo pipefail

TARGET="/etc/docker/daemon.json"

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required to write ${TARGET}" >&2
  exit 1
fi

echo "Writing Docker daemon config to use registry.docker.ir mirror..."
sudo mkdir -p /etc/docker

sudo tee "${TARGET}" >/dev/null <<'EOF'
{
  "insecure-registries": ["https://registry.docker.ir"],
  "registry-mirrors": ["https://registry.docker.ir"]
}
EOF

echo "Restarting Docker daemon to apply changes..."
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart docker
elif command -v service >/dev/null 2>&1; then
  sudo service docker restart
else
  echo "Could not restart Docker automatically (no systemctl/service found). Please restart Docker manually." >&2
  exit 1
fi

echo "Done."
