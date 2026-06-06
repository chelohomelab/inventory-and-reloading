# User Guide

A walkthrough of every feature in the Firearm Inventory & Reloading app.

---

## Navigation Overview

The app is a single-page application. The top navigation bar contains:

- **Inventory** tabs — Rifles, Shotguns, Handguns, Thompson Center
- **Reloading** tab — Component inventory (powders, primers, bullets, casings)
- **Ammo Log** tab — Factory and handloaded ammunition records
- **Range Session** tab — Performance/shot-string log
- **⚙️ Username** (top right) — Your profile and feature preferences
- **Logout**

Admins also have access to **Admin → Users** via the profile page.

---

## Inventory — Firearms

### Adding a Firearm

1. Go to the **Rifles**, **Shotguns**, or **Handguns** tab
2. Click **+ Add** to open the add form
3. Fill in Brand, Model, and Price Paid
4. Optionally upload up to two photos
5. Click **Save**

### Viewing / Editing a Firearm

- Click any firearm card to open its detail page
- The detail page shows all fields, attached barrels, scope, and accessories
- Use the **Edit** button to modify any field
- Use **Upload Photo** to add or replace images

### Marking a Firearm as Sold

On the firearm detail page, click **Mark as Sold**, enter the sale price, and confirm. The firearm moves to the **Sold** view (use the Sold toggle — see below).

### Sold Toggle Filter

At the top right of the inventory panel there is a **Sold** button. Click it to toggle between:

- **Default (off):** shows your active collection
- **Sold (highlighted):** shows items you have sold, with sale prices

The toggle works across all tabs including Thompson Center.

---

## Inventory — Barrels

Barrels are managed from a firearm's detail page. Each firearm can have multiple barrels (useful for multi-caliber platforms). Barrels can have their own scope mounted.

---

## Inventory — Thompson Center

Thompson Center is tracked differently because receivers and barrels are bought and sold independently.

### Receivers

- Add an **Encore** or **Contender** receiver with serial number and price paid
- Mark a receiver as sold (price recorded)
- The Sold toggle filters receivers by sold status

### TC Barrels

- Add barrels with caliber, barrel length, twist rate, hardware color, threading, and muzzle brake details
- TC barrels always show regardless of the Sold toggle (barrels don't have an individual sold status)
- Attach a scope to a TC barrel independently of the receiver

---

## Scopes

Scopes are a shared pool — each scope can be mounted to any firearm or barrel.

- Go to **Scopes** (link in the inventory section or nav)
- Add a scope with brand, model, and adjustment unit (MOA or MIL)
- From a firearm or barrel detail page, use **Mount Scope** to assign a scope inline — no separate screen needed
- A scope mounted to one item is automatically unmounted from any previous item

---

## Reloading Components

The **Reloading** tab tracks on-hand inventory for:

| Section | Tracked fields |
|---|---|
| Powders | Brand, name, weight (lbs), price |
| Primers | Brand, type, quantity, price per 1000 |
| Bullets | Brand, line, caliber, weight (gr), type, BC G1/G7, quantity, price |
| Casings | Brand, caliber, quantity, times fired, price |

### Adding Components

Click **+ Add** in any component section. Fill in the fields and click Save.

### Deducting Components

Use the **Deduct** button to subtract a used quantity (e.g., after a loading session). This keeps your on-hand count accurate.

### Low Stock Alerts

The app shows a warning badge when any component falls below a configurable threshold. Thresholds are set in **Settings** (admin only):

| Setting | Default |
|---|---|
| Powder | 0.5 lbs |
| Primers | 200 |
| Bullets | 100 |
| Casings | 50 |

---

## Ammo Log

Tracks both factory ammunition and handloads for use in the performance log.

- **Factory ammo:** brand, caliber, bullet weight/type, BC
- **Handloads:** same fields plus powder name, charge weight, and COAL
- Attach a photo of the box or load workup sheet

---

## Range Sessions (Performance Log)

Log shot strings from the range or load development.

1. Go to **Range Session**
2. Click **+ New Session**
3. Select the barrel and the ammo used
4. Enter the date and raw velocities (comma-separated: `3010,2995,3005`)
5. The app automatically calculates **Average**, **Extreme Spread (ES)**, and **Standard Deviation (SD)**
6. Optionally upload a target photo and record group size (inches and MOA)

---

## Profile & Feature Preferences

Click **⚙️ Username** in the top nav to open your profile page.

Each user can individually toggle off features they don't use:

| Feature flag | Hides when off |
|---|---|
| Shotguns | Shotguns inventory tab |
| Handguns | Handguns inventory tab |
| Thompson Center | TC inventory tab |
| Reloading | Reloading components tab |
| Ammo Log | Ammo Log tab |

Preferences are saved per-user in the database and apply on every device you log in from.

---

## Settings (Admin)

Accessible from the nav bar (admin users only). Allows editing:

- Low-stock thresholds for reloading components
- Lookup values (dropdown lists for calibers, brands, etc.)

---

## Admin — User Management

Accessible via the profile page for admin accounts.

- **Add users** — create additional accounts for family members or other users
- **Edit users** — change username, email, or password
- **Deactivate / Delete users** — remove access without deleting their data

---

## Tips

- **Photos:** JPEG and PNG are supported. Images are resized for display but the originals are stored.
- **Multi-barrel rifles:** Add the rifle once, then add each barrel from the detail page. Each barrel can have its own scope and performance log.
- **TC workflow:** Add receiver → add barrels → mount scopes per barrel → log range sessions per barrel.
- **Backup:** The entire database is a single file at `data/reloading.db`. Copy it off the server periodically. Photos are in `uploads/`.
