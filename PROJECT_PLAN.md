# 📚 Book-Keep – Full Project Plan

## 1. Project Overview

Book-Keep is a personal web application for tracking books and audiobooks.

The application allows users to:
- add books and audiobooks
- store metadata and notes
- rate entries based on multiple criteria
- automatically calculate final score and tier
- browse, filter, and manage entries

---

## 2. Tech Stack

- **Backend:** Python
- **Framework:** Flask
- **Database:** SQLite
- **Frontend:** HTML + CSS (later upgradeable)
- **Templating:** Jinja2 (Flask templates)

---

## 3. Project Structure

```text
Book-Keep/
│
├── app.py
├── database.py
├── main.py (CLI testing tool)
├── data/
│   └── books.db
├── templates/
│   ├── index.html
│   ├── add.html
│   ├── edit.html
│   ├── details.html
│   └── stats.html
├── static/
│   └── style.css
└── PROJECT_PLAN.md
```

---

## 4. Database Design

### 4.1 Table: `entries`

Stores main information about books/audiobooks.

| Column | Type | Description |
|---|---|---|
| id | INTEGER (PK, AUTOINCREMENT) | Unique ID |
| naslov | TEXT | Title |
| avtor | TEXT | Author |
| tip | TEXT | Type (book / audiobook) |
| zvrst | TEXT | Genre |
| slika_naslovnice | TEXT | Cover image URL |
| kratko_mnenje | TEXT | Short review |
| fav_quote | TEXT | Favorite quote |
| opombe | TEXT | Notes |
| skupna_ocena | REAL | Final score |
| tier | TEXT | Tier |

#### Allowed Values

**tip:**
- book
- audiobook

**zvrst:**
- Fantazija
- Znanstvena fantastika
- Romanca
- Kriminalka
- Triler
- Grozljivka
- Avantura
- Zgodovinski roman
- Mladinski roman
- Realisticni roman
- Self-Help
- Drugo

**tier:**
- S
- A
- B
- C
- D
- F

---

### 4.2 Table: `entry_lengths`

Stores length data.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Primary key |
| entry_id | INTEGER FK | Reference to entry |
| st_strani | INTEGER | Page count |

---

### 4.3 Table: `entry_ratings`

Stores ratings by criteria.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Primary key |
| entry_id | INTEGER FK | Reference to entry |
| kriterij | TEXT | Criterion |
| ocena | REAL | Rating |

#### Allowed `kriterij` values

**Book:**
- zgodba (story)
- liki (characters)
- tempo (pacing)
- slog (writing style)
- custveni_vpliv (emotional impact)

**Audiobook:**
- zgodba
- liki
- tempo
- naracija (narration)
- jasnost_govora (clarity)
- zvocna_izkusnja (audio experience)

---

### 4.4 Table: `rating_settings`

Stores weights for scoring.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Primary key |
| tip | TEXT | Type |
| kriterij | TEXT | Criterion |
| utez | REAL | Weight |
| je_aktiven | INTEGER (0/1) | Active flag |

---

## 5. Current Progress

- [x] Database schema created
- [x] Connection handling
- [x] CRUD (Create, Read, Delete)
- [x] CLI interface
- [x] Flask setup
- [x] Display entries in browser
- [x] Add entry form (basic)
- [x] Dropdown validation

---

## 6. Short-Term Goals

### 6.1 Improve Add Form

- [x] Add all fields (review, quote, notes)
- [x] Add numeric validation
- [x] Add ratings input (dynamic)
- [x] Replace free text with dropdowns where needed

### 6.2 Delete via Flask

- [x] Add delete button
- [x] Route `/delete/<id>`
- [x] Redirect after deletion

### 6.3 Improve UI

- [x] Display clean cards
- [x] Show:
  - title
  - author
  - genre
  - score
  - tier
- [x] Hide technical fields

---

## 7. Mid-Term Goals

### 7.1 Automatic Score Calculation

Instead of manual input:

```python
score = sum(rating * weight) / sum(weights)
```

Tasks:
- [x] Implement `calculate_score()`
- [x] Load weights from DB
- [x] Auto-save score

---

### 7.2 Automatic Tier Calculation

Suggested logic:

| Score | Tier |
|---|---|
| 9–10 | S |
| 8–9 | A |
| 7–8 | B |
| 6–7 | C |
| 5–6 | D |
| <5 | F |

Tasks:
- [x] Implement `calculate_tier()`
- [x] Remove manual tier input

---

### 7.3 Entry Details Page

Route:

```text
/entry/<id>
```

Tasks:
- [x] Show all data
- [x] Show ratings breakdown
- [x] Show length info
- [x] Show notes and quote

---

## 8. Long-Term Features

### 8.1 Edit Entries

- [x] `/edit/<id>`
- [x] Update database
- [x] Pre-fill form

### 8.2 Search & Filtering

- [x] Search by title
- [x] Search by author
- [x] Filter by genre
- [x] Filter by tier
- [x] Sorting

### 8.3 Statistics Page

Examples:
- [x] Total books
- [x] Total audiobooks
- [x] Average score
- [x] Favorite genre
- [x] Total pages read

---

### 8.4 "Hooked" Feature

Goal: create an entry when you start reading, add opinions at checkpoints while reading, and only allow final rating/tier once the book is finished. Include a DNF bucket ("couldn't finish on god").

#### 1. Core Concepts

Entry lifecycle (`status`):
- `in_progress`: started but not finished (no final score/tier)
- `finished`: completed (ratings enabled -> score + tier calculated)
- `dnf`: dropped / couldn't finish (no final score; tier set to special DNF tier)

Checkpoints (fixed enum, in order):
- `pages_5`
- `first_chapter`
- `pct_25`
- `pct_50`
- `pct_80`
- `end`
- `never` (optional marker meaning "not hooked")

At each checkpoint the user can store a short opinion.

#### 2. Data Model / DB Changes

`entries` table changes:
- add `status TEXT NOT NULL CHECK(status IN ('in_progress','finished','dnf')) DEFAULT 'in_progress'`
- add `started_at TEXT`, `finished_at TEXT`, `dnf_at TEXT` (ISO date/time)
- make `skupna_ocena` nullable (only set when `finished`)
- make `tier` nullable except for `dnf`
- add tier `G` = "couldn't finish (on god)" and allow `NULL` for in-progress entries

New table: `entry_checkpoints`
- `id INTEGER PK`
- `entry_id INTEGER FK -> entries.id ON DELETE CASCADE`
- `checkpoint TEXT NOT NULL CHECK(checkpoint IN ('pages_5','first_chapter','pct_25','pct_50','pct_80','end','never'))`
- `opinion TEXT`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `UNIQUE(entry_id, checkpoint)` (one editable opinion per checkpoint per entry)

Ratings behavior:
- keep `entry_ratings` for final ratings
- only allow writing ratings when `status='finished'`

#### 3. Business Rules

- If `status != 'finished'`: ratings inputs are disabled/hidden; `skupna_ocena` and `tier` must be `NULL`
- When switching to `finished`: require ratings (at least active criteria), calculate score and tier (S-F), and set `finished_at`
- When switching to `dnf`: set `tier='G'`, set `skupna_ocena=NULL`, optionally clear ratings, and set `dnf_at`

#### 4. UI / UX Changes

Add (`/add`):
- create entry as `in_progress` by default
- keep form minimal; do not show ratings on create

Details (`/entry/<id>`):
- show status and actions: Mark finished, Mark DNF (on god), optionally back to in-progress
- show checkpoint opinions UI (in order) with save
- show ratings only when finished (or on a dedicated finish page)

Library (`/`):
- show "In progress" section/badge for in-progress items (no score/tier)
- show DNF items with tier `G`

Tier Board (`/tiers`):
- add an "In progress" lane
- keep S-F lanes
- add a `G (DNF)` lane

#### 5. Routes

- `POST /entry/<id>/checkpoint/<checkpoint>`: upsert checkpoint opinion
- `GET/POST /finish/<id>`: final ratings + mark finished
- `POST /entry/<id>/dnf`: mark DNF

---

### 8.5 Cover Images

- [x] Display image
- [x] Fallback image
- [x] Later: upload support

---

## 9. UI Improvements

- [x] CSS styling
- [x] Cards layout
- [x] Buttons
- [x] Responsive design

---

## 10. Development Philosophy

- Make it work
- Make it clean
- Make it smart

---

## 11.Tier tab

- [x] Route `/tiers`
- [x] Group entries into rows by tier (S-F)
- [x] Render covers only per entry
- [x] Horizontal scroll + responsive layout
- [x] Tier row colors (S-F)


## 11.Tier tab
# 📊 Tier Board (Visual Ranking View)

## Description

Once an entry (book/audiobook) has an assigned **tier**, it will be displayed in a dedicated **Tier Board tab**.

The Tier Board visually organizes entries into tier rows (S–F), similar to a ranking chart.

Each entry is represented **only by its cover image**, making the view clean and visually focused.

---

## Layout Logic

The page is structured into horizontal sections:

```
[S Tier]  → images
[A Tier]  → images
[B Tier]  → images
[C Tier]  → images
[D Tier]  → images
[F Tier]  → images
```

Each row:
- has a **label (S, A, B, …)** on the left
- contains **images of entries** belonging to that tier

---

## Data Logic

Entries are grouped by their `tier` field:

```python
tiers = {
    "S": [],
    "A": [],
    "B": [],
    "C": [],
    "D": [],
    "F": []
}

for entry in entries:
    if entry["tier"] in tiers:
        tiers[entry["tier"]].append(entry)
```

---

## Display Rules

- Only entries with a valid `tier` are shown  
- Each entry displays:
  - `slika_naslovnice` (cover image)

Optional (future):
- hover → show title, author, score

---

## UI Behavior

- Images are displayed in a **horizontal scroll or grid**
- Responsive layout (wrap on smaller screens)
- Tier rows are visually distinct (colors like the reference image)

### Suggested Colors

| Tier | Color |
|------|------|
| S | Red |
| A | Orange |
| B | Yellow |
| C | Light Yellow |
| D | Green |
| F | Gray |

---

## Route

```
/tiers
```

---

## Future Improvements

- Drag & drop to change tier  
- Click image → go to `/entry/<id>`  
- Filter (books / audiobooks)  
- Animate transitions  


## Posible improvments
# Feature Ideas

Cover upload: Add image upload, store thumbnails, validate size/format.
User accounts: Per-user libraries with Flask-Login and optional profiles.
Import/Export: CSV/JSON export + import; OpenLibrary/ISBN lookup.
Bulk edit: Multi-select to change tier/genre/weights in batch.
Recommendations: Simple content-based suggestions from genres/ratings.
Reading progress: Track pages/minutes, "hooked" checkpoints.
# Data & Backend

Weights editor: UI for rating_settings to tune weights live.
Backup & restore: DB dump/restore and scheduled backups.
API: JSON REST endpoints for entries, tiers, stats.
Analytics logging: Track adds/edits for usage metrics.
# UI / UX

Tier board UX: Drag & drop to change tier, click-to-open details, hover tooltips.
Responsive layout: Mobile-first grid and lazy-loading images.
Search UX: Full-text, fuzzy search, multi-facet filters, saved searches.
Accessibility: Keyboard nav, ARIA roles, contrast, image alt text.
# Stats & Visuals

Charts & graphs: Score distribution, time-read, genre breakdown (Chart.js).
Goals & progress: Reading targets, streaks, and leaderboards.
Exportable reports: PDF/CSV summaries for periods or tags.
# Quality & Maintenance

Tests & CI: Unit tests for core logic (calculate_score, calculate_tier), GitHub Actions.
Linting & types: mypy, flake8/black, add type hints.
Docker + deps: Dockerfile, requirements.txt, pinned versions.
Docs: README with setup, contribution guide, and API docs.
# Integrations & Extras

OpenLibrary / Goodreads: Autofill metadata + covers.
Audio player: In-browser playback for audiobooks with position saving.
Notifications: Email or local reminders for goals/reading sessions.
Export to e-reader: Create simple EPUB or reading list exports#


## Used colors
- 171A21
- F18F01
- 7A9B76
- 7284A8
- DC9596
