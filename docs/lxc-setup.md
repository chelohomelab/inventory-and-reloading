# Proxmox LXC Setup

This guide covers creating the Proxmox LXC container that will host the application.

---

## 1. Download a Container Template

In the Proxmox web UI:

1. Select your node → **local** storage → **CT Templates**
2. Click **Templates** and download **Debian 12 (Bookworm)**

---

## 2. Create the LXC Container

In the Proxmox web UI click **Create CT** and fill in:

| Field | Recommended value |
|---|---|
| Hostname | `firearm-inventory` |
| Password | Set a strong root password |
| Template | `debian-12-standard_*.tar.zst` |
| Disk | 8 GB (expandable later) |
| CPU | 1–2 cores |
| Memory | 512 MB (1024 MB recommended) |
| Swap | 512 MB |
| Network | DHCP or a static IP on your LAN bridge |
| DNS | Use host settings |

> **Tip:** Assign a static IP so the app URL never changes. Either configure it in the LXC network settings or set a DHCP reservation on your router.

Click **Finish**. Start the container, then open a shell via the Proxmox console or SSH.

---

## 3. Update the System

```bash
apt update && apt upgrade -y
```

---

## 4. Install Docker

```bash
# Install prerequisites
apt install -y ca-certificates curl gnupg

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add the Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Compose plugin
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Verify:

```bash
docker --version
docker compose version
```

---

## 5. (Optional) Install Git

```bash
apt install -y git
```

---

## 6. Enable Docker on Boot

```bash
systemctl enable docker
systemctl start docker
```

---

## Next Step

Continue to [Installation Guide](installation.md).
