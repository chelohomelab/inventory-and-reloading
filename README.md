# Firearm Inventory & Reloading

A self-hosted homelab app to track your firearm collection and reloading data.

**Stack:** FastAPI · SQLite · Jinja2 · Tailwind CSS · Docker

---

## Documentation

| Guide | Description |
|---|---|
| [LXC Setup](docs/lxc-setup.md) | Create and configure a Proxmox LXC container with Docker |
| [Installation](docs/installation.md) | Deploy the app, first-time setup, and updating |
| [User Guide](docs/user-guide.md) | Feature walkthrough — inventory, reloading, range sessions, profiles |

---

## Quick Start

```bash
git clone https://github.com/chelohomelab/reloading-and-inventory.git
cd reloading-and-inventory
docker compose up -d --build
```

Then open `http://<host-ip>:8000/setup` to create your admin account.

---

## Features

- **Firearm inventory** — Rifles, Shotguns, Handguns with photos and sale tracking
- **Thompson Center** — Receivers and barrels tracked independently
- **Scope management** — Shared scope pool, mount/unmount inline
- **Reloading components** — Powders, primers, bullets, casings with low-stock alerts
- **Ammo log** — Factory and handload records
- **Range sessions** — Chronograph data with automatic ES/SD calculation and target photos
- **Per-user preferences** — Each user can hide features they don't use
- **Multi-user** — Admin-managed accounts
