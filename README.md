# Book-Keep

Personal web app for tracking **books** and **audiobooks** with a visual-first library, Tier Board, and a reading workflow that supports **in-progress checkpoints** and **DNF**.

## Tech

- Python 3
- Flask (server + routing)
- SQLite (storage)
- Jinja2 templates
- HTML/CSS/JS (no frontend framework)

## Run

```powershell
python app.py
```

Then open:

- `http://127.0.0.1:5000/`

## Language (EN/SL)

All UI strings live in [data.json](data.json) under `en` and `sl`.

- Use the **EN/SL** toggle in the top navigation to switch language.
- The app stores the selected language in a cookie: `bk_lang` (`en` or `sl`).
- Switch links are served by: `GET /lang/<lang_code>?next=<path>`

Note: user-entered content (title, notes, reviews, etc.) is never translated.

## How To Use

### 1) Add A New Entry

Go to **Add** (`/add`) and create an entry when you start reading/listening.

- New entries start as `in_progress` by default.
- You can upload a local cover image (saved under `static/covers/`) or paste a cover URL.

### 2) Track Reading With Checkpoints ("Hooked")

Open an entry (`/entry/<id>`) and fill your opinions at checkpoints:

- `pages_5`, `first_chapter`, `pct_25`, `pct_50`, `pct_80`, `end`, `never`

These are saved per checkpoint and can be updated anytime.

### 3) Finish And Rate (Tier Is Computed)

When you complete the book/audiobook, click **Finish** (`/finish/<id>`) and enter final ratings.

- Score is computed from your ratings + weights in `rating_settings`.
- Tier is computed from the score (S-F).

### 4) DNF ("Couldn't Finish On God")

If you drop a book, mark it **DNF** on the entry page.

- DNF uses tier `G`.
- It is excluded from statistics.

## Main Pages / Routes

- `/` Library (visual cards, filters)
- `/entry/<id>` Entry details + checkpoints + status actions
- `/finish/<id>` Final rating form (only when finishing)
- `/tiers` Tier Board (In progress + S-F + G)
- `/stats` Statistics (finished items only)
- `/weights` Weights editor for scoring (rating_settings)
- `/export.json` Full export (includes ratings + checkpoints)
- `/export.csv` CSV export (ratings packed as JSON in a column)

## Notes

- The SQLite DB path is configured in `database.py` and (in this environment) is stored under:
  `C:\Users\Stefan\.codex\memories\Book-Keep\books.db`
