# EC2 Instance Setup from Scratch

Complete guide to provision a new EC2 instance, configure Cloudflare Tunnel,
and deploy a Dockerized app under a custom domain.

---

## Overview

```
User → Cloudflare (DNS + SSL + CDN) → Cloudflare Tunnel → EC2 (Nginx + Docker)
```

No Elastic IP needed. Cloudflare Tunnel handles inbound traffic securely.

---

## Part 1: AWS — Launch EC2 Instance

### 1.1 Launch Instance

1. Go to **AWS Console → EC2 → Launch Instance**
2. Settings:
   - **Name**: give it a meaningful name (e.g., `aiwithamit-server`)
   - **AMI**: Ubuntu Server 24.04 LTS (64-bit x86)
   - **Instance type**: `t3.small` (2 vCPU, 2GB RAM) — handles 4-5 small apps
   - **Key pair**: Create new → download `.pem` file → store safely
3. **Network settings**:
   - Create a new security group with these inbound rules:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | My IP | Terminal access |
| HTTP | 80 | 0.0.0.0/0 | Nginx (Cloudflare Tunnel uses this) |

> No need for port 443 — Cloudflare handles SSL termination.

4. **Storage**: 20GB gp3 (default 8GB is fine for small apps, increase if needed)
5. Click **Launch Instance**

### 1.2 Note the Public IP

Go to EC2 → Instances → copy the **Public IPv4 address**.
You'll use this temporarily for SSH. No Elastic IP needed if using Cloudflare Tunnel.

### 1.3 SSH into the Instance

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

---

## Part 2: EC2 — Install Dependencies

Run all commands as `ubuntu` user (use `sudo` where required).

### 2.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Install Docker

```bash
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker

# Allow ubuntu user to run docker without sudo
sudo usermod -aG docker ubuntu
newgrp docker

# Verify
docker --version
```

### 2.3 Install Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx

# Verify
sudo systemctl status nginx
```

### 2.4 Install Git

```bash
sudo apt install -y git

# Verify
git --version
```

### 2.5 Install cloudflared

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
  -o cloudflared
sudo mv cloudflared /usr/local/bin/
sudo chmod +x /usr/local/bin/cloudflared

# Verify
cloudflared --version
```

---

## Part 3: Cloudflare — Create Tunnel

### 3.1 Login to Cloudflare

```bash
cloudflared tunnel login
```

This prints a URL. Open it in your browser and authorize your domain (`aiwithamit.in`).
A certificate file will be saved to `~/.cloudflared/cert.pem`.

### 3.2 Create a Tunnel

```bash
cloudflared tunnel create my-tunnel
```

Note the **tunnel ID** printed (e.g., `07790caa-1c7d-4738-aa7b-99c29f9e432b`).
A credentials JSON file is saved to `~/.cloudflared/<tunnel-id>.json`.

### 3.3 Create Tunnel Config

```bash
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

```yaml
tunnel: <your-tunnel-id>
credentials-file: /etc/cloudflared/<tunnel-id>.json

ingress:
  - hostname: your-app.aiwithamit.in
    service: http://localhost:8000
  - service: http_status:404
```

> Add one `hostname` entry per app. The final `http_status:404` line must always be last.

### 3.4 Copy Config to System Directory

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/config.yml /etc/cloudflared/
sudo cp ~/.cloudflared/<tunnel-id>.json /etc/cloudflared/
```

### 3.5 Register DNS Route

This creates a CNAME record in Cloudflare pointing your subdomain to the tunnel:

```bash
cloudflared tunnel route dns my-tunnel your-app.aiwithamit.in
```

Verify in Cloudflare dashboard → DNS → you should see a CNAME record for `your-app`
pointing to `<tunnel-id>.cfargotunnel.com`.

### 3.6 Install Tunnel as System Service

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# Verify
sudo systemctl status cloudflared
```

---

## Part 4: Nginx — Configure Reverse Proxy

### 4.1 Remove Default Site

```bash
sudo rm /etc/nginx/sites-enabled/default
```

### 4.2 Create App Config

```bash
sudo tee /etc/nginx/sites-available/your-app << 'EOF'
server {
    listen 80;
    server_name your-app.aiwithamit.in;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/your-app /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## Part 5: Deploy the App

### 5.1 Clone the Repository

```bash
cd ~
git clone <your-repo-url> your-app
cd your-app
```

### 5.2 Create .env File

```bash
nano .env
```

```
OPENROUTER_API_KEY=sk-or-your-key-here
DATABASE_URL=/data/app.db
```

```bash
chmod 600 .env
```

> Never commit `.env` to git. Keep it only on the server.

### 5.3 Build Docker Image

```bash
docker build -t your-app .
```

### 5.4 Run the Container

```bash
docker run -d \
  --name your-app \
  --restart unless-stopped \
  -p 8000:8000 \
  -v your-app-data:/data \
  --env-file .env \
  your-app
```

| Flag | Purpose |
|------|---------|
| `-d` | Run in background |
| `--restart unless-stopped` | Auto-restart on EC2 reboot |
| `-p 8000:8000` | Map host port to container port |
| `-v your-app-data:/data` | Persist data (SQLite, uploads, etc.) |
| `--env-file .env` | Inject secrets at runtime (not baked into image) |

### 5.5 Verify

```bash
# Container running?
docker ps

# App responding?
curl http://localhost:8000/api/health

# Nginx proxying?
curl http://localhost:80

# Full end-to-end
curl https://your-app.aiwithamit.in/api/health
```

---

## Part 6: Cloudflare Dashboard Settings

1. Go to **SSL/TLS → Overview** → set mode to **Flexible**
   (EC2 runs HTTP only; Cloudflare handles HTTPS to the user)
2. Go to **SSL/TLS → Edge Certificates** → enable **Always Use HTTPS**

---

## Part 7: Verify Everything Works

```bash
# All containers running
docker ps

# Nginx status
sudo systemctl status nginx

# Tunnel status
sudo systemctl status cloudflared

# Test app via domain
curl https://your-app.aiwithamit.in
```

Visit `https://your-app.aiwithamit.in` in browser — should load your app over HTTPS.

---

## Part 8: Adding More Apps Later

See [DEPLOY_NEW_APP.md](./DEPLOY_NEW_APP.md) for step-by-step instructions.

Quick summary for each new app:
1. Run container on a new port (8001, 8002, ...)
2. Add Nginx config for the new subdomain
3. Add entry in `/etc/cloudflared/config.yml`
4. Run `cloudflared tunnel route dns my-tunnel new-subdomain.aiwithamit.in`
5. Restart cloudflared: `sudo systemctl restart cloudflared`

---

## Quick Reference

### Useful Commands

| Task | Command |
|------|---------|
| SSH into EC2 | `ssh -i your-key.pem ubuntu@<EC2-IP>` |
| List running containers | `docker ps` |
| View app logs | `docker logs your-app` |
| Restart app | `docker restart your-app` |
| Rebuild & redeploy | See update script below |
| Nginx status | `sudo systemctl status nginx` |
| Reload Nginx | `sudo systemctl reload nginx` |
| Tunnel status | `sudo systemctl status cloudflared` |
| Restart tunnel | `sudo systemctl restart cloudflared` |
| Tunnel logs | `sudo journalctl -xeu cloudflared --no-pager` |
| Free disk space | `df -h` |
| Memory usage | `free -h` |
| CPU + memory live | `htop` |

### Update Script

Save as `~/update-app.sh` for one-command deploys:

```bash
#!/bin/bash
APP=$1
PORT=$2

cd ~/$APP
git pull
docker build -t $APP .
docker stop $APP && docker rm $APP
docker run -d \
  --name $APP \
  --restart unless-stopped \
  -p $PORT:8000 \
  -v $APP-data:/data \
  --env-file .env \
  $APP

echo "Done. $APP running on port $PORT"
```

```bash
chmod +x ~/update-app.sh

# Usage
./update-app.sh kanban 8000
./update-app.sh my-other-app 8001
```

---

## Installed Software Summary

| Software | Purpose | Install method |
|----------|---------|----------------|
| Docker | Container runtime | `apt install docker.io` |
| Nginx | Reverse proxy | `apt install nginx` |
| Git | Clone repos | `apt install git` |
| cloudflared | Cloudflare Tunnel | Manual binary download |

---

## Cost Estimate (ap-south-1 / us-east-1)

| Resource | Monthly Cost |
|----------|-------------|
| t3.small (24/7) | ~$15 |
| EBS 20GB gp3 | ~$1.60 |
| No Elastic IP (tunnel) | $0 |
| Cloudflare Tunnel | Free |
| **Total** | **~$17/mo** |

With $600 AWS credits → ~3 years of runtime.
