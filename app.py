import sys
from pathlib import Path
import secrets
import time

# This repo sometimes ends up with an unwritable `__pycache__/` on Windows.
# Avoid writing `.pyc` files so running the app doesn't fail with WinError 5.
sys.dont_write_bytecode = True

import csv
import io
import json
from functools import lru_cache

from flask import Flask, render_template, request, redirect, url_for, abort, Response, flash
from flask import session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from app_version import __version__
import updater
from database import (
    get_all_entries_for_user,
    get_entry_for_user,
    add_entry,
    update_entry,
    delete_entry_for_user,
    init_db,
    get_rating_settings_for_user,
    update_rating_setting,
    CHECKPOINTS,
    upsert_checkpoint,
    mark_dnf,
    mark_in_progress,
    mark_finished,
    get_user_by_username,
    create_user,
    count_users,
    claim_orphaned_data,
    seed_rating_settings_for_user,
)

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.secret_key = "dev"

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "covers"
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUTH_EXEMPT_ENDPOINTS = {"login", "signup", "set_lang", "static"}


def _load_i18n() -> dict:
    path = BASE_DIR / "data.json"
    try:
        mtime = int(path.stat().st_mtime)
    except OSError:
        mtime = -1
    return _load_i18n_cached(mtime)


@lru_cache(maxsize=4)
def _load_i18n_cached(_mtime: int) -> dict:
    path = BASE_DIR / "data.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {"en": {}, "sl": {}}


def _get_lang() -> str:
    lang = (request.cookies.get("bk_lang") or "en").lower()
    return lang if lang in ("en", "sl") else "en"


def tr(key: str) -> str:
    data = _load_i18n()
    lang = _get_lang()
    v = (data.get(lang, {}).get(key)) or (data.get("en", {}).get(key))
    if v:
        return v
    if key.startswith("genre."):
        return key.removeprefix("genre.")
    return key


@app.context_processor
def _inject_static_version():
    # Cache-bust static files so CSS/JS changes show up immediately.
    def mtime(rel_path: str) -> int:
        try:
            return int((BASE_DIR / rel_path).stat().st_mtime)
        except OSError:
            return int(time.time())

    return {
        "static_v_css": mtime("static/style.css"),
        "static_v_js": mtime("static/app.js"),
        "lang": _get_lang(),
        "t": tr,
        "current_path": (request.full_path[:-1] if request.full_path.endswith("?") else request.full_path),
        "current_user": {"id": session.get("user_id"), "username": session.get("username")} if session.get("user_id") else None,
        "app_version": __version__,
    }


@app.get("/update")
def check_update():
    info = updater.get_update_info(timeout_s=2.5)
    return render_template("update.html", info=info)


def _current_user_id() -> int | None:
    uid = session.get("user_id")
    return int(uid) if uid is not None else None


@app.before_request
def _require_login():
    # Require login for all app routes except auth/lang/static.
    if request.endpoint in AUTH_EXEMPT_ENDPOINTS:
        return None
    if request.endpoint is None:
        return None
    if _current_user_id() is None:
        nxt = request.full_path[:-1] if request.full_path.endswith("?") else request.full_path
        return redirect(url_for("login", next=nxt))
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = get_user_by_username(username)
        if not user or not check_password_hash(user.get("password_hash") or "", password):
            flash(tr("flash.login_failed"), "error")
            return redirect(url_for("login", next=request.args.get("next") or ""))

        session.clear()
        session["user_id"] = int(user["id"])
        session["username"] = user["username"]
        seed_rating_settings_for_user(int(user["id"]))

        nxt = (request.args.get("next") or "").strip() or url_for("index")
        return redirect(nxt)

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""

        if not username or len(username) < 3:
            flash(tr("flash.signup_bad_username"), "error")
            return redirect(url_for("signup"))
        if not password or len(password) < 6:
            flash(tr("flash.signup_bad_password"), "error")
            return redirect(url_for("signup"))
        if password != password2:
            flash(tr("flash.signup_pw_mismatch"), "error")
            return redirect(url_for("signup"))
        if get_user_by_username(username):
            flash(tr("flash.signup_exists"), "error")
            return redirect(url_for("signup"))

        uid = create_user(username, generate_password_hash(password))
        if count_users() == 1:
            claim_orphaned_data(uid)
        seed_rating_settings_for_user(uid)

        session.clear()
        session["user_id"] = int(uid)
        session["username"] = username

        flash(tr("flash.signup_success"), "success")
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/lang/<lang_code>")
def set_lang(lang_code: str):
    lang_code = (lang_code or "").lower()
    if lang_code not in ("en", "sl"):
        abort(400)

    nxt = request.args.get("next") or url_for("index")
    resp = redirect(nxt)
    resp.set_cookie("bk_lang", lang_code, max_age=60 * 60 * 24 * 365)
    return resp


@app.after_request
def _no_store(resp):
    # Make dev iterations predictable: don't let the browser cache HTML/CSS/JS.
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


def _is_allowed_image(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_IMAGE_EXTS


def _save_cover_upload(user_id: int, file_storage) -> str | None:
    """
    Save an uploaded cover image under static/covers and return its public URL
    path (e.g. /static/covers/abc.jpg). Returns None when no file was uploaded.
    """
    if file_storage is None or not getattr(file_storage, "filename", ""):
        return None

    filename = secure_filename(file_storage.filename)
    if not filename:
        return None

    if not _is_allowed_image(filename):
        abort(400, description="Unsupported cover image type.")

    user_dir = UPLOAD_DIR / str(int(user_id))
    user_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower()
    token = secrets.token_hex(8)
    out_name = f"{token}{ext}"
    out_path = user_dir / out_name
    file_storage.save(out_path)

    return url_for("static", filename=f"covers/{int(user_id)}/{out_name}")


def _maybe_delete_local_cover(url_path: str | None) -> None:
    # Only delete files we own under /static/covers/.
    if not url_path:
        return
    if not url_path.startswith("/static/covers/"):
        return

    rel = url_path.removeprefix("/static/")
    target = (BASE_DIR / "static" / rel).resolve()
    if UPLOAD_DIR.resolve() not in target.parents:
        return
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass


@app.route("/")
def index():
    entries = get_all_entries_for_user(_current_user_id())

    q = (request.args.get("q") or "").strip().lower()
    tip = (request.args.get("tip") or "").strip()
    zvrst = (request.args.get("zvrst") or "").strip()
    tier = (request.args.get("tier") or "").strip()
    status = (request.args.get("status") or "").strip()
    sort = (request.args.get("sort") or "newest").strip()

    def match(e):
        if q and (q not in (e.get("naslov") or "").lower()) and (q not in (e.get("avtor") or "").lower()):
            return False
        if tip and e.get("tip") != tip:
            return False
        if zvrst and e.get("zvrst") != zvrst:
            return False
        if tier and e.get("tier") != tier:
            return False
        if status and e.get("status") != status:
            return False
        return True

    entries = [e for e in entries if match(e)]

    if sort == "score_desc":
        entries.sort(key=lambda e: float(e.get("skupna_ocena") or 0), reverse=True)
    elif sort == "title_asc":
        entries.sort(key=lambda e: (e.get("naslov") or "").lower())
    else:
        # newest by id
        entries.sort(key=lambda e: int(e.get("id") or 0), reverse=True)

    return render_template("index.html", entries=entries, q=q, tip=tip, zvrst=zvrst, tier=tier, status=status, sort=sort)


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        uid = _current_user_id()
        if uid is None:
            abort(401)
        naslov = (request.form.get("naslov") or "").strip()
        avtor = (request.form.get("avtor") or "").strip()
        tip = (request.form.get("tip") or "book").strip()
        zvrst = (request.form.get("zvrst") or "Drugo").strip()

        # Prefer uploaded file; fallback to URL typed in the text field.
        uploaded_cover = _save_cover_upload(uid, request.files.get("cover_file"))
        slika_naslovnice = uploaded_cover or (request.form.get("slika_naslovnice") or "").strip() or None
        kratko_mnenje = (request.form.get("kratko_mnenje") or "").strip() or tr("default.review")
        fav_quote = (request.form.get("fav_quote") or "").strip() or None
        opombe = (request.form.get("opombe") or "").strip() or None

        def to_int(name):
            v = (request.form.get(name) or "").strip()
            return int(v) if v != "" else None

        st_strani = to_int("st_strani")

        add_entry(
            naslov=naslov,
            avtor=avtor,
            tip=tip,
            zvrst=zvrst,
            slika_naslovnice=slika_naslovnice,
            kratko_mnenje=kratko_mnenje,
            fav_quote=fav_quote,
            opombe=opombe,
            status="in_progress",
            st_strani=st_strani,
            ratings=None,
            user_id=uid,
        )

        flash(tr("flash.entry_added"), "success")
        return redirect(url_for("index"))

    return render_template("add.html")


@app.post("/delete/<int:entry_id>")
def delete(entry_id: int):
    uid = _current_user_id()
    if uid is None:
        abort(401)
    delete_entry_for_user(entry_id=entry_id, user_id=uid)
    flash(tr("flash.entry_deleted"), "success")
    return redirect(url_for("index"))


@app.route("/entry/<int:entry_id>")
def entry_details(entry_id: int):
    uid = _current_user_id()
    if uid is None:
        abort(401)
    entry = get_entry_for_user(entry_id=entry_id, user_id=uid)
    if entry is None:
        abort(404)
    checkpoints = [{"key": k, "label": k} for k in CHECKPOINTS]
    return render_template("details.html", entry=entry, checkpoints=checkpoints)


@app.route("/edit/<int:entry_id>", methods=["GET", "POST"])
def edit(entry_id: int):
    uid = _current_user_id()
    if uid is None:
        abort(401)
    entry = get_entry_for_user(entry_id=entry_id, user_id=uid)
    if entry is None:
        abort(404)

    if request.method == "POST":
        naslov = (request.form.get("naslov") or "").strip()
        avtor = (request.form.get("avtor") or "").strip()
        tip = (request.form.get("tip") or "book").strip()
        zvrst = (request.form.get("zvrst") or "Drugo").strip()

        uploaded_cover = _save_cover_upload(uid, request.files.get("cover_file"))
        slika_naslovnice = uploaded_cover or (request.form.get("slika_naslovnice") or "").strip() or None
        kratko_mnenje = (request.form.get("kratko_mnenje") or "").strip() or tr("default.review")
        fav_quote = (request.form.get("fav_quote") or "").strip() or None
        opombe = (request.form.get("opombe") or "").strip() or None

        def to_int(name):
            v = (request.form.get(name) or "").strip()
            return int(v) if v != "" else None

        st_strani = to_int("st_strani")

        update_entry(
            entry_id=entry_id,
            naslov=naslov,
            avtor=avtor,
            tip=tip,
            zvrst=zvrst,
            slika_naslovnice=slika_naslovnice,
            kratko_mnenje=kratko_mnenje,
            fav_quote=fav_quote,
            opombe=opombe,
            st_strani=st_strani,
            ratings=None,
            user_id=uid,
        )

        if uploaded_cover:
            # If a new local file was uploaded, remove the old local cover file (if any).
            _maybe_delete_local_cover(entry.get("slika_naslovnice"))

        flash(tr("flash.entry_saved"), "success")
        return redirect(url_for("entry_details", entry_id=entry_id))

    return render_template("edit.html", entry=entry)


@app.post("/entry/<int:entry_id>/checkpoint/<checkpoint>")
def save_checkpoint(entry_id: int, checkpoint: str):
    uid = _current_user_id()
    if uid is None:
        abort(401)
    entry = get_entry_for_user(entry_id=entry_id, user_id=uid)
    if entry is None:
        abort(404)

    opinion = (request.form.get("opinion") or "").strip() or None
    try:
        upsert_checkpoint(entry_id, checkpoint, opinion, user_id=uid)
    except ValueError:
        abort(400)

    flash(tr("flash.checkpoint_saved"), "success")
    return redirect(url_for("entry_details", entry_id=entry_id))


@app.post("/entry/<int:entry_id>/dnf")
def set_dnf(entry_id: int):
    uid = _current_user_id()
    if uid is None:
        abort(401)
    entry = get_entry_for_user(entry_id=entry_id, user_id=uid)
    if entry is None:
        abort(404)
    mark_dnf(entry_id, user_id=uid)
    flash(tr("flash.marked_dnf"), "success")
    return redirect(url_for("entry_details", entry_id=entry_id))


@app.post("/entry/<int:entry_id>/in_progress")
def set_in_progress(entry_id: int):
    uid = _current_user_id()
    if uid is None:
        abort(401)
    entry = get_entry_for_user(entry_id=entry_id, user_id=uid)
    if entry is None:
        abort(404)
    mark_in_progress(entry_id, user_id=uid)
    flash(tr("flash.marked_in_progress"), "success")
    return redirect(url_for("entry_details", entry_id=entry_id))


@app.route("/finish/<int:entry_id>", methods=["GET", "POST"])
def finish(entry_id: int):
    uid = _current_user_id()
    if uid is None:
        abort(401)
    entry = get_entry_for_user(entry_id=entry_id, user_id=uid)
    if entry is None:
        abort(404)

    if request.method == "POST":
        ratings = {}
        for key in request.form:
            if not key.startswith("rating_"):
                continue
            kriterij = key.removeprefix("rating_")
            raw = (request.form.get(key) or "").strip()
            if raw == "":
                continue
            ratings[kriterij] = float(raw)

        if not ratings:
            flash(tr("flash.finish_need_rating"), "error")
            return redirect(url_for("finish", entry_id=entry_id))

        mark_finished(entry_id, entry.get("tip") or "book", ratings, user_id=uid)
        flash(tr("flash.entry_finished"), "success")
        return redirect(url_for("entry_details", entry_id=entry_id))

    return render_template("finish.html", entry=entry)


@app.route("/stats")
def stats():
    entries = get_all_entries_for_user(_current_user_id())

    # Stats are for finished items only (exclude in-progress and DNF).
    finished = [e for e in entries if e.get("status") == "finished"]

    total = len(finished)
    total_books = sum(1 for e in finished if e.get("tip") == "book")
    total_audiobooks = sum(1 for e in finished if e.get("tip") == "audiobook")
    avg_score = round(sum(float(e.get("skupna_ocena") or 0) for e in finished) / total, 2) if total else 0

    # Genre counts
    genre_counts = {}
    for e in finished:
        g = e.get("zvrst") or "Drugo"
        genre_counts[g] = genre_counts.get(g, 0) + 1
    favorite_genre = max(genre_counts.items(), key=lambda kv: kv[1])[0] if genre_counts else None

    # Page totals (requires entry_lengths)
    # We'll compute via per-entry load to avoid duplicating SQL right now.
    total_pages = 0
    for e in finished:
        full = get_entry_for_user(entry_id=int(e["id"]), user_id=_current_user_id())
        if not full:
            continue
        st = full["lengths"].get("st_strani")
        if isinstance(st, int):
            total_pages += st

    return render_template(
        "stats.html",
        total=total,
        total_books=total_books,
        total_audiobooks=total_audiobooks,
        avg_score=avg_score,
        favorite_genre=favorite_genre,
        total_pages=total_pages,
    )


@app.route("/tiers")
def tiers():
    entries = get_all_entries_for_user(_current_user_id())
    grouped = {k: [] for k in ["IN_PROGRESS", "S", "A", "B", "C", "D", "F", "G"]}

    for e in entries:
        st = e.get("status")
        if st == "in_progress":
            grouped["IN_PROGRESS"].append(e)
            continue
        t = e.get("tier")
        if t in grouped:
            grouped[t].append(e)

    # Stable ordering: best tier first, then newest within tier.
    for t in grouped:
        grouped[t].sort(key=lambda e: int(e.get("id") or 0), reverse=True)

    return render_template("tiers.html", tiers=grouped)


@app.route("/weights", methods=["GET", "POST"])
def weights():
    if request.method == "POST":
        # Update settings in bulk from the posted form.
        settings = get_rating_settings_for_user(_current_user_id())
        for s in settings:
            sid = int(s["id"])
            raw_w = (request.form.get(f"w_{sid}") or "").strip()
            raw_a = request.form.get(f"a_{sid}")  # checkbox: present if checked
            if raw_w == "":
                continue
            try:
                w = float(raw_w)
            except ValueError:
                continue
            active = raw_a == "on"
            update_rating_setting(sid, w, active, user_id=_current_user_id())
        flash(tr("flash.weights_saved"), "success")
        return redirect(url_for("weights"))

    settings = get_rating_settings_for_user(_current_user_id())
    return render_template("weights.html", settings=settings)


@app.get("/export.json")
def export_json():
    entries = get_all_entries_for_user(_current_user_id())
    full = []
    for e in entries:
        fe = get_entry_for_user(entry_id=int(e["id"]), user_id=_current_user_id())
        if fe:
            full.append(fe)
    payload = {"entries": full}
    return Response(json.dumps(payload, ensure_ascii=False, indent=2), mimetype="application/json")


@app.get("/export.csv")
def export_csv():
    entries = get_all_entries_for_user(_current_user_id())
    out = io.StringIO()
    w = csv.writer(out)

    # Flatten ratings into a JSON-ish string column for now.
    w.writerow(
        [
            "id",
            "naslov",
            "avtor",
            "tip",
            "zvrst",
            "slika_naslovnice",
            "kratko_mnenje",
            "fav_quote",
            "opombe",
            "st_strani",
            "skupna_ocena",
            "tier",
            "ratings_json",
        ]
    )

    for e in entries:
        fe = get_entry_for_user(entry_id=int(e["id"]), user_id=_current_user_id())
        if not fe:
            continue
        w.writerow(
            [
                fe.get("id"),
                fe.get("naslov"),
                fe.get("avtor"),
                fe.get("tip"),
                fe.get("zvrst"),
                fe.get("slika_naslovnice"),
                fe.get("kratko_mnenje"),
                fe.get("fav_quote"),
                fe.get("opombe"),
                (fe.get("lengths") or {}).get("st_strani"),
                fe.get("skupna_ocena"),
                fe.get("tier"),
                json.dumps(fe.get("ratings") or {}, ensure_ascii=False),
            ]
        )

    csv_bytes = out.getvalue().encode("utf-8")
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=book-keep-export.csv"},
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
