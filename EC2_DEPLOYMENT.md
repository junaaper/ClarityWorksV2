# ClarityWorks — Single EC2 Deployment Guide

> Host the entire stack (React frontend, Express backend, Flask ML service, PostgreSQL, ChromaDB) on one EC2 instance using your $50 AWS credits.

---

## 1. Launch the EC2 Instance

1. Go to **AWS Console → EC2 → Launch Instance**
2. Settings:
   - **Name:** `clarityworks`
   - **AMI:** Ubuntu 22.04 LTS (free tier eligible)
   - **Instance type:** `t3.medium` (2 vCPU, 4 GB RAM) — the ML models + ChromaDB + spaCy need ~3 GB RAM. A `t3.small` (2 GB) will OOM.
   - **Key pair:** Create or select an existing `.pem` key
   - **Storage:** 30 GB gp3 (default 8 GB is too small for models + ChromaDB data)
   - **Security group:** Allow these inbound rules:
     - SSH (port 22) — your IP only
     - HTTP (port 80) — anywhere (0.0.0.0/0)
     - HTTPS (port 443) — anywhere (0.0.0.0/0)

3. Launch and note the **Public IPv4 address** (e.g., `3.15.xx.xx`)

### Cost estimate
`t3.medium` in us-east-1 = ~$0.0416/hr = **~$30/month**. Your $50 covers ~5 weeks. You can stop the instance when not using it to save credits.

---

## 2. SSH Into the Instance

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<YOUR_EC2_IP>
```

---

## 3. Install System Dependencies

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Python 3.10+ (comes with Ubuntu 22.04)
sudo apt install -y python3 python3-pip python3-venv

# Node.js 18 LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# PostgreSQL 14
sudo apt install -y postgresql postgresql-contrib

# Tesseract OCR (for image text extraction)
sudo apt install -y tesseract-ocr

# Build tools (needed for some Python packages)
sudo apt install -y build-essential libpq-dev

# Nginx (reverse proxy)
sudo apt install -y nginx

# PM2 (Node.js process manager)
sudo npm install -g pm2
```

---

## 4. Set Up PostgreSQL

```bash
sudo -u postgres psql
```

Inside the PostgreSQL shell:

```sql
CREATE DATABASE clarityworks_db;
CREATE USER clarityworks_user WITH PASSWORD 'clarityworks_pass';
GRANT ALL PRIVILEGES ON DATABASE clarityworks_db TO clarityworks_user;
\c clarityworks_db
GRANT ALL ON SCHEMA public TO clarityworks_user;
\q
```

---

## 5. Clone the Repository

```bash
cd /home/ubuntu
git clone https://github.com/<YOUR_USERNAME>/clarityworks.git
cd clarityworks
```

---

## 6. Set Up the ML Service (Flask — Port 5001)

```bash
cd /home/ubuntu/clarityworks/ml-service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Download NLTK data (for WordNet synonyms)
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"

# Create .env file
cat > .env << 'EOF'
FLASK_PORT=5001
FLASK_ENV=production
TESSERACT_PATH=/usr/bin/tesseract
FIREWORKS_API_KEY=<YOUR_FIREWORKS_API_KEY>
EOF

# Create persistent ChromaDB directory
mkdir -p /home/ubuntu/clarityworks/ml-service/data/chromadb

deactivate
```

> **ChromaDB persistence:** ChromaDB stores its data in `ml-service/data/chromadb/`. This directory persists across restarts. As long as you don't delete this folder or the EBS volume, your uploaded textbook chunks survive reboots.

---

## 7. Set Up the Backend (Express — Port 5000)

```bash
cd /home/ubuntu/clarityworks/backend

# Install dependencies
npm install

# Create .env file
cat > .env << 'EOF'
PORT=5000
DATABASE_URL=postgresql://clarityworks_user:clarityworks_pass@localhost:5432/clarityworks_db
JWT_SECRET=change_this_to_a_long_random_string_abc123xyz
PYTHON_SERVICE_URL=http://localhost:5001
NODE_ENV=production
EOF
```

---

## 8. Build the Frontend (React → Static Files)

The frontend is served as static files through Nginx — no dev server in production.

```bash
cd /home/ubuntu/clarityworks/frontend

# Install dependencies
npm install

# Create .env for production build
cat > .env << 'EOF'
VITE_API_URL=http://<YOUR_EC2_IP>
VITE_PYTHON_API_URL=http://<YOUR_EC2_IP>/ml
EOF

# Build static files
npm run build
# Output goes to frontend/dist/
```

> Replace `<YOUR_EC2_IP>` with your actual EC2 public IP (e.g., `http://3.15.42.100`). If you add a domain later, change it to `https://yourdomain.com`.

---

## 9. Configure Nginx (Reverse Proxy)

Nginx serves the frontend static files and proxies API requests to the backend and ML service.

```bash
sudo nano /etc/nginx/sites-available/clarityworks
```

Paste this configuration:

```nginx
server {
    listen 80;
    server_name _;

    # Frontend — serve static React build
    root /home/ubuntu/clarityworks/frontend/dist;
    index index.html;

    # React SPA — all non-API routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 110M;  # For RAG document uploads (100MB)
    }

    # ML Service proxy (for direct frontend calls)
    location /ml/ {
        rewrite ^/ml/(.*) /$1 break;
        proxy_pass http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 110M;
    }

    # Upload directories
    location /uploads/ {
        alias /home/ubuntu/clarityworks/backend/uploads/;
    }
}
```

Enable the site:

```bash
sudo ln -sf /etc/nginx/sites-available/clarityworks /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t          # Test config
sudo systemctl restart nginx
```

---

## 10. Start Services with PM2

PM2 keeps the backend and ML service running (auto-restart on crash, startup on reboot).

```bash
# Start ML Service (Flask)
pm2 start /home/ubuntu/clarityworks/ml-service/venv/bin/python \
  --name "ml-service" \
  --cwd /home/ubuntu/clarityworks/ml-service \
  -- app.py

# Start Backend (Express)
pm2 start npm \
  --name "backend" \
  --cwd /home/ubuntu/clarityworks/backend \
  -- run dev

# Check both are running
pm2 status

# Save PM2 process list + set up auto-start on reboot
pm2 save
pm2 startup
# Run the command PM2 prints (sudo env PATH=... pm2 startup ...)
```

### Verify services are up

```bash
# ML service health
curl http://localhost:5001/health

# Backend (should return 401 since no JWT)
curl http://localhost:5000/api/auth/me

# Frontend (should return HTML)
curl http://localhost:80
```

---

## 11. Open in Browser

Navigate to `http://<YOUR_EC2_IP>` — you should see the ClarityWorks login page.

---

## 12. (Optional) Custom Domain + HTTPS

If you have a domain:

```bash
# Point your domain's A record to EC2_IP, then:

# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is set up automatically
```

Update your frontend `.env` to use `https://yourdomain.com` and rebuild:

```bash
cd /home/ubuntu/clarityworks/frontend
# Edit .env: VITE_API_URL=https://yourdomain.com
npm run build
```

---

## Quick Reference

| Service | Port | Process Manager | Log Command |
|---------|------|-----------------|-------------|
| Frontend | 80/443 (Nginx) | systemd | `sudo journalctl -u nginx` |
| Backend | 5000 | PM2 | `pm2 logs backend` |
| ML Service | 5001 | PM2 | `pm2 logs ml-service` |
| PostgreSQL | 5432 | systemd | `sudo journalctl -u postgresql` |
| ChromaDB | embedded | (inside ML service) | `pm2 logs ml-service` |

### Persistent Data Locations

| Data | Path | Survives Reboot? |
|------|------|------------------|
| PostgreSQL DB | `/var/lib/postgresql/14/main/` | Yes (EBS) |
| ChromaDB vectors | `ml-service/data/chromadb/` | Yes (EBS) |
| RAG uploaded docs | `backend/uploads/documents/` | Yes (EBS) |
| Profile pictures | `backend/uploads/profiles/` | Yes (EBS) |
| Trained ML models | `ml-service/trained_models/` | Yes (EBS) |

### Common Commands

```bash
# Restart everything
pm2 restart all

# View logs (live)
pm2 logs

# Stop everything
pm2 stop all

# Rebuild frontend after changes
cd /home/ubuntu/clarityworks/frontend && npm run build

# Retrain ML model
cd /home/ubuntu/clarityworks/ml-service
source venv/bin/activate
python train_model.py
```

### Troubleshooting

| Problem | Fix |
|---------|-----|
| ML service OOM | Upgrade to `t3.medium` or add 2 GB swap: `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |
| Port 80 blocked | Check EC2 security group allows HTTP inbound |
| ChromaDB empty after redeploy | Make sure `ml-service/data/chromadb/` wasn't deleted — it's the persistent store |
| PDF upload fails | Check `client_max_body_size 110M` in Nginx config |
| spaCy model missing | `source venv/bin/activate && python -m spacy download en_core_web_sm` |
| Tesseract not found | Verify path: `which tesseract` → update `.env` TESSERACT_PATH |

---

## Adding Swap (Recommended for t3.medium)

4 GB RAM is tight. Add swap as a safety net:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make persistent across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
