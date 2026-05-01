# Deploying a New App on the Same EC2 Instance

This guide covers adding a new app to the EC2 instance at `aiwithamit.in` using
Cloudflare Tunnel + Nginx + Docker.

---

## Prerequisites

- EC2 instance running with cloudflared tunnel active
- Cloudflare managing `aiwithamit.in` DNS
- Docker installed on EC2
- SSH access to EC2

---

## Step 1: Build & Push Your Docker Image

On your **local machine**, build and push the image to Docker Hub (or ECR):

```bash
docker build -t yourdockerhubuser/app-name:latest .
docker push yourdockerhubuser/app-name:latest
```

Or copy files directly to EC2 and build there:

```bash
scp -i your-key.pem -r ./your-app ubuntu@<EC2-IP>:~/your-app
```

---

## Step 2: SSH into EC2

```bash
ssh -i your-key.pem ubuntu@<EC2-IP>
```

---

## Step 3: Pick a Free Port

Each app needs a unique host port. Check what's already in use:

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

Common convention:
| App | Port |
|-----|------|
| kanban (existing) | 8000 |
| new-app-1 | 8001 |
| new-app-2 | 8002 |

---

## Step 4: Create .env File for the New App

```bash
mkdir -p ~/your-app
nano ~/your-app/.env
```

Add required environment variables:
```
SOME_API_KEY=your-key-here
DATABASE_URL=/data/app.db
```

---

## Step 5: Run the Docker Container

```bash
docker run -d \
  --name your-app-name \
  --restart unless-stopped \
  -p 8001:8000 \
  -v your-app-data:/data \
  --env-file ~/your-app/.env \
  yourdockerhubuser/app-name:latest
```

- `-p 8001:8000` — maps host port 8001 to container port 8000 (adjust as needed)
- `-v your-app-data:/data` — persists SQLite or other file data
- `--restart unless-stopped` — auto-starts on EC2 reboot

Verify it's running:
```bash
docker ps
curl http://localhost:8001/api/health
```

---

## Step 6: Add Nginx Config

```bash
sudo tee /etc/nginx/sites-available/your-app << 'EOF'
server {
    listen 80;
    server_name your-subdomain.aiwithamit.in;

    location / {
        proxy_pass http://localhost:8001;
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

## Step 7: Add App to Cloudflare Tunnel Config

```bash
sudo nano /etc/cloudflared/config.yml
```

Add a new entry under `ingress` (before the final `http_status:404` line):

```yaml
tunnel: <your-tunnel-id>
credentials-file: /etc/cloudflared/<tunnel-id>.json

ingress:
  - hostname: kanban.aiwithamit.in       # existing app
    service: http://localhost:8000
  - hostname: your-subdomain.aiwithamit.in   # new app
    service: http://localhost:8001
  - service: http_status:404             # must always be last
```

Restart the tunnel:
```bash
sudo systemctl restart cloudflared
sudo systemctl status cloudflared
```

---

## Step 8: Add DNS Record in Cloudflare

```bash
cloudflared tunnel route dns <tunnel-name> your-subdomain.aiwithamit.in
```

Or manually in Cloudflare dashboard:
- DNS → Add record
- Type: `CNAME`
- Name: `your-subdomain`
- Target: `<tunnel-id>.cfargotunnel.com`
- Proxy: Enabled (orange cloud)

---

## Step 9: Verify

```bash
# Check tunnel is routing correctly
curl https://your-subdomain.aiwithamit.in/api/health
```

Visit `https://your-subdomain.aiwithamit.in` in browser.

---

## Updating an Existing App

```bash
cd ~/your-app
git pull

# Rebuild image
docker build -t your-app-name .

# Replace running container
docker stop your-app-name && docker rm your-app-name
docker run -d \
  --name your-app-name \
  --restart unless-stopped \
  -p 8001:8000 \
  -v your-app-data:/data \
  --env-file ~/your-app/.env \
  your-app-name
```

---

## Removing an App

```bash
# Stop and remove container
docker stop your-app-name && docker rm your-app-name

# Remove Nginx config
sudo rm /etc/nginx/sites-enabled/your-app
sudo rm /etc/nginx/sites-available/your-app
sudo nginx -t && sudo systemctl reload nginx

# Remove from Cloudflare tunnel config
sudo nano /etc/cloudflared/config.yml   # delete the hostname entry
sudo systemctl restart cloudflared

# Delete DNS record in Cloudflare dashboard manually
```

---

## Quick Reference

| What | Command |
|------|---------|
| List running apps | `docker ps` |
| View app logs | `docker logs your-app-name` |
| Check tunnel status | `sudo systemctl status cloudflared` |
| Check nginx status | `sudo systemctl status nginx` |
| Reload nginx | `sudo systemctl reload nginx` |
| Restart tunnel | `sudo systemctl restart cloudflared` |
| Used ports | `docker ps --format "table {{.Names}}\t{{.Ports}}"` |
