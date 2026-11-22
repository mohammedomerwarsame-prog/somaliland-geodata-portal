#!/usr/bin/env bash
# =============================================================================
# Somaliland GeoData Portal – one-time server setup
# Tested target: a fresh Ubuntu 24.04 server (VPS) with a domain pointing to it.
#
# Usage (as root, on the server):
#   curl -fsSL https://raw.githubusercontent.com/mohammedomerwarsame-prog/somaliland-geodata-portal/main/deploy/setup_server.sh -o setup.sh
#   sudo bash setup.sh geodata.example.so admin@example.so
#
# What it does: installs Python, PostgreSQL, Nginx and HTTPS (Let's Encrypt),
# downloads the portal, creates the database, and starts it as a service.
# =============================================================================
set -euo pipefail

DOMAIN="${1:?Usage: setup_server.sh <domain> <email-for-https>}"
EMAIL="${2:?Usage: setup_server.sh <domain> <email-for-https>}"
REPO="https://github.com/mohammedomerwarsame-prog/somaliland-geodata-portal.git"
APP_USER="geoportal"
APP_DIR="/srv/geoportal"
DATA_DIR="/srv/geoportal-data"          # uploaded datasets (back this up!)

echo "==> Installing system packages"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-dev build-essential libpq-dev \
  postgresql nginx certbot python3-certbot-nginx git ufw

echo "==> Creating app user and folders"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash "$APP_USER"
mkdir -p "$APP_DIR" "$DATA_DIR/private_media" "$DATA_DIR/media"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR" "$DATA_DIR"

echo "==> Downloading the portal code"
if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git clone "$REPO" "$APP_DIR"
else
  sudo -u "$APP_USER" git -C "$APP_DIR" pull
fi

echo "==> Creating PostgreSQL database"
DB_PASS="$(openssl rand -hex 16)"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='geoportal'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE USER geoportal WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='geoportal'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE geoportal OWNER geoportal;"

echo "==> Writing configuration (.env)"
if [ ! -f "$APP_DIR/.env" ]; then
  # The DB password is only set here when the user is created on first run.
  sudo -u postgres psql -c "ALTER USER geoportal WITH PASSWORD '$DB_PASS';"
  cat > "$APP_DIR/.env" <<EOF
DJANGO_SECRET_KEY=$(openssl rand -hex 40)
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN
DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN
DATABASE_ENGINE=postgresql
DATABASE_NAME=geoportal
DATABASE_USER=geoportal
DATABASE_PASSWORD=$DB_PASS
DATABASE_HOST=localhost
DATABASE_PORT=5432
PRIVATE_MEDIA_ROOT=$DATA_DIR/private_media
MEDIA_ROOT=$DATA_DIR/media
MAX_UPLOAD_MB=2048
PORTAL_ORGANIZATION=Somaliland GeoData Portal Team
CONTRIBUTE_TELEGRAM_URL=https://t.me/your_telegram_username
CONTRIBUTE_TELEGRAM_HANDLE=@your_telegram_username
CONTRIBUTE_EMAIL=data@example.org
EOF
  chown "$APP_USER":"$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi

echo "==> Installing Python packages and preparing the app"
sudo -u "$APP_USER" bash -c "
  cd $APP_DIR
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
  .venv/bin/python manage.py makemigrations organizations accounts datasets
  .venv/bin/python manage.py migrate --noinput
  .venv/bin/python manage.py collectstatic --noinput
  .venv/bin/python manage.py seed_portal
  .venv/bin/python manage.py import_boundaries || true
"

echo "==> Installing the web service (gunicorn)"
cp "$APP_DIR/deploy/geoportal.service" /etc/systemd/system/geoportal.service
systemctl daemon-reload
systemctl enable --now geoportal

echo "==> Configuring Nginx"
sed "s/__DOMAIN__/$DOMAIN/g; s#__APP_DIR__#$APP_DIR#g; s#__DATA_DIR__#$DATA_DIR#g" \
  "$APP_DIR/deploy/nginx.conf" > /etc/nginx/sites-available/geoportal
ln -sf /etc/nginx/sites-available/geoportal /etc/nginx/sites-enabled/geoportal
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> Firewall"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "==> HTTPS certificate"
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect \
  || echo "!! HTTPS failed. Check that $DOMAIN points to this server, then run: certbot --nginx -d $DOMAIN"

echo
echo "============================================================"
echo " Done. Open https://$DOMAIN"
echo " Create your administrator account:"
echo "   sudo -u $APP_USER $APP_DIR/.venv/bin/python $APP_DIR/manage.py createsuperuser"
echo " Edit Telegram/email/organization in: $APP_DIR/.env"
echo "   then: sudo systemctl restart geoportal"
echo " Back up daily: the 'geoportal' database and $DATA_DIR"
echo "============================================================"
