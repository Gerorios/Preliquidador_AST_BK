#!/usr/bin/env bash
# Aprovisionamiento del VPS de preliquidación (Ubuntu 22.04/24.04).
# Implementa los pasos 1-6 de docs/DEPLOY.md. Correr como root en el VPS nuevo:
#
#   DOMAIN=preliquidacion.tudominio.com bash provision.sh
#
# Es re-ejecutable: si un paso ya está hecho, lo saltea o lo re-aplica sin romper.
set -euo pipefail

DOMAIN="${DOMAIN:?Definí DOMAIN, ej: DOMAIN=preliquidacion.tudominio.com bash provision.sh}"
REPO_BACKEND="https://github.com/Gerorios/Preliquidador_AST_BK.git"

echo "── 1. Base del sistema ──────────────────────────────"
apt update && apt upgrade -y
apt install -y python3-venv python3-pip nginx git ufw

id -u deploy &>/dev/null || adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy

ufw allow OpenSSH && ufw allow 80 && ufw allow 443
ufw --force enable

echo "── 2. Backend ───────────────────────────────────────"
sudo -iu deploy bash <<EOSU
set -euo pipefail
if [ ! -d ~/backend/.git ]; then
  git clone "$REPO_BACKEND" ~/backend
fi
cd ~/backend
git pull
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p ~/frontend
EOSU

if [ ! -f /home/deploy/backend/.env ]; then
  cp /home/deploy/backend/.env.example /home/deploy/backend/.env
  chown deploy:deploy /home/deploy/backend/.env
  chmod 600 /home/deploy/backend/.env
  echo
  echo "⚠️  FALTA COMPLETAR /home/deploy/backend/.env (credenciales de las 3 bases,"
  echo "    secret_key, frontend_url=https://$DOMAIN). El servicio NO va a levantar sin eso."
  echo
fi

echo "── 3. systemd: uvicorn como servicio ────────────────"
cp /home/deploy/backend/deploy/preliquidacion.service /etc/systemd/system/preliquidacion.service
systemctl daemon-reload
systemctl enable --now preliquidacion || true

echo "── 5. nginx ─────────────────────────────────────────"
sed "s/SERVER_NAME_PLACEHOLDER/$DOMAIN/" \
  /home/deploy/backend/deploy/nginx-preliquidacion.conf \
  > /etc/nginx/sites-available/preliquidacion
ln -sf /etc/nginx/sites-available/preliquidacion /etc/nginx/sites-enabled/preliquidacion
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "── 6. HTTPS (Let's Encrypt) ─────────────────────────"
apt install -y certbot python3-certbot-nginx
echo "Cuando el DNS del dominio ya apunte a este VPS, correr:"
echo "  certbot --nginx -d $DOMAIN"

echo
echo "── Listo. Pendientes manuales ───────────────────────"
echo "1. Completar /home/deploy/backend/.env y: systemctl restart preliquidacion"
echo "2. Subir el frontend buildeado (desde tu máquina):"
echo "     rsync -avz --delete dist/ deploy@IP_DEL_VPS:/home/deploy/frontend/"
echo "3. certbot --nginx -d $DOMAIN   (cuando el DNS propague)"
echo "4. Verificar: systemctl status preliquidacion  y  https://$DOMAIN"
