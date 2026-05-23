import os
import json
import random
import secrets
import sqlite3
from datetime import datetime

from flask import (
    Flask, redirect, url_for, session, render_template,
    request, flash, g, jsonify
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

DATABASE = os.environ.get("DATABASE_PATH", "sorteo.db")

# --------------- Database helpers ---------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT,
        picture TEXT
    );
    CREATE TABLE IF NOT EXISTS sorteos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        owner_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        executed_at TEXT,
        winner TEXT,
        FOREIGN KEY (owner_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sorteo_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        name TEXT,
        UNIQUE(sorteo_id, email),
        FOREIGN KEY (sorteo_id) REFERENCES sorteos(id) ON DELETE CASCADE
    );
    """)
    db.commit()
    db.close()


# --------------- Flask-Login ---------------

login_manager = LoginManager(app)
login_manager.login_view = "login_page"


class User(UserMixin):
    def __init__(self, id_, email, name, picture):
        self.id = id_
        self.email = email
        self.name = name
        self.picture = picture


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return User(row["id"], row["email"], row["name"], row["picture"])
    return None


# --------------- Google OAuth ---------------

oauth = OAuth(app)

google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")

if google_client_id and google_client_secret:
    google = oauth.register(
        name="google",
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
else:
    google = None


# --------------- Routes ---------------

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html", google_enabled=google is not None)


@app.route("/login/google")
def login_google():
    if google is None:
        flash("Google OAuth no está configurado. Configura GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET.", "error")
        return redirect(url_for("login_page"))
    redirect_uri = url_for("authorize_google", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/authorize/google")
def authorize_google():
    if google is None:
        flash("Google OAuth no está configurado.", "error")
        return redirect(url_for("login_page"))

    token = google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info:
        user_info = google.get("https://openidconnect.googleapis.com/v1/userinfo").json()

    google_id = user_info["sub"]
    email = user_info["email"]
    name = user_info.get("name", email)
    picture = user_info.get("picture", "")

    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO users (id, email, name, picture) VALUES (?, ?, ?, ?)",
        (google_id, email, name, picture),
    )
    db.commit()

    user = User(google_id, email, name, picture)
    login_user(user)
    flash(f"¡Bienvenido, {name}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("index"))


# --------------- Dashboard ---------------

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    sorteos = db.execute(
        "SELECT * FROM sorteos WHERE owner_id = ? ORDER BY created_at DESC",
        (current_user.id,),
    ).fetchall()
    return render_template("dashboard.html", sorteos=sorteos)


# --------------- CRUD Sorteos ---------------

@app.route("/sorteo/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_sorteo():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title:
            flash("El título es obligatorio.", "error")
            return render_template("nuevo_sorteo.html")

        db = get_db()
        db.execute(
            "INSERT INTO sorteos (title, description, owner_id, created_at) VALUES (?, ?, ?, ?)",
            (title, description, current_user.id, datetime.utcnow().isoformat()),
        )
        db.commit()
        flash("Sorteo creado exitosamente.", "success")
        return redirect(url_for("dashboard"))
    return render_template("nuevo_sorteo.html")


@app.route("/sorteo/<int:sorteo_id>")
@login_required
def ver_sorteo(sorteo_id):
    db = get_db()
    sorteo = db.execute(
        "SELECT * FROM sorteos WHERE id = ? AND owner_id = ?",
        (sorteo_id, current_user.id),
    ).fetchone()
    if not sorteo:
        flash("Sorteo no encontrado.", "error")
        return redirect(url_for("dashboard"))

    participants = db.execute(
        "SELECT * FROM participants WHERE sorteo_id = ?", (sorteo_id,)
    ).fetchall()
    return render_template("ver_sorteo.html", sorteo=sorteo, participants=participants)


@app.route("/sorteo/<int:sorteo_id>/participante", methods=["POST"])
@login_required
def agregar_participante(sorteo_id):
    db = get_db()
    sorteo = db.execute(
        "SELECT * FROM sorteos WHERE id = ? AND owner_id = ?",
        (sorteo_id, current_user.id),
    ).fetchone()
    if not sorteo:
        flash("Sorteo no encontrado.", "error")
        return redirect(url_for("dashboard"))

    if sorteo["winner"]:
        flash("Este sorteo ya fue ejecutado.", "error")
        return redirect(url_for("ver_sorteo", sorteo_id=sorteo_id))

    email = request.form.get("email", "").strip()
    name = request.form.get("name", "").strip()
    if not email:
        flash("El correo es obligatorio.", "error")
        return redirect(url_for("ver_sorteo", sorteo_id=sorteo_id))

    try:
        db.execute(
            "INSERT INTO participants (sorteo_id, email, name) VALUES (?, ?, ?)",
            (sorteo_id, email, name or email),
        )
        db.commit()
        flash(f"Participante {email} agregado.", "success")
    except sqlite3.IntegrityError:
        flash("Ese correo ya está registrado en este sorteo.", "error")

    return redirect(url_for("ver_sorteo", sorteo_id=sorteo_id))


@app.route("/sorteo/<int:sorteo_id>/participante/<int:part_id>/eliminar", methods=["POST"])
@login_required
def eliminar_participante(sorteo_id, part_id):
    db = get_db()
    sorteo = db.execute(
        "SELECT * FROM sorteos WHERE id = ? AND owner_id = ?",
        (sorteo_id, current_user.id),
    ).fetchone()
    if not sorteo or sorteo["winner"]:
        flash("No se puede modificar este sorteo.", "error")
        return redirect(url_for("dashboard"))

    db.execute("DELETE FROM participants WHERE id = ? AND sorteo_id = ?", (part_id, sorteo_id))
    db.commit()
    flash("Participante eliminado.", "success")
    return redirect(url_for("ver_sorteo", sorteo_id=sorteo_id))


@app.route("/sorteo/<int:sorteo_id>/ejecutar", methods=["POST"])
@login_required
def ejecutar_sorteo(sorteo_id):
    db = get_db()
    sorteo = db.execute(
        "SELECT * FROM sorteos WHERE id = ? AND owner_id = ?",
        (sorteo_id, current_user.id),
    ).fetchone()
    if not sorteo:
        flash("Sorteo no encontrado.", "error")
        return redirect(url_for("dashboard"))

    if sorteo["winner"]:
        flash("Este sorteo ya fue ejecutado.", "error")
        return redirect(url_for("ver_sorteo", sorteo_id=sorteo_id))

    participants = db.execute(
        "SELECT * FROM participants WHERE sorteo_id = ?", (sorteo_id,)
    ).fetchall()

    if len(participants) < 2:
        flash("Se necesitan al menos 2 participantes para ejecutar el sorteo.", "error")
        return redirect(url_for("ver_sorteo", sorteo_id=sorteo_id))

    winner = random.choice(participants)
    winner_text = f"{winner['name']} ({winner['email']})"

    db.execute(
        "UPDATE sorteos SET winner = ?, executed_at = ? WHERE id = ?",
        (winner_text, datetime.utcnow().isoformat(), sorteo_id),
    )
    db.commit()
    flash(f"🎉 ¡El ganador es: {winner_text}!", "success")
    return redirect(url_for("ver_sorteo", sorteo_id=sorteo_id))


@app.route("/sorteo/<int:sorteo_id>/eliminar", methods=["POST"])
@login_required
def eliminar_sorteo(sorteo_id):
    db = get_db()
    sorteo = db.execute(
        "SELECT * FROM sorteos WHERE id = ? AND owner_id = ?",
        (sorteo_id, current_user.id),
    ).fetchone()
    if not sorteo:
        flash("Sorteo no encontrado.", "error")
        return redirect(url_for("dashboard"))

    db.execute("DELETE FROM participants WHERE sorteo_id = ?", (sorteo_id,))
    db.execute("DELETE FROM sorteos WHERE id = ?", (sorteo_id,))
    db.commit()
    flash("Sorteo eliminado.", "success")
    return redirect(url_for("dashboard"))


# --------------- Init ---------------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
