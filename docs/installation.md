# Installation Guide

Prerequisites: a running Debian 12 LXC with Docker installed. See [LXC Setup](lxc-setup.md) if you haven't done that yet.

---

## 1. Clone the Repository

```bash
cd /opt
git clone https://github.com/chelohomelab/reloading-and-inventory.git
cd reloading-and-inventory
```

---

## 2. Build and Start the Container

```bash
docker compose up -d --build
```

Docker will:
- Build the Python image
- Create `data/` (SQLite database) and `uploads/` (photos) directories on the host
- Start the app on port **8000**

Verify it is running:

```bash
docker compose ps
docker compose logs -f   # Ctrl+C to exit
```

---

## 3. First-Time Setup

Open a browser and navigate to:

```
http://<lxc-ip>:8000/setup
```

Create the first admin account. After submitting you are redirected to the login page. This `/setup` endpoint is automatically disabled once at least one user exists.

---

## 4. Directory Structure After First Run

```
reloading-and-inventory/
├── data/
│   └── reloading.db      ← SQLite database (persistent)
├── uploads/              ← Photo uploads (persistent)
└── ...
```

Both `data/` and `uploads/` are mounted as Docker volumes, so they survive container rebuilds and updates.

---

## 5. Updating the Application

```bash
cd /opt/reloading-and-inventory
git pull
docker compose up -d --build
```

The database and uploads are untouched. The app is typically back online in under 30 seconds.

---

## 6. (Optional) HTTPS with a Reverse Proxy

For HTTPS access from outside your LAN, put a reverse proxy in front of port 8000. Two common options on Proxmox:

### Option A — Nginx Proxy Manager (recommended for beginners)
- Deploy NPM as a separate LXC or Docker container
- Add a **Proxy Host** pointing to `http://<lxc-ip>:8000`
- Enable **Force SSL** and request a Let's Encrypt certificate

### Option B — Caddy
```bash
apt install -y caddy
```

`/etc/caddy/Caddyfile`:
```
inventory.yourdomain.com {
    reverse_proxy localhost:8000
}
```

```bash
systemctl reload caddy
```

Caddy handles TLS automatically via Let's Encrypt.

---

## 7. Stopping / Removing the App

```bash
# Stop (data preserved)
docker compose down

# Stop and remove the image (data preserved)
docker compose down --rmi all
```

---

## Next Step

Continue to the [User Guide](user-guide.md) to learn how to use the application.
