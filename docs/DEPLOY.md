# Guía de deploy — Sistema de Preliquidación

Cómo poner el sistema en producción (hosting). Decidido en sesión de asesoría; ver también [`DOCUMENTACION.md`](DOCUMENTACION.md).

## ⚡ ESTADO ACTUAL: EN PRODUCCIÓN (desde 2026-07-23)

- **URL**: `http://179.197.237.196` (VPS Hostinger KVM 1, São Paulo — mismo datacenter que la base; ping backend↔base ~7ms).
- **Layout en el VPS**: backend en `/home/deploy/backend` (servicio systemd `preliquidacion`, uvicorn en 127.0.0.1:8000), frontend estático en `/home/deploy/frontend`, nginx adelante. `.env` de producción en `/home/deploy/backend/.env` (SECRET_KEY propio, distinto al de desarrollo).
- **Pendiente**: subdominio de la empresa (lo gestiona un tercero) + HTTPS con certbot + actualizar `FRONTEND_URL`; confirmar backups de la base en Hostinger.

### Regla de trabajo: el deploy SIEMPRE se autoriza explícitamente

Pushear a GitHub **no** toca producción. Producción solo cambia cuando alguien ejecuta el deploy en el VPS. La regla acordada:

> **Nadie (incluido el asistente) impacta cambios en producción sin la autorización explícita del responsable del sistema.** El flujo es: desarrollar y probar en local → commit/push a GitHub → **pedir OK para deployar** → recién ahí ejecutar el deploy en el VPS.

**Ojo con el dato**: la base de datos es una sola (desarrollo y producción comparten `preliquidacion`). Los cambios de **datos** hechos desde el entorno local (generar quincenas, precios, usuarios) impactan al instante en lo que ven los usuarios — esta regla de autorización aplica al **código**.

### Cómo se ejecuta el deploy (una vez autorizado)

```bash
# Backend (corte de ~10s):
ssh root@179.197.237.196 "cd /home/deploy/backend && sudo -u deploy git pull && sudo -u deploy .venv/bin/pip install -q -r requirements.txt && systemctl restart preliquidacion && sleep 5 && curl -s http://127.0.0.1:8000/health"

# Frontend (sin corte) — desde la máquina de desarrollo:
cd frontend_preliquidacion && npm run build
scp -r dist/* root@179.197.237.196:/home/deploy/frontend/

# Migraciones nuevas (migrations/wsN.sql): correrlas contra la base ANTES o junto
# con el deploy del código que las necesita.
```

## Arquitectura

**Un solo VPS** en **Hostinger, región São Paulo (Brasil)** — la misma red donde vive la base MySQL (`191.101.235.7`). El factor #1 de latencia es la distancia backend↔base (el sistema hace muchas queries por acción); por eso el backend va **pegado a la base**, no cerca de los usuarios. El frontend es estático y chico → se sirve del mismo VPS.

```
Usuario (Argentina) ──HTTPS, 1 dominio──► VPS São Paulo
                                          ├─ nginx:  /       → frontend estático (dist/)
                                          │          /api/…  → uvicorn 127.0.0.1:8000
                                          └─ uvicorn (systemd) ──► MySQL (localhost / red interna)
```

## Requisitos previos (pedir a quien administra el server)

- **VPS KVM** en Hostinger São Paulo: 1-2 vCPU, **2-4 GB RAM**, ~40 GB disco, **Ubuntu 22.04/24.04 LTS**, con **acceso SSH root**.
  - Ideal: si el server de la base ya es un VPS, correr el backend **en esa misma máquina** (MySQL por `localhost`, latencia cero).
  - Si es un VPS aparte: pedir que **habiliten la IP del VPS** para conectarse a MySQL.
- **Subdominio** de tu dominio (ej. `preliquidacion.tudominio.com`) con un **registro DNS A** apuntando a la IP del VPS.
- **Backups de la base:** confirmar con el tercero que se hacen (Hostinger tiene backups automáticos). Es lo único de "caídas/pérdida" que no depende del VPS.

---

## Pasos

> **Atajo:** los pasos 1-6 están automatizados en [`deploy/provision.sh`](../deploy/provision.sh)
> (usa [`deploy/preliquidacion.service`](../deploy/preliquidacion.service) y
> [`deploy/nginx-preliquidacion.conf`](../deploy/nginx-preliquidacion.conf)). En el VPS nuevo, como root:
> `DOMAIN=preliquidacion.tudominio.com bash provision.sh` — y quedan solo los pendientes
> manuales que imprime al final (.env, rsync del front, certbot). Los pasos de abajo
> siguen valiendo como referencia/explicación.

### 1. Base del VPS
```bash
# como root
apt update && apt upgrade -y
adduser deploy && usermod -aG sudo deploy       # usuario no-root para operar
# Firewall: solo SSH + HTTP + HTTPS
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
apt install -y python3-venv python3-pip nginx git
```

### 2. Backend
```bash
sudo -iu deploy
git clone https://github.com/Gerorios/Preliquidador_AST_BK.git ~/backend
cd ~/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# crear el .env con las credenciales de las 3 bases (ver .env.example).
# Si el backend está en la MISMA máquina que MySQL, usar host=127.0.0.1.
nano .env
```

### 3. uvicorn como servicio (systemd) — reinicia solo, arranca al bootear
`/etc/systemd/system/preliquidacion.service`:
```ini
[Unit]
Description=Preliquidacion backend (uvicorn)
After=network.target

[Service]
User=deploy
WorkingDirectory=/home/deploy/backend
ExecStart=/home/deploy/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now preliquidacion
sudo systemctl status preliquidacion        # verificar que esté "active (running)"
```
> **Workers:** arrancar con **1 worker** (el cache del maestro de sueldos —15-19k empleados— es por proceso; el diseño asume single-worker). Con pocos usuarios alcanza. Si más adelante notás que las requests se encolan detrás de un "generar quincena" largo, subí a `--workers 2`, teniendo en cuenta que el cache de sueldos pasa a ser por worker (el botón "refrescar sueldos" refresca solo el worker que atiende; ante la duda, reiniciar el servicio).

### 4. Frontend (estático)
En tu máquina (o en el VPS): `npm run build` en el repo del front, y copiar `dist/` al VPS:
```bash
# desde tu máquina, tras 'npm run build' en frontend_preliquidacion/
rsync -avz --delete dist/ deploy@IP_DEL_VPS:/home/deploy/frontend/
```

### 5. nginx — sirve el front y proxya /api
`/etc/nginx/sites-available/preliquidacion`:
```nginx
server {
    listen 80;
    server_name preliquidacion.tudominio.com;

    root /home/deploy/frontend;
    index index.html;

    # SPA: cualquier ruta no-archivo cae en index.html (React Router)
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;   # "generar quincena" puede tardar; margen amplio
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/preliquidacion /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 6. HTTPS (Let's Encrypt, gratis)
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d preliquidacion.tudominio.com
# certbot edita el nginx para HTTPS y renueva solo (timer systemd)
```

### 7. CORS / config del backend
Como el front y el back quedan bajo el **mismo dominio** (nginx sirve los dos), **no hay CORS entre ellos**. Verificar en el `.env` que `frontend_url` apunte al dominio final (por si algún header lo usa).

---

## Actualizar (deploy de cambios)

- **Backend:** `cd ~/backend && git pull && source .venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart preliquidacion`
- **Frontend:** `npm run build` local + el `rsync` del paso 4 (no requiere reiniciar nada).
- **Migraciones:** las nuevas (`migrations/wsN.sql`) se corren **una vez** contra la base. Ojo: las que agregan columnas/tablas **no son diferibles** (correr antes/junto con el deploy de esa versión).

## Checklist de "no tener problemas a futuro"

- [x] Backend pegado a la base (mismo VPS/red São Paulo) → latencia mínima.
- [x] `systemd Restart=always` → si el backend crashea, vuelve solo; y arranca al bootear.
- [x] nginx adelante → sirve estáticos rápido y aísla el uvicorn.
- [x] HTTPS con renovación automática.
- [ ] **Backups de la base** confirmados con el tercero (Hostinger automated backups).
- [ ] (Opcional) Monitoreo de uptime externo (UptimeRobot, gratis) que te avise si el sitio se cae.
- [ ] (Opcional) `logrotate` para los logs de uvicorn si crecen.
