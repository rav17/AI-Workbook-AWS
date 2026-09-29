#!/bin/bash
# Entrypoint for the target host container.
# Starts: SSH server, node_exporter, and fake application.

set -e

echo "[entrypoint] Starting target host services..."

# Copy SSH key to shared volume so self-healing can use it
cp /root/.ssh/id_ed25519 /shared-keys/id_ed25519 2>/dev/null || true
cp /root/.ssh/id_ed25519.pub /shared-keys/id_ed25519.pub 2>/dev/null || true
chmod 600 /shared-keys/id_ed25519 2>/dev/null || true

# Start SSH server
echo "[entrypoint] Starting SSH server..."
/usr/sbin/sshd

# Start node_exporter in background
echo "[entrypoint] Starting node_exporter on :9100..."
/usr/local/bin/node_exporter --web.listen-address=":9100" &

# Start fake application in background
echo "[entrypoint] Starting fake application on :8080..."
python3 /opt/app/fake_app.py &

echo "[entrypoint] All services started. Target host ready."
echo "[entrypoint] SSH: port 22 | node_exporter: port 9100 | app: port 8080"

# Keep container running
wait -n
