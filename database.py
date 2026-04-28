from pathlib import Path
import sqlite3
from typing import Dict, Optional, Any
import sys
import os
from datetime import datetime, timezone

# Prevent `.pyc` writes (see note in app.py).
sys.dont_write_bytecode = True

BASE_DIR = Path(__file__).resolve().parent

# The repo-local `data/` folder can have ACLs that allow writes but block deletes/renames,
# which breaks SQLite journaling on Windows ("disk I/O error"). Store the DB in a
# known-writable location for this environment.
USERPROFILE = os.environ.get("USERPROFILE")
DEFAULT_WRITABLE = Path(USERPROFILE) / ".codex" / "memories" / "Book-Keep" if USERPROFILE else (BASE_DIR / "data")
DB_DIR = DEFAULT_WRITABLE
DB_PATH = DB_DIR / "books.db"

# Legacy repo DB locations (used only for one-time copy/import).
LEGACY_DB_PATHS = [
    BASE_DIR / "data" / "books_local.db",
    BASE_DIR / "data" / "books.db",
]

BOOK_KRITERIJI = ["zgodba", "liki", "tempo", "slog", "custveni_vpliv"]
AUDIOBOOK_KRITERIJI = ["zgodba", "liki", "tempo", "naracija", "jasnost_govora", "zvocna_izkusnja"]

CHECKPOINTS = ["pages_5", "first_chapter", "pct_25", "pct_50", "pct_80", "end", "never"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def calculate_score(ratings: Dict[str, float], weights: Dict[str, float]) -> float:
    # Weighted average over only criteria that have both rating and a positive weight.
    total_w = 0.0
    total = 0.0
    for kriterij, ocena in ratings.items():
        w = float(weights.get(kriterij, 0.0))
        if w <= 0:
            continue
        total += float(ocena) * w
        total_w += w
    if total_w <= 0:
        return 0.0
    return round(total / total_w, 2)


def calculate_tier(score: float) -> str:
    # Keep tiers stable and simple; clamp to the expected range.
    s = float(score)
    if s >= 9:
        return "S"
    if s >= 8:
        return "A"
    if s >= 7:
        return "B"
    if s >= 6:
        return "C"
    if s >= 5:
        return "D"
    return "F"


def delete_entry(entry_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def get_all_entries():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM entries")
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_entry(entry_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
    entry_row = cursor.fetchone()
    if entry_row is None:
        conn.close()
        return None

    cursor.execute("SELECT st_strani FROM entry_lengths WHERE entry_id = ?", (entry_id,))
    length_row = cursor.fetchone()

    cursor.execute("SELECT kriterij, ocena FROM entry_ratings WHERE entry_id = ?", (entry_id,))
    ratings_rows = cursor.fetchall()

    cursor.execute(
        "SELECT checkpoint, opinion, created_at, updated_at FROM entry_checkpoints WHERE entry_id = ?",
        (entry_id,),
    )
    checkpoint_rows = cursor.fetchall()

    conn.close()

    entry = dict(entry_row)
    entry["lengths"] = dict(length_row) if length_row is not None else {"st_strani": None}
    entry["ratings"] = {r["kriterij"]: r["ocena"] for r in ratings_rows}
    entry["checkpoints"] = {r["checkpoint"]: {"opinion": r["opinion"], "created_at": r["created_at"], "updated_at": r["updated_at"]} for r in checkpoint_rows}
    return entry


def get_rating_weights(tip: str) -> Dict[str, float]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT kriterij, utez FROM rating_settings WHERE tip = ? AND je_aktiven = 1",
        (tip,),
    )
    rows = cursor.fetchall()
    conn.close()

    weights = {r["kriterij"]: float(r["utez"]) for r in rows}
    if weights:
        return weights

    # Fallback to equal weights if table isn't seeded yet.
    kriteriji = BOOK_KRITERIJI if tip == "book" else AUDIOBOOK_KRITERIJI
    return {k: 1.0 for k in kriteriji}


def get_rating_settings() -> list[dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, tip, kriterij, utez, je_aktiven FROM rating_settings ORDER BY tip, id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_rating_setting(setting_id: int, utez: float, je_aktiven: bool) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE rating_settings SET utez = ?, je_aktiven = ? WHERE id = ?",
        (float(utez), 1 if je_aktiven else 0, int(setting_id)),
    )
    conn.commit()
    conn.close()


def add_entry(
    naslov: str,
    avtor: str,
    tip: str,
    zvrst: str,
    slika_naslovnice: Optional[str],
    kratko_mnenje: str,
    fav_quote: Optional[str],
    opombe: Optional[str],
    status: str = "in_progress",
    started_at: Optional[str] = None,
    skupna_ocena: Optional[float] = None,
    tier: Optional[str] = None,
    st_strani: Optional[int] = None,
    ratings: Optional[Dict[str, float]] = None,
) -> int:

    if ratings is None:
        ratings = {}

    if started_at is None:
        started_at = _now_iso()

    if status == "finished":
        if skupna_ocena is None:
            weights = get_rating_weights(tip)
            skupna_ocena = calculate_score(ratings, weights)
        if tier is None:
            tier = calculate_tier(float(skupna_ocena or 0))
    elif status == "dnf":
        skupna_ocena = None
        tier = "G"
    else:
        # in_progress
        skupna_ocena = None
        tier = None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO entries 
        (naslov, avtor, tip, zvrst, slika_naslovnice, kratko_mnenje, fav_quote, opombe,
         status, started_at, finished_at, dnf_at, skupna_ocena, tier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        naslov, avtor, tip, zvrst, slika_naslovnice,
        kratko_mnenje, fav_quote, opombe,
        status,
        started_at,
        _now_iso() if status == "finished" else None,
        _now_iso() if status == "dnf" else None,
        skupna_ocena,
        tier,
    ))

    entry_id = cursor.lastrowid

    cursor.execute("SELECT id FROM entry_lengths WHERE entry_id = ?", (entry_id,))
    existing_len = cursor.fetchone()
    if existing_len is None:
        cursor.execute("""
            INSERT INTO entry_lengths 
            (entry_id, st_strani)
            VALUES (?, ?)
        """, (
            entry_id, st_strani
        ))

    if status == "finished":
        for kriterij, ocena in ratings.items():
            cursor.execute(
                "INSERT INTO entry_ratings (entry_id, kriterij, ocena) VALUES (?, ?, ?)",
                (entry_id, kriterij, ocena),
            )

    conn.commit()
    conn.close()
    return int(entry_id)


def update_entry(
    entry_id: int,
    naslov: str,
    avtor: str,
    tip: str,
    zvrst: str,
    slika_naslovnice: Optional[str],
    kratko_mnenje: str,
    fav_quote: Optional[str],
    opombe: Optional[str],
    st_strani: Optional[int] = None,
    ratings: Optional[Dict[str, float]] = None,
) -> None:
    if ratings is None:
        ratings = {}

    existing = get_entry(entry_id)
    status = (existing or {}).get("status") or "in_progress"
    skupna_ocena = (existing or {}).get("skupna_ocena")
    tier = (existing or {}).get("tier")

    if status == "finished":
        weights = get_rating_weights(tip)
        skupna_ocena = calculate_score(ratings, weights)
        tier = calculate_tier(skupna_ocena)
    elif status == "dnf":
        skupna_ocena = None
        tier = "G"
    else:
        skupna_ocena = None
        tier = None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE entries
        SET naslov = ?, avtor = ?, tip = ?, zvrst = ?, slika_naslovnice = ?,
            kratko_mnenje = ?, fav_quote = ?, opombe = ?, skupna_ocena = ?, tier = ?
        WHERE id = ?
        """,
        (
            naslov,
            avtor,
            tip,
            zvrst,
            slika_naslovnice,
            kratko_mnenje,
            fav_quote,
            opombe,
            skupna_ocena,
            tier,
            entry_id,
        ),
    )

    cursor.execute("SELECT id FROM entry_lengths WHERE entry_id = ?", (entry_id,))
    length_id = cursor.fetchone()
    if length_id is None:
        cursor.execute(
            "INSERT INTO entry_lengths (entry_id, st_strani) VALUES (?, ?)",
            (entry_id, st_strani),
        )
    else:
        cursor.execute(
            "UPDATE entry_lengths SET st_strani = ? WHERE entry_id = ?",
            (st_strani, entry_id),
        )

    cursor.execute("DELETE FROM entry_ratings WHERE entry_id = ?", (entry_id,))
    if status == "finished":
        for kriterij, ocena in ratings.items():
            cursor.execute(
                "INSERT INTO entry_ratings (entry_id, kriterij, ocena) VALUES (?, ?, ?)",
                (entry_id, kriterij, ocena),
            )

    conn.commit()
    conn.close()


def upsert_checkpoint(entry_id: int, checkpoint: str, opinion: str | None) -> None:
    if checkpoint not in CHECKPOINTS:
        raise ValueError("Invalid checkpoint")

    now = _now_iso()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO entry_checkpoints (entry_id, checkpoint, opinion, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(entry_id, checkpoint) DO UPDATE SET
            opinion = excluded.opinion,
            updated_at = excluded.updated_at
        """,
        (int(entry_id), checkpoint, opinion, now, now),
    )
    conn.commit()
    conn.close()


def mark_dnf(entry_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE entries SET status='dnf', dnf_at=?, finished_at=NULL, skupna_ocena=NULL, tier='G' WHERE id=?", (_now_iso(), int(entry_id)))
    cur.execute("DELETE FROM entry_ratings WHERE entry_id = ?", (int(entry_id),))
    conn.commit()
    conn.close()


def mark_in_progress(entry_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE entries SET status='in_progress', finished_at=NULL, dnf_at=NULL, skupna_ocena=NULL, tier=NULL WHERE id=?", (int(entry_id),))
    cur.execute("DELETE FROM entry_ratings WHERE entry_id = ?", (int(entry_id),))
    conn.commit()
    conn.close()


def mark_finished(entry_id: int, tip: str, ratings: Dict[str, float]) -> None:
    weights = get_rating_weights(tip)
    score = calculate_score(ratings, weights)
    tier = calculate_tier(score)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE entries SET status='finished', finished_at=?, dnf_at=NULL, skupna_ocena=?, tier=? WHERE id=?",
        (_now_iso(), float(score), tier, int(entry_id)),
    )
    cur.execute("DELETE FROM entry_ratings WHERE entry_id = ?", (int(entry_id),))
    for k, v in ratings.items():
        cur.execute("INSERT INTO entry_ratings (entry_id, kriterij, ocena) VALUES (?, ?, ?)", (int(entry_id), k, float(v)))
    conn.commit()
    conn.close()

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    # If we don't have a working DB yet, try to seed it from the newest backup.
    # This avoids being blocked by a legacy `books.db-journal` that Windows refuses to delete.
    data_dir = DB_PATH.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        # Prefer repo backups, then any legacy DB files.
        repo_data_dir = BASE_DIR / "data"
        backups = []
        try:
            backups = sorted(repo_data_dir.glob("books.db.bak-*"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            backups = []

        seed_candidates = backups + [p for p in LEGACY_DB_PATHS if p.exists()]
        if seed_candidates:
            for src in seed_candidates:
                try:
                    DB_PATH.write_bytes(Path(src).read_bytes())
                    break
                except OSError:
                    continue

    conn = get_connection()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    

    cursor.executescript('''CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    naslov TEXT NOT NULL,
    avtor TEXT NOT NULL,
    tip TEXT NOT NULL CHECK(tip IN ('book', 'audiobook')),
    zvrst TEXT NOT NULL CHECK(zvrst IN (
        'Fantazija',
        'Znanstvena fantastika',
        'Romanca',
        'Kriminalka',
        'Triler',
        'Grozljivka',
        'Avantura',
        'Zgodovinski roman',
        'Mladinski roman',
        'Realisticni roman',
        'Self-Help',
        'Drugo'
    )),
    slika_naslovnice TEXT,
    kratko_mnenje TEXT NOT NULL,
    fav_quote TEXT,
    opombe TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK(status IN ('in_progress','finished','dnf')),
    started_at TEXT,
    finished_at TEXT,
    dnf_at TEXT,
    skupna_ocena REAL,
    tier TEXT CHECK(tier IN ('S', 'A', 'B', 'C', 'D', 'F', 'G'))
);

CREATE TABLE IF NOT EXISTS entry_lengths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    st_strani INTEGER,
    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entry_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    kriterij TEXT NOT NULL CHECK(kriterij IN (
        'zgodba',
        'liki',
        'tempo',
        'slog',
        'custveni_vpliv',
        'naracija',
        'jasnost_govora',
        'zvocna_izkusnja'
    )),
    ocena REAL NOT NULL CHECK(ocena >= 1 AND ocena <= 10),
    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rating_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tip TEXT NOT NULL CHECK(tip IN ('book', 'audiobook')),
    kriterij TEXT NOT NULL CHECK(kriterij IN (
        'zgodba',
        'liki',
        'tempo',
        'slog',
        'custveni_vpliv',
        'naracija',
        'jasnost_govora',
        'zvocna_izkusnja'
    )),
    utez REAL NOT NULL CHECK(utez > 0),
    je_aktiven INTEGER NOT NULL CHECK(je_aktiven IN (0, 1)) );

CREATE TABLE IF NOT EXISTS entry_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    checkpoint TEXT NOT NULL CHECK(checkpoint IN (
        'pages_5','first_chapter','pct_25','pct_50','pct_80','end','never'
    )),
    opinion TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(entry_id, checkpoint),
    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
);
                      ''')

    # Seed default weights (equal weights) once.
    cursor.execute("SELECT COUNT(1) FROM rating_settings")
    (count,) = cursor.fetchone()
    if int(count) == 0:
        for k in BOOK_KRITERIJI:
            cursor.execute(
                "INSERT INTO rating_settings (tip, kriterij, utez, je_aktiven) VALUES ('book', ?, ?, 1)",
                (k, 1.0),
            )
        for k in AUDIOBOOK_KRITERIJI:
            cursor.execute(
                "INSERT INTO rating_settings (tip, kriterij, utez, je_aktiven) VALUES ('audiobook', ?, ?, 1)",
                (k, 1.0),
            )

    conn.commit()

    # Migrate legacy `entries` schema (skupna_ocena/tier NOT NULL) to new lifecycle-based schema.
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'")
    row = cursor.fetchone()
    legacy_sql = (row[0] if row else "") or ""
    if "skupna_ocena REAL NOT NULL" in legacy_sql or "tier TEXT NOT NULL" in legacy_sql or "status TEXT" not in legacy_sql:
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.executescript("""
        ALTER TABLE entries RENAME TO entries_old;

        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naslov TEXT NOT NULL,
            avtor TEXT NOT NULL,
            tip TEXT NOT NULL CHECK(tip IN ('book', 'audiobook')),
            zvrst TEXT NOT NULL CHECK(zvrst IN (
                'Fantazija','Znanstvena fantastika','Romanca','Kriminalka','Triler','Grozljivka',
                'Avantura','Zgodovinski roman','Mladinski roman','Realisticni roman','Self-Help','Drugo'
            )),
            slika_naslovnice TEXT,
            kratko_mnenje TEXT NOT NULL,
            fav_quote TEXT,
            opombe TEXT,
            status TEXT NOT NULL DEFAULT 'in_progress' CHECK(status IN ('in_progress','finished','dnf')),
            started_at TEXT,
            finished_at TEXT,
            dnf_at TEXT,
            skupna_ocena REAL,
            tier TEXT CHECK(tier IN ('S','A','B','C','D','F','G'))
        );

        INSERT INTO entries (
            id,naslov,avtor,tip,zvrst,slika_naslovnice,kratko_mnenje,fav_quote,opombe,
            status,started_at,finished_at,dnf_at,skupna_ocena,tier
        )
        SELECT
            id,naslov,avtor,tip,zvrst,slika_naslovnice,kratko_mnenje,fav_quote,opombe,
            'finished', NULL, NULL, NULL, skupna_ocena, tier
        FROM entries_old;

        DROP TABLE entries_old;
        """)
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    # Migrate entry_lengths to drop `trajanje_minut` (duration) if it exists.
    cursor.execute("PRAGMA table_info(entry_lengths)")
    cols = [r[1] for r in cursor.fetchall()]
    if "trajanje_minut" in cols:
        # Some dev DBs can contain orphaned rows; copy only valid ones.
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.executescript("""
        DROP TABLE IF EXISTS entry_lengths_new;
        CREATE TABLE entry_lengths_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            st_strani INTEGER,
            FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
        );

        INSERT INTO entry_lengths_new (id, entry_id, st_strani)
        SELECT el.id, el.entry_id, el.st_strani
        FROM entry_lengths el
        JOIN entries e ON e.id = el.entry_id;

        DROP TABLE entry_lengths;
        ALTER TABLE entry_lengths_new RENAME TO entry_lengths;
        """)
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    conn.close()
