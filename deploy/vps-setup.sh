#!/bin/bash
# Bootstrap a fresh Ubuntu 22.04+ VPS to run Delphee Lead Hunter
# Usage: ssh root@YOUR_VPS_IP < deploy/vps-setup.sh
#
# After running this script:
#   1. Edit /opt/delphee/.env with your real API keys
#   2. Copy docker-compose.yml, Dockerfile, and app/ to /opt/delphee/
#      (or git clone your repo there)
#   3. Run: cd /opt/delphee && docker compose up -d --build

set -e

echo "==> Installing Docker..."
curl -fsSL https://get.docker.com | sh

echo "==> Installing Docker Compose plugin..."
apt-get install -y docker-compose-plugin

echo "==> Creating app directory..."
mkdir -p /opt/delphee
cd /opt/delphee

echo "==> Writing default .env (fill in your API keys before starting)..."
cat > /opt/delphee/.env << 'EOF'
# Required: fill in your real keys before starting
GEMINI_API_KEY=your-gemini-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Database — PostgreSQL (used automatically by vps-docker-compose.yml)
DATABASE_URL=postgresql+asyncpg://delphee:changeme@db:5432/delphee
DB_BACKEND=sql
DB_PASSWORD=changeme

# Change this to a random secret in production
SECRET_KEY=change-me-in-production
PORT=8000
EOF

echo ""
echo "=== VPS setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit /opt/delphee/.env — add your GEMINI_API_KEY and ANTHROPIC_API_KEY"
echo "  2. Copy your project files to /opt/delphee/ (or: git clone YOUR_REPO /opt/delphee)"
echo "  3. cd /opt/delphee && docker compose -f deploy/vps-docker-compose.yml up -d --build"
echo "  4. App will be at http://YOUR_VPS_IP (port 80)"
echo ""
echo "  For HTTPS with a custom domain, set your domain in deploy/Caddyfile"
echo "  then redeploy — Caddy handles SSL automatically via Let's Encrypt."
