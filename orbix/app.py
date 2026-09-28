from flask import Flask, render_template, jsonify, request, session, redirect, url_for, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random
import os
import re
import psycopg2
import json
import bcrypt
import uuid
from urllib.parse import quote
from urllib.request import Request, urlopen
import sqlite3
from calendar import monthrange

try:
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VideoGrant
except ImportError:
    AccessToken = None
    VideoGrant = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "Twilio.env"))

FLASK_SECRET_KEY = "839079e1f27d7fe27bdbaff0bab7f4ee7a56492500b74ea05ed85a6858a275b8"
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/orbix"
GOOGLE_MAPS_API_KEY = "your_google_maps_api_key_here"
MEDICAL_API_KEY = "ds_pk_16d9e77342994592fa5832839246dab52a356c696310bea224eae0cc98dccb27"
GEOAPIFY_API_KEY = "21c9896e84844ff2b9325d588cee1ac7"
OSM_USER_AGENT = "OrbixHealth/1.0"
NOMINATIM_EMAIL = "ommsai982007@gmail.com"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
TWILIO_API_KEY_SID = os.getenv("TWILIO_API_KEY_SID", "").strip()
TWILIO_API_KEY_SECRET = os.getenv("TWILIO_API_KEY_SECRET", "").strip()
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000").strip().rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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").strip()

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = FLASK_SECRET_KEY
app.config["JSON_SORT_KEYS"] = False
CORS(app)

@app.get("/health")
def health_check():
    return jsonify({
        "status": "ok",
        "service": "Orbix Health",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    })

# ── Database Setup ──
USERS_FILE = os.path.join(BASE_DIR, "users.json")
CONVERSATIONS_FILE = os.path.join(BASE_DIR, "conversations.json")
FAMILY_DATA_FILE = os.path.join(BASE_DIR, "family_data.json")
CALL_RECORDS_DB = os.path.join(BASE_DIR, "call_records.db")


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured. Add it to your .env file.")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def read_json_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError, OSError):
        return {}


def write_json_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users or {}, f, ensure_ascii=False, indent=2)


def read_json_conversations():
    if not os.path.exists(CONVERSATIONS_FILE):
        return {}
    try:
        with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError, OSError):
        return {}


def write_json_conversations(data):
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data or {}, f, ensure_ascii=False, indent=2)


def ensure_call_records_table():
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tollfree_calls (
                        id TEXT PRIMARY KEY,
                        caller_number TEXT,
                        language TEXT,
                        problem TEXT,
                        mode TEXT,
                        emergency BOOLEAN DEFAULT FALSE,
                        message TEXT,
                        status TEXT DEFAULT 'new',
                        created_at TEXT,
                        updated_at TEXT
                    )
                    """
                )
            conn.commit()
            conn.close()
            return
        except Exception:
            pass

    conn = sqlite3.connect(CALL_RECORDS_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tollfree_calls (
            id TEXT PRIMARY KEY,
            caller_number TEXT,
            language TEXT,
            problem TEXT,
            mode TEXT,
            emergency INTEGER DEFAULT 0,
            message TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_call_record(record):
    ensure_call_records_table()
    payload = {
        "id": record.get("id") or f"CALL-{random.randint(100000, 999999)}",
        "caller_number": record.get("caller_number") or "anonymous",
        "language": normalize_tollfree_language(record.get("language")),
        "problem": (record.get("problem") or "").strip(),
        "mode": (record.get("mode") or "voice").strip().lower(),
        "emergency": bool(record.get("emergency")),
        "message": (record.get("message") or "").strip(),
        "status": record.get("status") or "new",
        "created_at": record.get("created_at") or datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "updated_at": record.get("updated_at") or datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }

    if DATABASE_URL:
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tollfree_calls (id, caller_number, language, problem, mode, emergency, message, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        caller_number = EXCLUDED.caller_number,
                        language = EXCLUDED.language,
                        problem = EXCLUDED.problem,
                        mode = EXCLUDED.mode,
                        emergency = EXCLUDED.emergency,
                        message = EXCLUDED.message,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        payload["id"],
                        payload["caller_number"],
                        payload["language"],
                        payload["problem"],
                        payload["mode"],
                        payload["emergency"],
                        payload["message"],
                        payload["status"],
                        payload["created_at"],
                        payload["updated_at"],
                    ),
                )
            conn.commit()
            conn.close()
            return payload
        except Exception:
            pass

    conn = sqlite3.connect(CALL_RECORDS_DB)
    conn.execute(
        """
        INSERT OR REPLACE INTO tollfree_calls (id, caller_number, language, problem, mode, emergency, message, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["id"],
            payload["caller_number"],
            payload["language"],
            payload["problem"],
            payload["mode"],
            int(payload["emergency"]),
            payload["message"],
            payload["status"],
            payload["created_at"],
            payload["updated_at"],
        ),
    )
    conn.commit()
    conn.close()
    return payload


def load_call_records(limit=50):
    ensure_call_records_table()
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, caller_number, language, problem, mode, emergency, message, status, created_at, updated_at FROM tollfree_calls ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cur.fetchall()
            conn.close()
            return [
                {
                    "id": row[0],
                    "caller_number": row[1],
                    "language": row[2],
                    "problem": row[3],
                    "mode": row[4],
                    "emergency": bool(row[5]),
                    "message": row[6],
                    "status": row[7],
                    "created_at": row[8],
                    "updated_at": row[9],
                }
                for row in rows
            ]
        except Exception:
            pass

    conn = sqlite3.connect(CALL_RECORDS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, caller_number, language, problem, mode, emergency, message, status, created_at, updated_at FROM tollfree_calls ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "caller_number": row["caller_number"],
            "language": row["language"],
            "problem": row["problem"],
            "mode": row["mode"],
            "emergency": bool(row["emergency"]),
            "message": row["message"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_user_conversations(user_id):
    conversations = read_json_conversations().get(user_id, [])
    return conversations if isinstance(conversations, list) else []


def save_user_conversations(user_id, conversations):
    store = read_json_conversations()
    store[user_id] = list(conversations or [])
    write_json_conversations(store)


def read_family_data():
    if not os.path.exists(FAMILY_DATA_FILE):
        return {}
    try:
        with open(FAMILY_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError, OSError):
        return {}


def write_family_data(data):
    with open(FAMILY_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data or {}, f, ensure_ascii=False, indent=2)


def family_account(store, owner_id):
    account = store.get(owner_id)
    if not isinstance(account, dict):
        account = {}
        store[owner_id] = account
    account.setdefault("members", [])
    account.setdefault("records", {})
    account.setdefault("vaccinations", [])
    account.setdefault("reminders", {})
    return account


def family_members(owner_id, account=None):
    user = session.get("primary_profile") or {}
    primary_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    if not primary_name:
        primary_name = session.get("username") or "Primary account"
    members = [{
        "id": "self",
        "name": primary_name,
        "age": user.get("age"),
        "gender": user.get("gender") or "",
        "relation": "self",
        "is_primary": True,
    }]
    if account:
        members.extend(account.get("members", []))
    return members


def active_family_member_id(owner_id):
    store = read_family_data()
    account = store.get(owner_id, {})
    valid_ids = {member.get("id") for member in family_members(owner_id, account)}
    member_id = session.get("active_member_id", "self")
    if member_id not in valid_ids:
        member_id = "self"
        session["active_member_id"] = member_id
    return member_id


def save_family_record(record_type, fields):
    if not is_logged_in():
        return None
    owner_id = session["user_id"]
    member_id = active_family_member_id(owner_id)
    store = read_family_data()
    account = family_account(store, owner_id)
    record = {
        "id": str(uuid.uuid4()),
        "member_id": member_id,
        "type": record_type,
        "created_at": datetime.now().isoformat(),
        **fields,
    }
    records = account["records"].setdefault(member_id, [])
    records.insert(0, record)
    del records[200:]
    write_family_data(store)
    return record


def init_db():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT UNIQUE,
                    password_hash TEXT,
                    provider TEXT DEFAULT 'local',
                    google_sub TEXT,
                    age INTEGER,
                    gender TEXT,
                    weight REAL,
                    height INTEGER,
                    blood_group TEXT,
                    allergies TEXT,
                    emergency_name TEXT,
                    emergency_phone TEXT,
                    created_at TEXT
                )
                """
            )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def migrate_legacy_users():
    if not os.path.exists(USERS_FILE):
        return

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            legacy_users = json.load(f)
    except (ValueError, json.JSONDecodeError):
        return

    if not legacy_users:
        return

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            existing_count = cur.fetchone()[0]
        conn.close()
    except Exception:
        return

    if existing_count > 0:
        return

    save_users(legacy_users)


def load_users():
    try:
        init_db()
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY created_at")
            rows = cur.fetchall()
        conn.close()

        users = {}
        for row in rows:
            user = {"id": row[0], "first_name": row[1], "last_name": row[2], "email": row[3], "password_hash": row[4], "provider": row[5], "google_sub": row[6], "age": row[7], "gender": row[8], "weight": row[9], "height": row[10], "blood_group": row[11], "allergies": row[12], "emergency_name": row[13], "emergency_phone": row[14], "created_at": row[15]}
            users[row[0]] = user

        if not users and os.path.exists(USERS_FILE):
            migrate_legacy_users()
            return load_users()

        return users
    except Exception:
        return read_json_users()


def save_users(users):
    try:
        init_db()
        conn = get_db_connection()
        with conn.cursor() as cur:
            for user_id, user in (users or {}).items():
                payload = (
                    user_id,
                    user.get("first_name"),
                    user.get("last_name"),
                    user.get("email"),
                    user.get("password_hash"),
                    user.get("provider", "local"),
                    user.get("google_sub"),
                    user.get("age"),
                    user.get("gender"),
                    user.get("weight"),
                    user.get("height"),
                    user.get("blood_group"),
                    user.get("allergies"),
                    user.get("emergency_name"),
                    user.get("emergency_phone"),
                    user.get("created_at") or datetime.now().isoformat(),
                )
                cur.execute(
                    """
                    INSERT INTO users (id, first_name, last_name, email, password_hash, provider, google_sub, age, gender, weight, height, blood_group, allergies, emergency_name, emergency_phone, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        provider = EXCLUDED.provider,
                        google_sub = EXCLUDED.google_sub,
                        age = EXCLUDED.age,
                        gender = EXCLUDED.gender,
                        weight = EXCLUDED.weight,
                        height = EXCLUDED.height,
                        blood_group = EXCLUDED.blood_group,
                        allergies = EXCLUDED.allergies,
                        emergency_name = EXCLUDED.emergency_name,
                        emergency_phone = EXCLUDED.emergency_phone,
                        created_at = EXCLUDED.created_at
                    """,
                    payload,
                )
        conn.commit()
        conn.close()
        return True
    except Exception:
        write_json_users(users)
        return False


def sanitize_name(value):
    if not value:
        return ""
    cleaned = re.sub(r"[^A-Za-z\s]", "", value.strip())
    return " ".join(cleaned.split())

def is_valid_name(value):
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", value.strip()))

def is_logged_in():
    return "user_id" in session

def get_current_user():
    if not is_logged_in():
        return None
    users = load_users()
    return users.get(session["user_id"])

@app.before_request
def enforce_auth():
    public_paths = {"/auth/login", "/auth/signup", "/static"}
    if request.path.startswith("/static/"):
        return None

    if request.path in public_paths:
        if is_logged_in() and request.path in {"/auth/login", "/auth/signup"}:
            return redirect("/")
        return None

    if request.path.startswith("/auth/"):
        if not is_logged_in():
            return redirect("/auth/login")
        return None

    if request.path == "/" or request.path == "/index.html" or request.path.startswith("/page/"):
        if not is_logged_in():
            return redirect("/auth/login")

try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except ImportError:
    groq_client = None


# ── Language dictionary ───────────────────────────────────────────────────────
INDIAN_LANGUAGES = [
    {"code": "as", "name": "Assamese", "native": "অসমীয়া", "flag": "🇮🇳"},
    {"code": "bn", "name": "Bengali", "native": "বাংলা", "flag": "🇮🇳"},
    {"code": "brx", "name": "Bodo", "native": "बड़ो", "flag": "🇮🇳"},
    {"code": "doi", "name": "Dogri", "native": "डोगरी", "flag": "🇮🇳"},
    {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી", "flag": "🇮🇳"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
    {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ", "flag": "🇮🇳"},
    {"code": "ks", "name": "Kashmiri", "native": "कॉशुर", "flag": "🇮🇳"},
    {"code": "kok", "name": "Konkani", "native": "कोंकणी", "flag": "🇮🇳"},
    {"code": "mai", "name": "Maithili", "native": "मैथिली", "flag": "🇮🇳"},
    {"code": "ml", "name": "Malayalam", "native": "മലയാളം", "flag": "🇮🇳"},
    {"code": "mni", "name": "Manipuri", "native": "মৈতৈলোন্", "flag": "🇮🇳"},
    {"code": "mr", "name": "Marathi", "native": "मराठी", "flag": "🇮🇳"},
    {"code": "ne", "name": "Nepali", "native": "नेपाली", "flag": "🇮🇳"},
    {"code": "or", "name": "Odia", "native": "ଓଡ଼ିଆ", "flag": "🇮🇳"},
    {"code": "pa", "name": "Punjabi", "native": "ਪੰਜਾਬੀ", "flag": "🇮🇳"},
    {"code": "sa", "name": "Sanskrit", "native": "संस्कृतम्", "flag": "🇮🇳"},
    {"code": "sat", "name": "Santali", "native": "ᱥᱟᱱᱛᱟᱲᱤ", "flag": "🇮🇳"},
    {"code": "sd", "name": "Sindhi", "native": "سنڌي", "flag": "🇮🇳"},
    {"code": "ta", "name": "Tamil", "native": "தமிழ்", "flag": "🇮🇳"},
    {"code": "te", "name": "Telugu", "native": "తెలుగు", "flag": "🇮🇳"},
    {"code": "ur", "name": "Urdu", "native": "اردو", "flag": "🇮🇳"},
]

LANGUAGE_NAMES = {"en": "English", **{item["code"]: item["name"] for item in INDIAN_LANGUAGES}, "es": "Spanish", "fr": "French"}

TRANSLATIONS = {
    "en": {
        "home": "Home", "ai_chat": "AI Chat", "health_records": "Health Records",
        "knowledge": "Knowledge", "bmd": "BMD", "pulse": "Pulse", "reports": "Reports",
        "settings": "Settings", "analytics": "Analytics",
        "languages": "Languages",
        "dashboard_title": "Dashboard",
        "health_records_label": "Health Records",
        "weekly": "Weekly",
    },
    "hi": {
        "home": "होम", "ai_chat": "AI चैट", "health_records": "स्वास्थ्य रिकॉर्ड",
        "knowledge": "ज्ञान", "bmd": "BMD", "pulse": "पल्स", "reports": "रिपोर्ट",
        "settings": "सेटिंग्स", "analytics": "एनालिटिक्स",
        "languages": "भाषाएँ",
        "dashboard_title": "डैशबोर्ड",
        "health_records_label": "स्वैस्थ्य रिकॉर्ड",
        "weekly": "साप्ताहिक",
    },
    "or": {
        "home": "ହୋମ୍", "ai_chat": "AI ଚାଟ୍", "health_records": "ସ୍ୱାସ୍ଥ୍ୟ ରେକର୍ଡ",
        "knowledge": "ଜ୍ଞାନ", "bmd": "BMD", "pulse": "ପଲ୍ସ", "reports": "ରିପୋର୍ଟ",
        "settings": "ସେଟିଂ", "analytics": "ଏନାଲିଟିକ୍ସ",
        "languages": "ଭାଷା",
        "dashboard_title": "ଡ୍ୟାଶବୋର୍ଡ",
        "health_records_label": "ସ୍ୱାସ୍ଥ୍ୟ ରେକର୍ଡ",
        "weekly": "ସାପ୍ତାହିକ",
    },
    "es": {
        "home": "Inicio", "ai_chat": "Chat IA", "health_records": "Registros",
        "knowledge": "Conocimiento", "bmd": "BMD", "pulse": "Pulso", "reports": "Informes",
        "settings": "Ajustes", "analytics": "Análisis",
        "languages": "Idiomas",
    },
    "fr": {
        "home": "Accueil", "ai_chat": "Chat IA", "health_records": "Dossiers",
        "knowledge": "Connaissances", "bmd": "BMD", "pulse": "Pouls", "reports": "Rapports",
        "settings": "Paramètres", "analytics": "Analytique",
        "languages": "Langues",
    },
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"]

# ── Mock data helpers ─────────────────────────────────────────────────────────

def tracker_data():
    return {
        "time": "09:45 AM",
        "temp": "98.57°F",
        "percent": "3.62%",
        "bar_values": [12, 18, 95, 42, 30, 25, 78],
        "months": MONTHS,
    }

def vitals_data():
    return {
        "oxygen_pct": "97.5",
        "oxygen_delta": "±0.2% from last week",
        "bpm_time": "12:02",
        "bpm_value": "89",
        "bpm_delta": "±0.2% from last week",
    }

def wellness_data():
    return {
        "kcal": "19,365.29",
        "kcal_badge": "↗10%",
        "calories_burned": "265",
        "workouts": "8",
        "workouts_badge": "↗24%",
        "blockchain_pct": round(random.uniform(85, 99.9), 1),
    }

def breath_data():
    days = ["S", "M", "T", "W", "T", "F", "S"]
    levels = [random.uniform(20, 100) for _ in range(7)]
    return {
        "change": "↗278%",
        "days": days,
        "levels": levels,
        "current_status": "Normal",
        "current_value": random.randint(10, 15),
        "user_id": "35,m2",
    }

def comparison_data():
    """7-day comparison metrics."""
    return {
        "sleep": {
            "this_week": "7h 48m", "last_week": "6h 52m",
            "change_pct": 14, "trend": "up",
            "this_vals": [6.5, 7.0, 8.0, 7.0, 6.5, 8.0, 7.8],
            "last_vals": [6.0, 6.5, 7.0, 6.5, 6.0, 7.5, 7.0],
        },
        "water": {
            "this_week": "2.1 L", "last_week": "1.6 L",
            "change_pct": 31, "trend": "up",
            "this_vals": [1.8, 2.0, 2.2, 2.1, 2.3, 2.0, 2.1],
            "last_vals": [1.5, 1.6, 1.4, 1.7, 1.5, 1.8, 1.6],
        },
        "activity": {
            "this_week": "6,842", "last_week": "5,230",
            "change_pct": 31, "trend": "up",
            "this_vals": [5500, 6200, 7000, 6800, 7200, 6500, 6842],
            "last_vals": [4200, 4800, 5500, 5000, 5800, 5200, 5230],
        },
        "mood": {
            "this_week": "Good", "last_week": "Fair",
            "change_pct": 20, "trend": "up",
            "this_vals": [3.5, 4.0, 4.2, 3.8, 4.5, 4.0, 4.1],
            "last_vals": [3.0, 3.2, 3.5, 3.0, 3.8, 3.5, 3.3],
        },
        "heart_rate": {
            "this_week": "72 bpm", "last_week": "76 bpm",
            "change_pct": 5, "trend": "down",
            "this_vals": [75, 72, 70, 73, 71, 74, 72],
            "last_vals": [78, 76, 77, 75, 78, 76, 76],
        },
    }

def knowledge_search(query):
    """RAG-style mock knowledge base."""
    q = re.sub(r"[^a-z0-9\s]", " ", (query or "").lower())
    # Handle common typing mistakes without changing the user's displayed question.
    q = re.sub(r"\bsuger\b|\bsugr\b", "sugar", q)
    sources = []
    answer = ""
    table = None

    if "blood sugar" in q or "glucose" in q or "diabetes" in q:
        table = [
            ("Test", "Reference range", "Unit"),
            ("Fasting Blood Glucose", "70 – 99", "mg/dL"),
            ("2 Hours After Eating", "< 140", "mg/dL"),
            ("HbA1c (average over 3 months)", "< 5.7", "%"),
        ]
        answer = (
            "For a healthy adult, the normal range of blood sugar (glucose) levels depends "
            "on when the test is done (fasting or after eating). Here are the generally "
            "accepted ranges from trusted sources:"
        )
        sources = [
            {"name": "WHO – Diabetes Factsheet", "url": "who.int/health-topics/diabetes", "relevance": "High"},
            {"name": "ICMR – Blood Glucose Guidelines", "url": "icmr.gov.in", "relevance": "High"},
            {"name": "Blood Sugar Levels", "url": "nhs.uk", "relevance": "Medium"},
        ]
    elif "sleep" in q or "insomnia" in q:
        table = [
            ("Age group", "Recommended sleep", "Unit"),
            ("Adults (18-64)", "7-9 hours", "hours/night"),
            ("Older adults (65+)", "7-8 hours", "hours/night"),
            ("Teenagers (14-17)", "8-10 hours", "hours/night"),
        ]
        answer = (
            "Sleep requirements vary by age group. The National Sleep Foundation and WHO "
            "recommend the following durations for optimal health:"
        )
        sources = [
            {"name": "WHO – Sleep & Health", "url": "who.int/news-room/fact-sheets", "relevance": "High"},
            {"name": "National Sleep Foundation", "url": "thesleepfoundation.org", "relevance": "High"},
        ]
    elif "heart rate" in q or "bpm" in q or "pulse" in q:
        table = [
            ("Measure", "Reference range", "Unit"),
            ("Resting Heart Rate (Adults)", "60 – 100", "bpm"),
            ("Athletes", "40 – 60", "bpm"),
            ("Target Exercise Zone", "50-85%", "of max HR"),
        ]
        answer = (
            "A normal resting heart rate for adults ranges from 60 to 100 beats per minute. "
            "Well-trained athletes may have a resting heart rate closer to 40-60 bpm."
        )
        sources = [
            {"name": "NHS – Heart Rate", "url": "nhs.uk/conditions/blood-pressure", "relevance": "High"},
            {"name": "AHA – Heart Rate Guidelines", "url": "heart.org", "relevance": "Medium"},
        ]
    elif "hemoglobin" in q or "hb" in q:
        table = [
            ("Group", "Reference range", "Unit"),
            ("Men", "13.8 – 17.2", "g/dL"),
            ("Women", "12.1 – 15.1", "g/dL"),
            ("Children (1-5 yrs)", "11.0 – 13.5", "g/dL"),
        ]
        answer = (
            "Hemoglobin levels indicate your red blood cell count and oxygen-carrying capacity. "
            "Low hemoglobin may indicate anemia, while high levels can suggest dehydration or lung disease."
        )
        sources = [
            {"name": "WHO – Haemoglobin Concentrations", "url": "who.int/vmnis/indicators/hemoglobin", "relevance": "High"},
            {"name": "ICMR – Haemoglobin Reference", "url": "icmr.gov.in", "relevance": "Medium"},
        ]
    else:
        answer = (
            f"Here is general health information about \"{query}\":\n\n"
            "• What it may mean: The answer depends on your age, symptoms, medicines, medical history, "
            "and any test results. A single symptom or reading cannot confirm a diagnosis.\n"
            "• What you can do now: Note when it started, how severe it is, what makes it better or worse, "
            "and any related symptoms. Follow the instructions on any prescribed medicine and avoid changing "
            "a dose without speaking with a clinician.\n"
            "• When to get help: Seek urgent care for chest pain, severe breathing difficulty, fainting, "
            "new confusion, sudden weakness, uncontrolled bleeding, or a rapidly worsening condition.\n"
            "• Next step: Share the person's age, the exact symptom or report value, duration, and relevant "
            "medical conditions for more targeted general guidance. A healthcare professional should provide "
            "personalized advice."
        )

    related = [
        f"What are the symptoms of abnormal {q.split()[0] if q else 'blood sugar'}?",
        f"What foods help maintain normal {q.split()[0] if q else 'blood sugar'} levels?",
        f"How often should I check my {q.split()[0] if q else 'blood sugar'}?",
        f"Can stress affect my {q.split()[0] if q else 'blood sugar'} levels?",
    ]

    return {"answer": answer, "table": table, "sources": sources, "related": related}


def clean_markdown_text(text):
    if not text:
        return ""
    cleaned = str(text)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\*)\*(?!\*)", "", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*]\s+", "• ", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("`", "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def localized_fallback(language):
    fallbacks = {
        "hi": "मैं आपके लक्षण, पोषण, नींद और स्वास्थ्य रिपोर्ट समझने में मदद कर सकता हूँ। कृपया बताएं कि यह कब से हो रहा है और क्या स्थिति बिगड़ रही है।",
        "or": "ମୁଁ ଆପଣଙ୍କ ଲକ୍ଷଣ, ପୋଷଣ, ନିଦ୍ରା ଏବଂ ସ୍ୱାସ୍ଥ୍ୟ ରିପୋର୍ଟ ବୁଝିବାରେ ସାହାଯ୍ୟ କରିପାରିବି। ଏହା କେବେଠାରୁ ହେଉଛି ଏବଂ ଅବସ୍ଥା ଖରାପ ହେଉଛି କି ଜଣାନ୍ତୁ।",
        "es": "Puedo ayudarte a entender síntomas, nutrición, sueño e informes de salud. Comparte desde cuándo ocurre y si está empeorando.",
        "fr": "Je peux vous aider à comprendre les symptômes, la nutrition, le sommeil et les rapports de santé. Indiquez depuis quand cela dure et si cela s'aggrave.",
    }
    return fallbacks.get(language, "I can help you understand symptoms, nutrition, sleep and health reports. Please share how long this has been happening and whether it is getting worse.")


def localized_chat_response(message, language, symptom_result):
    """Return useful offline guidance when the optional AI provider is unavailable."""
    query = str(message or "").lower()
    detected = symptom_result.get("detected", {})

    english = {
        "fever": (
            "You mentioned fever. Fever is often caused by an infection, but the cause cannot be confirmed from one message.\n\n"
            "What to do now:\n"
            "• Check and record your temperature with a thermometer every 4–6 hours.\n"
            "• Drink water or oral rehydration solution in small, frequent amounts and rest.\n"
            "• Wear light clothing and avoid alcohol. Do not use antibiotics unless prescribed.\n"
            "• Ask a pharmacist or clinician before taking paracetamol, especially if you have liver disease, take other medicines, or this is for a child.\n\n"
            "Get medical advice if fever lasts more than 3 days, keeps returning, or is accompanied by rash, persistent vomiting, severe weakness, confusion, or dehydration. Seek urgent care for breathing difficulty, seizure, fainting, stiff neck, or severe headache.\n\n"
            "Please share your temperature, age, how long it has been present, and any cough, pain, vomiting, or recent travel."
        ),
        "headache": (
            "You mentioned a headache. Common causes include dehydration, poor sleep, stress, eye strain, viral illness, or migraine; a diagnosis needs an examination.\n\n"
            "For now:\n"
            "• Rest in a quiet, dim room and drink water.\n"
            "• Take a break from screens and note the location, severity, triggers, and duration.\n"
            "• Use only medicines that are safe for you and follow the package or clinician instructions. Avoid taking pain medicine repeatedly without medical advice.\n\n"
            "Seek urgent care for a sudden worst-ever headache, head injury, fever with stiff neck, confusion, fainting, vision loss, weakness, numbness, speech trouble, or repeated vomiting.\n\n"
            "Tell me when it started, where it hurts, severity from 0–10, and whether you have fever, nausea, vision changes, or high blood pressure."
        ),
        "cough": (
            "You mentioned a cough. It may occur with a cold, allergy, asthma, reflux, or another infection, so duration and associated symptoms matter.\n\n"
            "Helpful steps:\n"
            "• Drink warm fluids, rest, and avoid smoke, dust, and strong fragrances.\n"
            "• Do not start antibiotics or combine cough medicines without advice. Honey may soothe cough in adults and children over 1 year, but never give honey to an infant under 1 year.\n"
            "• Arrange a medical review if it lasts more than 3 weeks, keeps worsening, or is associated with fever, wheezing, weight loss, or night sweats.\n\n"
            "Get urgent help for breathing difficulty, blue lips, chest pain, coughing blood, confusion, or severe weakness.\n\n"
            "Please share how long you have been coughing, whether it is dry or with mucus, your age, and whether you have fever or breathing trouble."
        ),
        "sleep": (
            "For most adults, 7–9 hours of sleep is a useful target, but quality and daytime function matter too.\n\n"
            "Try this for the next 1–2 weeks:\n"
            "• Keep the same wake-up time every day and get morning daylight.\n"
            "• Avoid caffeine late in the day, heavy meals near bedtime, and screens for about 1 hour before sleep.\n"
            "• Keep the room dark, quiet, and cool. If you are awake for a long time, do a calm activity and return when sleepy.\n\n"
            "Speak with a clinician if sleep difficulty lasts more than 2–4 weeks, affects daily life, or includes loud snoring, choking during sleep, mania, or severe low mood.\n\n"
            "Tell me your usual sleep time, wake time, how long this has been happening, and whether stress, pain, caffeine, or snoring is involved."
        ),
        "nutrition": (
            "A balanced plate is usually more useful than a single food or supplement. Aim for vegetables or fruit, a protein source, whole grains, and enough water.\n\n"
            "Practical steps:\n"
            "• Include pulses, eggs, fish, dairy, or another protein you tolerate.\n"
            "• Prefer minimally processed foods and limit excess sugar, salt, and packaged snacks.\n"
            "• Do not start supplements or extreme diets without checking your health conditions and medicines.\n\n"
            "Personal advice depends on age, weight goals, pregnancy, diabetes, kidney or liver disease, allergies, and activity level. Share your goal and any medical conditions for more specific general guidance."
        ),
    }

    hindi = {
        "fever": (
            "आपने बुखार बताया है। बुखार संक्रमण के कारण हो सकता है, लेकिन केवल एक संदेश से कारण तय नहीं किया जा सकता।\n\n"
            "अभी क्या करें:\n"
            "• थर्मामीटर से तापमान हर 4–6 घंटे में जाँचकर लिखें।\n"
            "• पानी या ORS थोड़ी-थोड़ी मात्रा में लें और आराम करें।\n"
            "• हल्के कपड़े पहनें। बिना डॉक्टर की सलाह एंटीबायोटिक शुरू न करें।\n"
            "• पैरासिटामोल लेने से पहले उम्र, दूसरी दवाओं और लिवर की बीमारी को ध्यान में रखें तथा लेबल/डॉक्टर के निर्देश मानें।\n\n"
            "बुखार 3 दिन से अधिक रहे, बार-बार आए, या उल्टी, दाने, बहुत कमजोरी, भ्रम या पानी की कमी हो तो डॉक्टर से संपर्क करें। सांस में दिक्कत, बेहोशी, दौरा, गर्दन अकड़ना या तेज सिरदर्द हो तो तुरंत अस्पताल जाएँ।\n\n"
            "कृपया तापमान, उम्र, बुखार कितने समय से है और साथ में खाँसी, दर्द या उल्टी है या नहीं बताएं।"
        ),
        "headache": (
            "सिरदर्द के सामान्य कारण पानी की कमी, नींद की कमी, तनाव, आँखों पर जोर, वायरल बीमारी या माइग्रेन हो सकते हैं। सही कारण के लिए जाँच जरूरी हो सकती है।\n\n"
            "अभी आराम करें, पानी पिएँ, स्क्रीन से ब्रेक लें और दर्द की जगह, तीव्रता तथा अवधि नोट करें। दवा केवल लेबल या डॉक्टर के निर्देश के अनुसार लें और बार-बार painkiller बिना सलाह न लें।\n\n"
            "अचानक बहुत तेज सिरदर्द, सिर पर चोट, गर्दन अकड़ना, भ्रम, बेहोशी, आँखों की रोशनी कम होना, हाथ-पैर में कमजोरी/सुन्नपन, बोलने में दिक्कत या बार-बार उल्टी हो तो तुरंत चिकित्सा सहायता लें।\n\n"
            "दर्द कब शुरू हुआ, 0–10 में कितना है और बुखार, मतली या vision problem है या नहीं बताएं।"
        ),
    }

    odia = {
        "fever": (
            "ଆପଣ ଜ୍ୱର ବିଷୟରେ କହିଛନ୍ତି। ଜ୍ୱର ସଂକ୍ରମଣ ଯୋଗୁଁ ହୋଇପାରେ, କିନ୍ତୁ ଗୋଟିଏ ମେସେଜ୍‌ରୁ କାରଣ ନିଶ୍ଚିତ କରାଯାଇପାରିବ ନାହିଁ।\n\n"
            "ଏବେ କଣ କରିବେ:\n"
            "• ଥର୍ମୋମିଟରରେ ପ୍ରତି 4–6 ଘଣ୍ଟାରେ ତାପମାତ୍ରା ମାପି ଲେଖନ୍ତୁ।\n"
            "• ପାଣି କିମ୍ବା ORS ଅଳ୍ପ ଅଳ୍ପ କରି ପିଅନ୍ତୁ ଏବଂ ବିଶ୍ରାମ ନିଅନ୍ତୁ।\n"
            "• ଡାକ୍ତରଙ୍କ ପରାମର୍ଶ ବିନା ଆଣ୍ଟିବାୟୋଟିକ୍ ନିଅନ୍ତୁ ନାହିଁ।\n\n"
            "ଜ୍ୱର 3 ଦିନରୁ ଅଧିକ ରହିଲେ, ବାରମ୍ବାର ଫେରିଲେ, କିମ୍ବା ବାନ୍ତି, ଦୁର୍ବଳତା, ଦ୍ୱନ୍ଦ୍ୱ, ଶ୍ୱାସକଷ୍ଟ ହେଲେ ଡାକ୍ତରଙ୍କୁ ଦେଖାନ୍ତୁ। ବେହୋସ, ଦୌରା, ଗଳା କଠିନ କିମ୍ବା ଅତ୍ୟଧିକ ମୁଣ୍ଡବିନ୍ଧା ହେଲେ ତୁରନ୍ତ ହସ୍ପିଟାଲ୍ ଯାଆନ୍ତୁ।\n\n"
            "ଆପଣଙ୍କ ତାପମାତ୍ରା, ବୟସ, ଜ୍ୱର କେତେ ସମୟ ହେଲା ଏବଂ ଖାସି/ବାନ୍ତି/ଯନ୍ତ୍ରଣା ଅଛି କି ଜଣାନ୍ତୁ।"
        ),
    }

    if any(word in query for word in ["fever", "bukhar", "ତାପ", "ଜ୍ୱର"]):
        intent = "fever"
    elif any(word in query for word in ["headache", "head pain", "sar dard", "ମୁଣ୍ଡବିନ୍ଧା"]):
        intent = "headache"
    elif any(word in query for word in ["cough", "khansi", "ଖାସି", "କାଶ"]):
        intent = "cough"
    elif any(word in query for word in ["sleep", "insomnia", "neend", "ନିଦ"]):
        intent = "sleep"
    elif any(word in query for word in ["food", "diet", "nutrition", "eat", "meal", "khana", "खाना", "भोजन", "ଖାଦ୍ୟ"]):
        intent = "nutrition"
    else:
        intent = None

    if language == "hi" and intent in hindi:
        return hindi[intent]
    if language == "or" and intent in odia:
        return odia[intent]
    if language == "or":
        return (
            f"ଆପଣ କହିଥିବା କଥା: {message}\n\n"
            "ଏହା ସାଧାରଣ ସ୍ୱାସ୍ଥ୍ୟ ସୂଚନା, ନିଶ୍ଚିତ ରୋଗ ନିର୍ଣ୍ଣୟ ନୁହେଁ। ବୟସ, ଲକ୍ଷଣ କେବେ ଆରମ୍ଭ ହେଲା, ତୀବ୍ରତା, ଚାଲୁଥିବା ଔଷଧ ଏବଂ ପୁରୁଣା ରୋଗ ବିଷୟରେ ଜଣାଇଲେ ଉତ୍ତର ଅଧିକ ଉପଯୋଗୀ ହେବ।\n\n"
            "ଏବେ ପାଣି ପିଅନ୍ତୁ, ବିଶ୍ରାମ ନିଅନ୍ତୁ ଏବଂ ଡାକ୍ତରଙ୍କ ପରାମର୍ଶ ବିନା ଆଣ୍ଟିବାୟୋଟିକ୍ କିମ୍ବା ନୂଆ ଔଷଧ ନିଅନ୍ତୁ ନାହିଁ। ଲକ୍ଷଣ ବଢ଼ିଲେ କିମ୍ବା 2–3 ଦିନରେ ଭଲ ନହେଲେ ଡାକ୍ତରଙ୍କୁ ଦେଖାନ୍ତୁ।\n\n"
            "ଛାତି ଯନ୍ତ୍ରଣା, ଶ୍ୱାସକଷ୍ଟ, ବେହୋସ, ହଠାତ୍ ଦୁର୍ବଳତା, ଦ୍ୱନ୍ଦ୍ୱ କିମ୍ବା ବାରମ୍ବାର ବାନ୍ତି ହେଲେ ତୁରନ୍ତ 108/112 କୁ ଫୋନ୍ କରନ୍ତୁ କିମ୍ବା ନିକଟସ୍ଥ ହସ୍ପିଟାଲ୍ ଯାଆନ୍ତୁ।"
        )
    if intent in english:
        return english[intent]

    level = detected.get("level", "Moderate")
    return (
        f"आपने जो बताया: {message}\n\n"
        "यह सामान्य स्वास्थ्य जानकारी है, पक्का diagnosis नहीं। सही सलाह के लिए उम्र, लक्षण कब शुरू हुए, तीव्रता, चल रही दवाएँ और पुरानी बीमारी महत्वपूर्ण हैं।\n\n"
        "अभी:\n"
        "• लक्षण कब और कितनी बार हो रहे हैं लिखें।\n"
        "• पानी, आराम और संतुलित भोजन रखें; बिना सलाह दवा या antibiotic शुरू न करें।\n"
        "• स्थिति बिगड़ती है या 2–3 दिन में सुधार नहीं होता तो clinician से मिलें।\n\n"
        "छाती में दर्द, सांस लेने में कठिनाई, बेहोशी, अचानक कमजोरी, भ्रम, लगातार उल्टी या बहुत तेज बिगड़ती स्थिति में तुरंत 108/112 या नजदीकी अस्पताल से संपर्क करें।\n\n"
        "कृपया उम्र, अवधि, severity और साथ के symptoms बताएं ताकि मैं अधिक उपयोगी सामान्य guidance दे सकूँ।"
    ) if language == "hi" else (
        f"You mentioned: {message}\n\n"
        "This is general health information, not a diagnosis. Please share age, duration, severity, medicines, and relevant medical conditions.\n\n"
        "Keep hydrated, rest, avoid self-starting antibiotics, and arrange clinical advice if symptoms persist or worsen. Seek urgent help for chest pain, breathing difficulty, fainting, sudden weakness, confusion, repeated vomiting, or rapid deterioration."
    )


def localized_safety_message(language, message):
    translations = {
        "hi": "⚠️ आपातकालीन चेतावनी: गंभीर लक्षण पाए गए हैं। कृपया तुरंत 108/112 पर कॉल करें या नजदीकी अस्पताल जाएं।",
        "or": "⚠️ ଜରୁରୀ ସତର୍କତା: ଗୁରୁତର ଲକ୍ଷଣ ଚିହ୍ନଟ ହୋଇଛି। ଦୟାକରି ତୁରନ୍ତ 108/112 କୁ କଲ୍ କରନ୍ତୁ କିମ୍ବା ନିକଟସ୍ଥ ହସ୍ପିଟାଲକୁ ଯାଆନ୍ତୁ।",
        "es": "⚠️ Alerta de emergencia: se detectaron síntomas graves. Llame inmediatamente al servicio de emergencias o vaya al hospital más cercano.",
        "fr": "⚠️ Alerte urgente : des symptômes graves ont été détectés. Appelez immédiatement les urgences ou rendez-vous à l'hôpital le plus proche.",
    }
    return translations.get(language, message)


def translate_user_message(message, language):
    """Translate the user's problem for the conversation display and model context."""
    if language == "en" or not message:
        return message
    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": (
                        f"Translate the user's health problem into {LANGUAGE_NAMES[language]}. "
                        "Translate Hinglish, mixed English, spelling mistakes, and informal text naturally. "
                        "Keep medicine names, numbers, symptoms, and medical units accurate. Return only the "
                        "translated problem, with no explanation or diagnosis."
                    )},
                    {"role": "user", "content": message},
                ],
                temperature=0.1,
                max_tokens=220,
            )
            translated = response.choices[0].message.content.strip()
            return translated or message
        except Exception:
            app.logger.exception("User message translation failed")

    common_hinglish_hi = {
        "mujhe sardi hua hai": "मुझे सर्दी हुई है",
        "mujhe bukhar hai": "मुझे बुखार है",
        "mujhe sar dard hai": "मुझे सिरदर्द है",
        "mujhe pet dard hai": "मुझे पेट में दर्द है",
        "mujhe khansi hai": "मुझे खांसी है",
        "mujhe saans lene mein dikkat hai": "मुझे सांस लेने में दिक्कत है",
        "mujhe chakkar aa raha hai": "मुझे चक्कर आ रहे हैं",
    }
    if language == "hi":
        return common_hinglish_hi.get(message.lower().strip(), message)
    common_health_phrases = {
        "ta": {"i have headache": "எனக்கு தலைவலி உள்ளது", "i have fever": "எனக்கு காய்ச்சல் உள்ளது", "i have cough": "எனக்கு இருமல் உள்ளது"},
        "te": {"i have headache": "నాకు తలనొప్పిగా ఉంది", "i have fever": "నాకు జ్వరం ఉంది", "i have cough": "నాకు దగ్గు ఉంది"},
        "bn": {"i have headache": "আমার মাথাব্যথা হচ্ছে", "i have fever": "আমার জ্বর হয়েছে", "i have cough": "আমার কাশি হয়েছে"},
        "mr": {"i have headache": "माझे डोके दुखत आहे", "i have fever": "मला ताप आला आहे", "i have cough": "मला खोकला आहे"},
        "gu": {"i have headache": "મારા માથામાં દુખાવો છે", "i have fever": "મને તાવ આવ્યો છે", "i have cough": "મને ઉધરસ છે"},
        "pa": {"i have headache": "ਮੇਰੇ ਸਿਰ ਵਿੱਚ ਦਰਦ ਹੈ", "i have fever": "ਮੈਨੂੰ ਬੁਖਾਰ ਹੈ", "i have cough": "ਮੈਨੂੰ ਖੰਘ ਹੈ"},
        "kn": {"i have headache": "ನನಗೆ ತಲೆನೋವು ಇದೆ", "i have fever": "ನನಗೆ ಜ್ವರ ಇದೆ", "i have cough": "ನನಗೆ ಕೆಮ್ಮು ಇದೆ"},
        "ml": {"i have headache": "എനിക്ക് തലവേദനയുണ്ട്", "i have fever": "എനിക്ക് പനിയുണ്ട്", "i have cough": "എനിക്ക് ചുമയുണ്ട്"},
        "or": {"i have headache": "ମୋର ମୁଣ୍ଡବିନ୍ଧା ହେଉଛି", "i have fever": "ମୋତେ ଜ୍ୱର ହୋଇଛି", "i have cough": "ମୋତେ କାଶ ହେଉଛି"},
        "ur": {"i have headache": "میرے سر میں درد ہے", "i have fever": "مجھے بخار ہے", "i have cough": "مجھے کھانسی ہے"},
    }
    translated_phrase = common_health_phrases.get(language, {}).get(message.lower().strip())
    if translated_phrase:
        return translated_phrase
    return message


def symptom_analysis(symptom):
    """Smart symptom intelligence with follow-up flow."""
    s = symptom.lower()
    red_flags = {
        "chest pain": {"level": "Urgent", "msg": "⚠️ CHEST PAIN DETECTED — Seek emergency care immediately. Call 108 / 112."},
        "difficulty breathing": {"level": "Urgent", "msg": "⚠️ BREATHING DIFFICULTY DETECTED — Seek emergency care immediately. Call 108 / 112."},
        "severe bleeding": {"level": "Urgent", "msg": "⚠️ SEVERE BLEEDING DETECTED — Seek emergency care immediately."},
        "loss of consciousness": {"level": "Urgent", "msg": "⚠️ LOSS OF CONSCIOUSNESS DETECTED — Seek emergency care immediately."},
        "stroke": {"level": "Urgent", "msg": "⚠️ STROKE SYMPTOMS DETECTED — Seek emergency care immediately. Call 108 / 112."},
        "severe headache": {"level": "High", "msg": "⚠️ SEVERE HEADACHE — Consult a doctor soon."},
        "high fever": {"level": "High", "msg": "⚠️ HIGH FEVER — Monitor closely, consult if >3 days."},
        "abdominal pain": {"level": "Moderate", "msg": "Abdominal pain can have many causes. Describe location and severity."},
        "headache": {"level": "Low", "msg": "Common headache — stay hydrated and rest."},
        "cough": {"level": "Low", "msg": "Cough — watch for duration and accompanying symptoms."},
        "fever": {"level": "Low", "msg": "Fever — monitor temperature regularly."},
        "fatigue": {"level": "Low", "msg": "Fatigue — could be lifestyle or medical."},
    }

    detected = None
    for flag, info in red_flags.items():
        if flag in s:
            detected = info
            break

    if not detected:
        detected = {"level": "Moderate", "msg": f"We'll explore your symptom \"{symptom}\" to understand better."}

    return {"symptom": symptom, "detected": detected}


def report_ocr_text(text):
    """Extract and explain health parameters from OCR text."""
    if not text or not str(text).strip():
        return {"params": [], "raw_text": ""}

    lines = [line.strip() for line in str(text).replace("\r", "").splitlines() if line.strip()]
    params = []
    seen = set()

    patterns = {
        "Hemoglobin": [r"(?:hemoglobin|hb)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(g/?dL|g\/dl|g\/dL)?", 12.0, 16.0, "g/dL"],
        "WBC": [r"(?:wbc|white blood cell)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/\u00b5l|/µL|/ul|/\u00b5L|/ul)?", 4000, 11000, "/µL"],
        "RBC": [r"(?:rbc|red blood cell)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:million/\u00b5l|million/µL|million/\u00b5L|million/ul|million/?\u00b5L)?", 4.0, 5.5, "million/µL"],
        "Platelet": [r"(?:platelet|plt)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/\u00b5l|/µL|/ul|/\u00b5L)?", 150000, 450000, "/µL"],
        "Glucose (Fasting)": [r"(?:fasting glucose|glucose fasting|fasting)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mg\/dl)?", 70, 100, "mg/dL"],
        "Glucose (Random)": [r"(?:random glucose|postprandial glucose|glucose random|pp glucose)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mg\/dl)?", 70, 140, "mg/dL"],
        "Creatinine": [r"(?:creatinine|serum creatinine)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mg\/dl)?", 0.6, 1.2, "mg/dL"],
        "Uric Acid": [r"(?:uric acid|uric acid serum)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mg\/dl)?", 2.4, 6.0, "mg/dL"],
        "Cholesterol": [r"(?:total cholesterol|cholesterol)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mg\/dl)?", 0, 200, "mg/dL"],
        "TSH": [r"(?:tsh|thyroid stimulating hormone)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mIU/L|miu/l|mIU\/L)?", 0.4, 4.0, "mIU/L"],
    }

    explanations = {
        "Hemoglobin": "Carries oxygen in blood. Low = anemia risk.",
        "Glucose (Fasting)": "Blood sugar after fasting. High = diabetes risk.",
        "Glucose (Random)": "Blood sugar at any time. High may indicate diabetes.",
        "Creatinine": "Kidney function marker. High = possible kidney issue.",
        "Uric Acid": "Waste product. High = gout risk.",
        "Cholesterol": "Blood fat level. High = heart disease risk.",
        "TSH": "Thyroid hormone regulator. High/low = thyroid disorder.",
        "WBC": "Immune cells. High = infection, Low = immune issue.",
        "RBC": "Oxygen-carrying cells. Low = anemia.",
        "Platelet": "Blood clotting cells. Low = bleeding risk.",
    }

    for name, (pattern, low, high, unit) in patterns.items():
        for line in lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if not match:
                continue
            value = float(match.group(1))
            status = "Normal"
            if value < low:
                status = "Low"
            elif value > high:
                status = "High"
            key = (name, value)
            if key in seen:
                continue
            seen.add(key)
            params.append({
                "name": name,
                "value": value,
                "unit": unit,
                "ref_range": f"{low}-{high}",
                "status": status,
                "explanation": explanations.get(name, "Reviewed for overall health."),
            })
            break

    if not params:
        for name, (pattern, low, high, unit) in patterns.items():
            match = re.search(pattern, str(text), re.IGNORECASE | re.DOTALL)
            if match:
                value = float(match.group(1))
                status = "Normal"
                if value < low:
                    status = "Low"
                elif value > high:
                    status = "High"
                params.append({
                    "name": name,
                    "value": value,
                    "unit": unit,
                    "ref_range": f"{low}-{high}",
                    "status": status,
                    "explanation": explanations.get(name, "Reviewed for overall health."),
                })
                break

    return {"params": params, "raw_text": text[:500]}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if not is_logged_in():
        return redirect("/auth/login")
    return render_template("index.html")

@app.route("/page/<path:name>")
def page(name):
    if not is_logged_in():
        return redirect("/auth/login")
    if name == "settings":
        return redirect(url_for("profile_page"))
    if name in {"nutrition", "bmd", "pulse", "records"}:
        return redirect(url_for("index"))
    template_path = os.path.join(app.template_folder, "pages", f"{name}.html")
    if not os.path.exists(template_path):
        return redirect(url_for("index"))
    return render_template(f"pages/{name}.html")


@app.route("/page/call-center")
def call_center_page():
    if not is_logged_in():
        return redirect("/auth/login")
    return render_template("pages/call-center.html")

@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/page/") or request.path.startswith("/api/"):
        if request.path.startswith("/page/"):
            return redirect(url_for("index"))
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404
    return redirect(url_for("index"))

@app.route("/api/tracker")
def api_tracker():
    return jsonify(tracker_data())

@app.route("/api/vitals")
def api_vitals():
    return jsonify(vitals_data())

@app.route("/api/wellness")
def api_wellness():
    return jsonify(wellness_data())

@app.route("/api/breath")
def api_breath():
    return jsonify(breath_data())


@app.route("/api/comparison")
def api_comparison():
    return jsonify(comparison_data())

@app.route("/api/knowledge", methods=["POST"])
def api_knowledge():
    data = request.get_json() or {}
    query = str(data.get("query", "")).strip()
    if not query:
        return jsonify({"error": "Question is required"}), 400
    requested_language = str(data.get("language", "en")).strip().lower()
    language = requested_language if requested_language in LANGUAGE_NAMES else "en"
    result = knowledge_search(query)
    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": (
                        f"You are a trusted health knowledge assistant. Reply only in {LANGUAGE_NAMES[language]}. "
                        "Answer the user's question with a detailed but easy-to-read solution. Include: what it is, "
                        "common causes or interpretation, practical next steps, warning signs, and when to see a "
                        "healthcare professional. Do not diagnose, invent lab ranges, or claim certainty. Preserve "
                        "medical values and units. Use short paragraphs and bullets. Return plain text only."
                    )},
                    {"role": "user", "content": f"Question: {query}\n\nRelevant trusted knowledge: {result['answer']}"},
                ],
                temperature=0.2,
                max_tokens=650,
            )
            result["answer"] = response.choices[0].message.content.strip()
        except Exception:
            app.logger.exception("Knowledge answer generation failed")
    elif language != "en":
        # Keep the API honest when the optional provider is unavailable.
        result["answer"] = localized_fallback(language) + "\n\n" + result["answer"]
    return jsonify({**result, "language": language})

@app.route("/api/symptom", methods=["POST"])
def api_symptom():
    data = request.get_json() or {}
    symptom = str(data.get("symptom", "")).strip()
    result = symptom_analysis(symptom)
    if symptom:
        save_family_record("symptom", {
            "title": "Symptom check",
            "symptom": symptom[:200],
            "level": result["detected"]["level"],
            "summary": result["detected"]["msg"][:300],
        })
    return jsonify(result)


@app.route("/api/translate-text", methods=["POST"])
def api_translate_text():
    data = request.get_json() or {}
    text = str(data.get("text", "")).strip()
    requested_language = str(data.get("language", "en")).strip().lower()
    language = requested_language if requested_language in LANGUAGE_NAMES else "en"
    if not text:
        return jsonify({"success": False, "message": "Text is required"}), 400
    translated = translate_user_message(text, language)
    return jsonify({
        "success": True,
        "language": language,
        "translated": translated,
        "changed": translated != text,
        "provider": "groq" if groq_client and translated != text else "local",
    })


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json() or {}
    message = str(data.get("message", "")).strip()
    requested_language = str(data.get("language", "en")).strip().lower()
    language = requested_language if requested_language in LANGUAGE_NAMES else "en"
    if not message:
        return jsonify({"success": False, "message": "Message is required"}), 400

    translated_message = translate_user_message(message, language)

    symptom_result = symptom_analysis(f"{message} {translated_message}")
    if symptom_result["detected"]["level"] in {"Urgent", "High", "Low"}:
        symptom_terms = (
            "severe headache", "high fever", "chest pain", "difficulty breathing",
            "severe bleeding", "loss of consciousness", "stroke", "abdominal pain",
            "headache", "cough", "fever", "fatigue",
        )
        symptom_text = f"{message} {translated_message}".lower()
        symptom = next((term for term in symptom_terms if term in symptom_text), message[:200])
        save_family_record("symptom", {
            "title": "Symptom check",
            "symptom": symptom,
            "level": symptom_result["detected"]["level"],
            "summary": symptom_result["detected"]["msg"][:300],
        })
    if symptom_result["detected"]["level"] in {"Urgent", "High"}:
        reply = clean_markdown_text(localized_safety_message(language, symptom_result["detected"]["msg"]))
        return jsonify({"success": True, "source": "safety", "reply": reply, "translated_message": translated_message, "original_message": message, "level": symptom_result["detected"]["level"], "language": language})

    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": (
                        f"You are Orbix Health Companion. Reply only in {LANGUAGE_NAMES[language]}. "
                        "Give a detailed but easy-to-understand answer with these sections when relevant: "
                        "what it may mean, what to do now, what to avoid, warning signs, and 2-3 follow-up questions. "
                        "Use bullet points, preserve medical numbers and units, do not diagnose, do not invent test results, "
                        "and recommend a clinician for persistent or concerning symptoms."
                    )},
                    {"role": "user", "content": translated_message},
                ],
                temperature=0.25,
                max_tokens=700,
            )
            reply = clean_markdown_text(response.choices[0].message.content.strip())
            return jsonify({"success": True, "source": "groq", "reply": reply, "translated_message": translated_message, "original_message": message, "level": "Normal", "language": language})
        except Exception:
            app.logger.exception("Groq chat request failed")

    return jsonify({
        "success": True,
        "source": "local",
        "reply": clean_markdown_text(localized_chat_response(message, language, symptom_result)),
        "translated_message": translated_message,
        "original_message": message,
        "level": "Moderate",
        "language": language,
    })


@app.route("/api/conversations", methods=["GET", "POST"])
def api_conversations():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]
    if request.method == "GET":
        member_id = active_family_member_id(user_id)
        conversations = [
            item for item in get_user_conversations(user_id)
            if item.get("member_id", "self") == member_id
        ]
        return jsonify({"conversations": sorted(conversations, key=lambda item: item.get("updated_at", ""), reverse=True)})

    payload = request.get_json() or {}
    conversation_id = payload.get("conversation_id") or str(uuid.uuid4())
    title = (payload.get("title") or "New conversation").strip() or "New conversation"
    messages = payload.get("messages") or []
    normalized_messages = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        normalized_messages.append({
            "role": message.get("role", "user"),
            "text": str(message.get("text", "")).strip(),
            "timestamp": message.get("timestamp") or datetime.now().isoformat(),
        })

    conversation = {
        "id": conversation_id,
        "member_id": active_family_member_id(user_id),
        "title": title,
        "updated_at": datetime.now().isoformat(),
        "messages": normalized_messages,
    }

    conversations = get_user_conversations(user_id)
    existing = [item for item in conversations if item.get("id") != conversation_id]
    existing.insert(0, conversation)
    save_user_conversations(user_id, existing)
    return jsonify({"success": True, "conversation": conversation})


@app.route("/api/conversations/<conversation_id>")
def api_conversation_detail(conversation_id):
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]
    member_id = active_family_member_id(user_id)
    conversation = next((
        item for item in get_user_conversations(user_id)
        if item.get("id") == conversation_id and item.get("member_id", "self") == member_id
    ), None)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify({"conversation": conversation})


@app.route("/api/report/ocr", methods=["POST"])
def api_report_ocr():
    data = request.get_json() or {}
    text = str(data.get("text", ""))
    result = report_ocr_text(text)
    if text.strip():
        save_family_record("report", {
            "title": "Lab report scan",
            "summary": f"{len(result['params'])} measurements reviewed",
            "params": result["params"],
            "raw_text": text[:500],
        })
    return jsonify(result)

@app.route("/api/translate")
def api_translate():
    lang = request.args.get("lang", "en")
    key = request.args.get("key", "home")
    translations = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return jsonify({"language": lang, "translations": translations, "key": key, "value": translations.get(key, key)})

@app.route("/api/languages")
def api_languages():
    return jsonify({
        "supported": [{"code": "en", "name": "English", "native": "English", "flag": "🇬🇧"}, *INDIAN_LANGUAGES, {"code": "es", "name": "Spanish", "native": "Español", "flag": "🇪🇸"}, {"code": "fr", "name": "French", "native": "Français", "flag": "🇫🇷"}],
        "coming_soon": [],
    })


# ── Care Hub feature APIs ────────────────────────────────────────────────────
@app.route("/api/checkin", methods=["GET", "POST"])
def api_checkin():
    if request.method == "POST":
        data = request.get_json() or {}
        checkin = {
            "mood": data.get("mood", "Good"),
            "energy": data.get("energy", "Moderate"),
            "symptoms": data.get("symptoms", "None reported"),
            "notes": data.get("notes", "").strip(),
            "date": datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "source": data.get("source", "online"),
        }
        session["latest_checkin"] = checkin
        save_family_record("checkin", {
            "title": "Health check-in",
            "summary": f"Mood: {checkin['mood']}; energy: {checkin['energy']}",
            "details": checkin,
        })
        return jsonify({"success": True, "checkin": checkin})
    return jsonify({"checkin": session.get("latest_checkin")})


@app.route("/api/offline/sync", methods=["POST"])
def api_offline_sync():
    data = request.get_json() or {}
    checkins = data.get("checkins") or []
    medicines = data.get("medicines") or []
    synced_checkins = []
    synced_medicines = []

    for item in checkins:
        payload = {
            "mood": item.get("mood", "Good"),
            "energy": item.get("energy", "Moderate"),
            "notes": (item.get("notes") or "").strip(),
            "date": item.get("savedAt") or datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "source": "offline-queue",
        }
        synced_checkins.append(payload)
        session["latest_checkin"] = payload
        save_family_record("checkin", {
            "title": "Offline health check-in",
            "summary": f"Mood: {payload['mood']}; energy: {payload['energy']}",
            "details": payload,
        })

    for item in medicines:
        synced_medicines.append({
            "id": item.get("id") or str(uuid.uuid4()),
            "member_id": active_family_member_id(session["user_id"]) if is_logged_in() else "self",
            "name": (item.get("name") or "Medicine").strip(),
            "dose": (item.get("dose") or "").strip(),
            "time": (item.get("time") or "").strip(),
            "frequency": (item.get("frequency") or "Once daily").strip(),
            "enabled": True,
            "source": "offline-queue",
        })

    if is_logged_in():
        owner_id = session["user_id"]
        member_id = active_family_member_id(owner_id)
        store = read_family_data()
        account = family_account(store, owner_id)
        existing = account["reminders"].setdefault(member_id, [])
        existing.extend(synced_medicines)
        write_family_data(store)
    else:
        existing = session.get("medicines", [])
        existing.extend(synced_medicines)
    session["medicines"] = existing

    return jsonify({
        "success": True,
        "synced": {
            "checkins": len(synced_checkins),
            "medicines": len(synced_medicines),
        },
        "message": "Queued offline entries were synced successfully.",
    })


@app.route("/api/medicines", methods=["GET", "POST", "DELETE"])
def api_medicines():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    owner_id = session["user_id"]
    member_id = active_family_member_id(owner_id)
    store = read_family_data()
    account = family_account(store, owner_id)
    reminders = account["reminders"]
    migrated_legacy = "self" not in reminders and bool(session.get("medicines"))
    if migrated_legacy:
        reminders["self"] = [
            {**item, "member_id": "self"} for item in session.get("medicines", [])
        ]
        write_family_data(store)
    medicines = reminders.get(member_id, [])
    if request.method == "POST":
        data = request.get_json() or {}
        name = str(data.get("name", "")).strip()
        dose = str(data.get("dose", "")).strip()
        time = str(data.get("time", "")).strip()
        frequency = str(data.get("frequency", "Once daily")).strip()
        if not name or not dose or not time:
            return jsonify({"success": False, "message": "Medicine, dose and time are required"}), 400
        reminder = {
            "id": str(uuid.uuid4()),
            "member_id": member_id,
            "name": name,
            "dose": dose,
            "time": time,
            "frequency": frequency,
            "enabled": True,
        }
        medicines.append(reminder)
        reminders[member_id] = medicines
        write_family_data(store)
        session["medicines"] = medicines
        return jsonify({"success": True, "medicine": reminder, "medicines": medicines})
    if request.method == "DELETE":
        medicine_id = (request.get_json() or {}).get("id")
        medicines = [item for item in medicines if item.get("id") != medicine_id]
        reminders[member_id] = medicines
        write_family_data(store)
        session["medicines"] = medicines
    session["medicines"] = medicines
    return jsonify({"medicines": medicines})


@app.route("/api/timeline")
def api_timeline():
    return jsonify({"events": [
        {"date": "Today", "type": "checkin", "title": "Daily health check-in", "detail": "Mood and energy recorded"},
        {"date": "05 Sep 2026", "type": "report", "title": "Blood report scanned", "detail": "Key parameters reviewed"},
        {"date": "03 Sep 2026", "type": "consultation", "title": "Follow-up reminder", "detail": "Review symptoms with your care team"},
        {"date": "01 Sep 2026", "type": "vitals", "title": "Vitals recorded", "detail": "Oxygen 97.5% and heart rate 72 bpm"},
    ]})


@app.route("/api/facilities")
def api_facilities():
    query = request.args.get("q", "nearby")
    facilities = [
        {"name": "Orbix Community Clinic", "type": "Primary Care", "distance": "1.2 km", "open": True, "phone": "+91 98765 43210"},
        {"name": "City General Hospital", "type": "Hospital & Emergency", "distance": "2.8 km", "open": True, "phone": "+91 91234 56789"},
        {"name": "Wellness Diagnostic Centre", "type": "Lab & Diagnostics", "distance": "3.5 km", "open": False, "phone": "+91 99887 66554"},
    ]
    return jsonify({"query": query, "facilities": facilities})


def normalize_medicine_name(value):
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


MEDICINE_AUTHORIZED_CATALOG = [
    {
        "name": "Paracetamol 500 mg",
        "identifier": "PARA-500-ALPHA-2026-1234",
        "batch": "ALPHA-2026",
        "manufacturer": "GovMed Pharma",
        "expiry": "2028-12-31",
        "authorized": True,
        "aliases": ["paracetamol", "paracetamol 500mg", "paracetamol 500 mg"],
    },
    {
        "name": "Amoxicillin 500 mg",
        "identifier": "AMOX-500-BETA-2026-7721",
        "batch": "BETA-2026",
        "manufacturer": "CarePlus Labs",
        "expiry": "2028-12-31",
        "authorized": True,
        "aliases": ["amoxicillin", "amoxicillin 500mg", "amoxicillin 500 mg"],
    },
]


def get_medicine_record(medicine_name):
    lookup = normalize_medicine_name(medicine_name)
    for record in MEDICINE_AUTHORIZED_CATALOG:
        if lookup in {normalize_medicine_name(alias) for alias in record.get("aliases", []) + [record.get("name", "")] }:
            return record
    return None


def get_medicine_availability_data(medicine_name):
    lookup = normalize_medicine_name(medicine_name)
    default_key = "paracetamol 500 mg"
    if lookup and lookup in {normalize_medicine_name(key) for key in ["amoxicillin 500 mg", "paracetamol 500 mg"]}:
        key = lookup
    else:
        key = default_key

    catalog = {
        "paracetamol 500 mg": [
            {"facility": "PHC", "status": "available", "availability": "Available", "distance": "1.4 km", "stock": "In stock"},
            {"facility": "Government Hospital", "status": "available", "availability": "Available", "distance": "3.2 km", "stock": "In stock"},
            {"facility": "Sub-centre", "status": "out_of_stock", "availability": "Out of stock", "distance": "1.1 km", "stock": "Not available"},
        ],
        "amoxicillin 500 mg": [
            {"facility": "PHC", "status": "available", "availability": "Available", "distance": "2.1 km", "stock": "In stock"},
            {"facility": "Government Hospital", "status": "low_stock", "availability": "Low stock", "distance": "4.4 km", "stock": "Limited"},
            {"facility": "Sub-centre", "status": "out_of_stock", "availability": "Out of stock", "distance": "1.6 km", "stock": "Not available"},
        ],
    }
    return catalog.get(key, catalog[default_key])


def parse_medicine_expiry(value):
    """Return an expiry date from YYYY-MM-DD, YYYY-MM, or MM/YYYY input."""
    if not value:
        return None
    text = str(value).strip()
    for pattern, formatter in [
        (r"^(\d{4})[-/]?(\d{2})[-/]?(\d{2})$", lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r"^(\d{4})[-/]?(\d{2})$", lambda m: (int(m.group(1)), int(m.group(2)), None)),
        (r"^(\d{2})[-/](\d{4})$", lambda m: (int(m.group(2)), int(m.group(1)), None)),
    ]:
        match = re.match(pattern, text)
        if match:
            try:
                year, month, day = formatter(match)
                if day is None:
                    day = monthrange(year, month)[1]
                return datetime(year, month, day).date()
            except ValueError:
                return None
    return None


def verify_medicine_record(medicine_name, identifier, batch=None, manufacturer=None, expiry=None):
    if not medicine_name or not identifier:
        return {
            "status": "unable_to_verify",
            "verified": False,
            "message": "Medicine name and QR/serial identifier are required for verification.",
        }

    record = get_medicine_record(medicine_name)
    if not record:
        return {
            "status": "unable_to_verify",
            "verified": False,
            "message": "This medicine could not be found in the authorised registry. Please confirm the product details or consult a pharmacist.",
        }

    identifier_match = str(record.get("identifier", "")).strip().upper() == str(identifier).strip().upper()
    batch_match = not batch or str(record.get("batch", "")).strip().upper() == str(batch).strip().upper()
    manufacturer_match = not manufacturer or str(record.get("manufacturer", "")).strip().upper() == str(manufacturer).strip().upper()
    supplied_expiry = parse_medicine_expiry(expiry)
    catalog_expiry = parse_medicine_expiry(record.get("expiry"))
    if expiry and not supplied_expiry:
        return {"status": "unable_to_verify", "verified": False, "message": "Expiry must be in MM/YYYY, YYYY-MM, or YYYY-MM-DD format."}
    if supplied_expiry and supplied_expiry < datetime.now().date():
        return {"status": "expired", "verified": False, "message": "Expired — do not use this medicine. Dispose of it safely and contact a pharmacist.", "medicine": record.get("name"), "expiry": expiry}
    expiry_match = not supplied_expiry or not catalog_expiry or supplied_expiry == catalog_expiry

    if record.get("authorized") is True and identifier_match and batch_match and manufacturer_match and expiry_match:
        return {
            "status": "verified",
            "verified": True,
            "message": "Verified — record matches the authorised database and passed identity checks.",
            "medicine": record.get("name"),
            "batch": record.get("batch"),
            "manufacturer": record.get("manufacturer"),
            "identifier": record.get("identifier"),
            "expiry": expiry or record.get("expiry"),
        }

    if record.get("authorized") is True and identifier_match:
        return {
            "status": "failed",
            "verified": False,
            "message": "Verification failed — the medicine identifier matches but the batch/manufacturer details do not align with the trusted registry.",
            "medicine": record.get("name"),
            "expiry": expiry or record.get("expiry"),
        }

    return {
        "status": "failed",
        "verified": False,
        "message": "Verification failed — this medicine is not recognised by the authorised database. Please verify with a pharmacist or licensed healthcare professional before use.",
        "medicine": record.get("name"),
    }


@app.route("/api/medicine/verify", methods=["POST"])
def api_medicine_verify():
    payload = request.get_json() or {}
    result = verify_medicine_record(
        payload.get("medicine", ""),
        payload.get("identifier", ""),
        payload.get("batch"),
        payload.get("manufacturer"),
        payload.get("expiry"),
    )
    return jsonify(result)


@app.route("/api/medicine/availability")
def api_medicine_availability():
    medicine_name = request.args.get("medicine", "Paracetamol 500 mg").strip() or "Paracetamol 500 mg"
    facilities = get_medicine_availability_data(medicine_name)
    return jsonify({
        "medicine": medicine_name,
        "facilities": [
            {
                "facility": item.get("facility"),
                "status": item.get("status"),
                "availability": item.get("availability"),
                "distance": item.get("distance"),
                "stock": item.get("stock"),
            }
            for item in facilities
        ],
    })


def fetch_json(url, params=None, timeout=10, extra_headers=None):
    if params:
        url = f"{url}?{params}"
    headers = {"User-Agent": OSM_USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def search_geoapify_doctors(query, specialty="all"):
    if not GEOAPIFY_API_KEY:
        return []
    try:
        search_query = query.strip()
        if not search_query:
            return []
        geocode_url = "https://api.geoapify.com/v1/geocode/search"
        geocode_params = f"text={quote(search_query)}&format=json&apiKey={GEOAPIFY_API_KEY}"
        geocode = fetch_json(geocode_url, params=geocode_params, timeout=15)
        results = geocode.get("results", [])
        if not results:
            return []
        center = results[0]
        lat = center.get("lat")
        lon = center.get("lon")
        if lat is None or lon is None:
            return []

        places_url = "https://api.geoapify.com/v2/places"
        place_params = (
            f"categories=healthcare.clinic,healthcare.doctor,healthcare.hospital,"
            f"healthcare.pharmacy&filter=circle:{lon},{lat},7000&limit=10&apiKey={GEOAPIFY_API_KEY}"
        )
        places = fetch_json(places_url, params=place_params, timeout=20)
        doctors = []
        for feature in places.get("features", [])[:10]:
            props = feature.get("properties", {})
            name = props.get("name") or props.get("formatted") or "Healthcare provider"
            if not name:
                continue
            categories = props.get("categories", ["healthcare"])
            searchable = f"{name} {' '.join(categories)}".lower()
            if specialty != "all" and specialty not in searchable:
                continue
            coords = feature.get("geometry", {}).get("coordinates", [lon, lat])
            if len(coords) >= 2:
                lon2, lat2 = coords[0], coords[1]
            else:
                lon2, lat2 = lon, lat
            doctors.append({
                "name": name,
                "specialty": categories[0].replace("healthcare.", "").replace("_", " ").title() if categories else "Medical centre",
                "facility": name,
                "city": query.strip(),
                "area": query.strip(),
                "address": props.get("formatted") or props.get("address_line1") or query.strip(),
                "phone": props.get("phone") or "Phone not listed",
                "hours": props.get("opening_hours") or "Hours not listed",
                "fee": "Contact provider",
                "available": True,
                "distance": "Nearby",
                "distance_km": 0.0,
                "latitude": lat2,
                "longitude": lon2,
            })
        return doctors
    except Exception:
        app.logger.exception("Geoapify doctor search failed for %s", query)
        return []


def get_doctor_directory():
    return [
        {
            "name": "Dr. Meera Nayak",
            "specialty": "General Physician",
            "facility": "Patia Government Primary Health Centre",
            "city": "Bhubaneswar",
            "area": "Patia",
            "address": "Patia Government Primary Health Centre, Bhubaneswar, Odisha",
            "phone": "+91 674 239 1122",
            "hours": "24x7 emergency desk",
            "fee": "Government facility",
            "available": True,
            "distance": "1.8 km",
            "distance_km": 1.8,
            "latitude": 20.3550,
            "longitude": 85.8180,
            "experience_years": 12,
            "verified": True,
            "emergency_capable": True,
            "open_24x7": True,
            "trust_score": 4.7,
        },
        {
            "name": "Dr. Suresh Das",
            "specialty": "General Physician",
            "facility": "Bhubaneswar District Government Hospital",
            "city": "Bhubaneswar",
            "area": "Old Town",
            "address": "District Government Hospital, Old Town, Bhubaneswar, Odisha",
            "phone": "+91 674 243 0011",
            "hours": "24x7 emergency and ambulance",
            "fee": "Government facility",
            "available": True,
            "distance": "5.4 km",
            "distance_km": 5.4,
            "latitude": 20.2485,
            "longitude": 85.8330,
            "experience_years": 18,
            "verified": True,
            "emergency_capable": True,
            "open_24x7": True,
            "trust_score": 4.9,
        },
        {
            "name": "Dr. Ananya Sharma",
            "specialty": "General Physician",
            "facility": "Orbix Community Clinic",
            "city": "Bhubaneswar",
            "area": "Patia",
            "address": "Plot 18, Patia Main Road, Patia, Bhubaneswar, Odisha 751024",
            "phone": "+91 98765 43210",
            "hours": "9:00 AM - 2:00 PM",
            "fee": "₹500",
            "available": True,
            "distance": "1.2 km",
            "distance_km": 1.2,
            "latitude": 20.2937,
            "longitude": 85.8249,
        },
        {
            "name": "Dr. Rakesh Kumar",
            "specialty": "Cardiologist",
            "facility": "City General Hospital",
            "city": "Bhubaneswar",
            "area": "Saheed Nagar",
            "address": "45 Janpath, Saheed Nagar, Bhubaneswar, Odisha 751007",
            "phone": "+91 91234 56789",
            "hours": "10:00 AM - 4:00 PM",
            "fee": "₹800",
            "available": True,
            "distance": "2.8 km",
            "distance_km": 2.8,
            "latitude": 20.2860,
            "longitude": 85.8320,
        },
        {
            "name": "Dr. Priya Mohanty",
            "specialty": "Paediatrician",
            "facility": "Mother & Child Care",
            "city": "Bhubaneswar",
            "area": "Khandagiri",
            "address": "Khandagiri Square, NH16, Bhubaneswar, Odisha 751030",
            "phone": "+91 97777 12345",
            "hours": "4:00 PM - 8:00 PM",
            "fee": "₹600",
            "available": True,
            "distance": "4.1 km",
            "distance_km": 4.1,
            "latitude": 20.2872,
            "longitude": 85.8040,
        },
        {
            "name": "Dr. Meera Das",
            "specialty": "Nutritionist",
            "facility": "Wellness Medical Centre",
            "city": "Cuttack",
            "area": "CDA Sector 6",
            "address": "CDA Sector 6 Market Complex, Cuttack, Odisha 753014",
            "phone": "+91 99887 66554",
            "hours": "11:00 AM - 6:00 PM",
            "fee": "₹400",
            "available": False,
            "distance": "3.5 km",
            "distance_km": 3.5,
            "latitude": 20.4667,
            "longitude": 85.8820,
        },
        {
            "name": "Dr. Aarav Mehta",
            "specialty": "General Physician",
            "facility": "Arogya Care Centre",
            "city": "Bhubaneswar",
            "area": "Old Town",
            "address": "12 Kharvela Nagar, Old Town, Bhubaneswar, Odisha 751002",
            "phone": "+91 98111 22001",
            "hours": "9:00 AM - 5:00 PM",
            "fee": "₹700",
            "available": True,
            "distance": "2.0 km",
            "distance_km": 2.0,
            "latitude": 20.2472,
            "longitude": 85.8442,
        },
        {
            "name": "Dr. Kavya Iyer",
            "specialty": "Cardiologist",
            "facility": "Heartline Cardiac Clinic",
            "city": "Bhubaneswar",
            "area": "Rasulgarh",
            "address": "3rd Floor, Rasulgarh Square, Bhubaneswar, Odisha 751010",
            "phone": "+91 98222 33002",
            "hours": "10:00 AM - 6:00 PM",
            "fee": "₹900",
            "available": True,
            "distance": "2.4 km",
            "distance_km": 2.4,
            "latitude": 20.3118,
            "longitude": 85.8277,
        },
        {
            "name": "Dr. Arjun Verma",
            "specialty": "Paediatrician",
            "facility": "New Life Children Hospital",
            "city": "Bhubaneswar",
            "area": "Chandrasekharpur",
            "address": "22 CRP Road, Chandrasekharpur, Bhubaneswar, Odisha 751016",
            "phone": "+91 98333 44003",
            "hours": "8:30 AM - 3:00 PM",
            "fee": "₹650",
            "available": True,
            "distance": "1.8 km",
            "distance_km": 1.8,
            "latitude": 20.3381,
            "longitude": 85.7886,
        },
        {
            "name": "Dr. Ishita Roy",
            "specialty": "Nutritionist",
            "facility": "Healthy Living Clinic",
            "city": "Bhubaneswar",
            "area": "Unit 3",
            "address": "10 Unit-3 Market, Bhubaneswar, Odisha 751001",
            "phone": "+91 98444 55004",
            "hours": "11:00 AM - 7:00 PM",
            "fee": "₹450",
            "available": False,
            "distance": "3.1 km",
            "distance_km": 3.1,
            "latitude": 20.2585,
            "longitude": 85.8415,
        },
        {
            "name": "Dr. Neel Shah",
            "specialty": "General Physician",
            "facility": "Sunrise Multispecialty Clinic",
            "city": "Bhubaneswar",
            "area": "Airport Road",
            "address": "18 Airport Road, Bhubaneswar, Odisha 751020",
            "phone": "+91 98555 66005",
            "hours": "9:00 AM - 4:00 PM",
            "fee": "₹500",
            "available": True,
            "distance": "2.6 km",
            "distance_km": 2.6,
            "latitude": 20.2547,
            "longitude": 85.8177,
        },
        {
            "name": "Dr. Sushmita Rao",
            "specialty": "General Physician",
            "facility": "Nayapalli Family Clinic",
            "city": "Bhubaneswar",
            "area": "Nayapalli",
            "address": "Nayapalli Main Road, Bhubaneswar, Odisha 751012",
            "phone": "+91 98666 77006",
            "hours": "8:00 AM - 1:00 PM",
            "fee": "₹450",
            "available": True,
            "distance": "2.2 km",
            "distance_km": 2.2,
            "latitude": 20.2864,
            "longitude": 85.8046,
        },
        {
            "name": "Dr. Vikram Patnaik",
            "specialty": "Cardiologist",
            "facility": "Heart Care Hospital",
            "city": "Bhubaneswar",
            "area": "Baramunda",
            "address": "NH16 Service Road, Baramunda, Bhubaneswar, Odisha 751003",
            "phone": "+91 98770 88007",
            "hours": "9:30 AM - 5:30 PM",
            "fee": "₹900",
            "available": True,
            "distance": "3.7 km",
            "distance_km": 3.7,
            "latitude": 20.2755,
            "longitude": 85.8031,
        },
        {
            "name": "Dr. Ritu Mishra",
            "specialty": "Paediatrician",
            "facility": "Little Stars Children Clinic",
            "city": "Bhubaneswar",
            "area": "Mancheswar",
            "address": "Industrial Estate Road, Mancheswar, Bhubaneswar, Odisha 751010",
            "phone": "+91 98881 99008",
            "hours": "4:30 PM - 8:30 PM",
            "fee": "₹550",
            "available": True,
            "distance": "3.9 km",
            "distance_km": 3.9,
            "latitude": 20.3284,
            "longitude": 85.8511,
        },
        {
            "name": "Dr. Tanmay Das",
            "specialty": "General Physician",
            "facility": "CDA Health Point",
            "city": "Cuttack",
            "area": "CDA Sector 9",
            "address": "CDA Sector 9, Cuttack, Odisha 753014",
            "phone": "+91 98992 11009",
            "hours": "8:30 AM - 2:30 PM",
            "fee": "₹400",
            "available": True,
            "distance": "2.1 km",
            "distance_km": 2.1,
            "latitude": 20.4746,
            "longitude": 85.8621,
        },
        {
            "name": "Dr. Nandini Mohapatra",
            "specialty": "Paediatrician",
            "facility": "Puri Child Wellness Centre",
            "city": "Puri",
            "area": "Grand Road",
            "address": "Grand Road, Puri, Odisha 752001",
            "phone": "+91 99003 22010",
            "hours": "10:00 AM - 4:00 PM",
            "fee": "₹500",
            "available": True,
            "distance": "1.6 km",
            "distance_km": 1.6,
            "latitude": 19.8050,
            "longitude": 85.8170,
        },
        {
            "name": "Dr. Abhishek Sahu",
            "specialty": "General Physician",
            "facility": "Rourkela Community Hospital",
            "city": "Rourkela",
            "area": "Civil Township",
            "address": "Civil Township Main Road, Rourkela, Odisha 769004",
            "phone": "+91 99114 33011",
            "hours": "9:00 AM - 3:00 PM",
            "fee": "₹450",
            "available": True,
            "distance": "2.4 km",
            "distance_km": 2.4,
            "latitude": 22.2380,
            "longitude": 84.8530,
        },
        {
            "name": "Dr. Padmini Pradhan",
            "specialty": "Nutritionist",
            "facility": "Sambalpur Wellness Centre",
            "city": "Sambalpur",
            "area": "Ainthapali",
            "address": "Ainthapali Main Road, Sambalpur, Odisha 768004",
            "phone": "+91 99225 44012",
            "hours": "11:00 AM - 6:00 PM",
            "fee": "₹400",
            "available": True,
            "distance": "2.9 km",
            "distance_km": 2.9,
            "latitude": 21.4710,
            "longitude": 83.9750,
        },
        {
            "name": "Dr. Kunal Behera",
            "specialty": "Cardiologist",
            "facility": "Berhampur Heart Clinic",
            "city": "Berhampur",
            "area": "Gandhi Nagar",
            "address": "Gandhi Nagar, Berhampur, Odisha 760001",
            "phone": "+91 99336 55013",
            "hours": "10:00 AM - 5:00 PM",
            "fee": "₹750",
            "available": False,
            "distance": "3.2 km",
            "distance_km": 3.2,
            "latitude": 19.3149,
            "longitude": 84.7941,
        },
        {
            "name": "Dr. Sneha Mishra",
            "specialty": "Obstetrician & Gynecologist",
            "facility": "Sakhi Community Women's Clinic",
            "city": "Bhubaneswar",
            "area": "Patia",
            "address": "Patia Main Road, Bhubaneswar, Odisha",
            "phone": "Phone not listed",
            "hours": "By appointment",
            "fee": "Contact facility",
            "available": True,
            "distance": "Nearby",
            "distance_km": 2.1,
            "latitude": 20.3550,
            "longitude": 85.8180,
            "experience_years": 8,
            "verified": False,
            "emergency_capable": False,
            "open_24x7": False,
            "trust_score": 4.3,
        },
        {
            "name": "Dr. Kabir Mishra",
            "specialty": "Dermatologist",
            "facility": "Coastal Skin Health Centre",
            "city": "Cuttack",
            "area": "CDA Sector 6",
            "address": "CDA Sector 6, Cuttack, Odisha",
            "phone": "Phone not listed",
            "hours": "By appointment",
            "fee": "Contact facility",
            "available": True,
            "distance": "Nearby",
            "distance_km": 2.7,
            "latitude": 20.4667,
            "longitude": 85.8820,
            "experience_years": 11,
            "verified": False,
            "emergency_capable": False,
            "open_24x7": False,
            "trust_score": 4.4,
        },
        {
            "name": "Dr. Niharika Patra",
            "specialty": "Orthopaedic Surgeon",
            "facility": "Kalinga Bone & Joint Clinic",
            "city": "Rourkela",
            "area": "Civil Township",
            "address": "Civil Township Main Road, Rourkela, Odisha",
            "phone": "Phone not listed",
            "hours": "By appointment",
            "fee": "Contact facility",
            "available": False,
            "distance": "Nearby",
            "distance_km": 3.0,
            "latitude": 22.2380,
            "longitude": 84.8530,
            "experience_years": 14,
            "verified": False,
            "emergency_capable": False,
            "open_24x7": False,
            "trust_score": 4.5,
        },
        {
            "name": "Dr. Devraj Sahoo",
            "specialty": "Ophthalmologist",
            "facility": "Netra Community Eye Centre",
            "city": "Sambalpur",
            "area": "Ainthapali",
            "address": "Ainthapali Main Road, Sambalpur, Odisha",
            "phone": "Phone not listed",
            "hours": "By appointment",
            "fee": "Contact facility",
            "available": True,
            "distance": "Nearby",
            "distance_km": 2.5,
            "latitude": 21.4710,
            "longitude": 83.9750,
            "experience_years": 16,
            "verified": False,
            "emergency_capable": False,
            "open_24x7": False,
            "trust_score": 4.6,
        },
        {
            "name": "Dr. Farah Khan",
            "specialty": "ENT Specialist",
            "facility": "Swasthya ENT Clinic",
            "city": "Berhampur",
            "area": "Gandhi Nagar",
            "address": "Gandhi Nagar, Berhampur, Odisha",
            "phone": "Phone not listed",
            "hours": "By appointment",
            "fee": "Contact facility",
            "available": True,
            "distance": "Nearby",
            "distance_km": 3.1,
            "latitude": 19.3149,
            "longitude": 84.7941,
            "experience_years": 6,
            "verified": False,
            "emergency_capable": False,
            "open_24x7": False,
            "trust_score": 4.2,
        },
    ]


def _doctor_matches_query(doctor, query):
    if not query:
        return True
    query = query.lower()
    searchable_values = [
        doctor.get("name", ""),
        doctor.get("specialty", ""),
        doctor.get("facility", ""),
        doctor.get("city", ""),
        doctor.get("area", ""),
        doctor.get("address", ""),
    ]
    return any(query in value.lower() for value in searchable_values)


def _doctor_location(doctor):
    """Return one complete location string without repeating address parts."""
    address = (doctor.get("address") or "").strip()
    address_lower = address.lower()
    parts = [address] if address else []
    for value in (doctor.get("area"), doctor.get("city"), doctor.get("state"), doctor.get("pincode")):
        value = str(value or "").strip()
        if value and value.lower() not in address_lower:
            parts.append(value)
    return ", ".join(parts) or "Location not listed"


def _with_doctor_locations(doctors):
    for doctor in doctors:
        doctor["location"] = _doctor_location(doctor)
        facility_text = f"{doctor.get('facility', '')} {doctor.get('name', '')}".lower()
        is_government = any(word in facility_text for word in ("government", "govt", "phc", "community health", "district hospital"))
        doctor.setdefault("facility_type", "Government" if is_government else "Private")
        doctor.setdefault("experience_years", 8)
        doctor.setdefault("verified", True)
        doctor.setdefault("emergency_capable", "hospital" in facility_text or "phc" in facility_text or "emergency" in facility_text)
        doctor.setdefault("open_24x7", "hospital" in facility_text or "phc" in facility_text)
        doctor.setdefault("trust_score", 4.5 if doctor.get("verified") else 3.5)
    return doctors


def recommend_doctors(query, specialty="all", facility_type="all", emergency=False):
    """Rank nearby providers for emergency readiness, trust, specialty, and distance."""
    doctors = _with_doctor_locations(get_doctor_directory())
    matches = [doctor for doctor in doctors if _doctor_matches_query(doctor, query)]
    if not matches:
        matches = _with_doctor_locations(search_openstreetmap_doctors(query, specialty))
    if specialty != "all":
        matches = [doctor for doctor in matches if specialty in doctor.get("specialty", "").lower()]
    if facility_type != "all":
        matches = [doctor for doctor in matches if doctor.get("facility_type", "").lower() == facility_type]

    def score(doctor):
        distance = float(doctor.get("distance_km", 99) or 99)
        value = (10 - min(distance, 10)) + float(doctor.get("trust_score", 0))
        value += min(int(doctor.get("experience_years", 0) or 0), 20) * 0.25
        if doctor.get("verified"):
            value += 4
        if emergency:
            value += 20 if doctor.get("emergency_capable") else -10
            value += 8 if doctor.get("open_24x7") else -4
        return value

    for doctor in matches:
        doctor["recommendation_score"] = round(score(doctor), 2)
        doctor["recommendation_reason"] = (
            "Emergency-ready and available 24x7" if emergency and doctor.get("emergency_capable") and doctor.get("open_24x7")
            else "Verified specialist with strong experience" if doctor.get("verified")
            else "Nearby healthcare provider"
        )
    return sorted(matches, key=lambda doctor: doctor.get("recommendation_score", 0), reverse=True)[:20]


def search_medical_api_doctors(query, specialty="all"):
    if not MEDICAL_API_KEY:
        return []
    try:
        payload = {
            "query": query.strip(),
            "specialty": specialty,
            "api_key": MEDICAL_API_KEY,
        }
        response = fetch_json(
            "https://api.example-medical.com/search",
            params=f"q={quote(payload['query'])}&specialty={quote(payload['specialty'])}&api_key={quote(payload['api_key'])}",
            timeout=15,
        )
        if not isinstance(response, dict):
            return []
        results = response.get("doctors") or response.get("providers") or response.get("results") or []
        normalized = []
        for item in results:
            normalized.append({
                "name": item.get("name") or item.get("doctor_name") or "Healthcare provider",
                "specialty": item.get("specialty") or item.get("specialization") or "Medical centre",
                "facility": item.get("facility") or item.get("clinic") or item.get("name") or "Healthcare provider",
                "city": item.get("city") or query.strip(),
                "area": item.get("area") or item.get("locality") or query.strip(),
                "address": item.get("address") or item.get("full_address") or query.strip(),
                "phone": item.get("phone") or item.get("contact") or "Phone not listed",
                "hours": item.get("hours") or item.get("timing") or "Hours not listed",
                "fee": item.get("fee") or "Contact provider",
                "available": item.get("available", True),
                "distance": item.get("distance") or "Nearby",
                "distance_km": float(item.get("distance_km", 0.0) or 0.0),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
            })
        return normalized
    except Exception:
        app.logger.exception("Medical API doctor search failed for %s", query)
        return []


def search_openstreetmap_doctors(query, specialty="all"):
    """Find real nearby healthcare places through public OpenStreetMap data and optional API-key providers."""
    try:
        if MEDICAL_API_KEY:
            medical_results = search_medical_api_doctors(query, specialty)
            if medical_results:
                return medical_results

        if GEOAPIFY_API_KEY:
            geoapify_results = search_geoapify_doctors(query, specialty)
            if geoapify_results:
                return geoapify_results

        locations = fetch_json(
            "https://nominatim.openstreetmap.org/search",
            f"q={quote(query)}&format=jsonv2&limit=1&addressdetails=1" + (f"&email={quote(NOMINATIM_EMAIL)}" if NOMINATIM_EMAIL else ""),
        )
        if not locations:
            return []
        location = locations[0]
        lat, lon = location["lat"], location["lon"]
        overpass_query = f"""
[out:json][timeout:15];
(
  nwr(around:7000,{lat},{lon})[amenity~"clinic|doctors|hospital|pharmacy"];
  nwr(around:7000,{lat},{lon})[healthcare~"doctor|clinic|hospital|centre|pharmacy"];
);
out center tags;
"""
        payload = "data=" + quote(overpass_query)
        places = fetch_json("https://overpass-api.de/api/interpreter", payload, timeout=20).get("elements", [])
        results = []
        seen = set()
        for place in places:
            tags = place.get("tags", {})
            name = tags.get("name") or tags.get("official_name")
            if not name or name.lower() in seen:
                continue
            place_type = tags.get("healthcare") or tags.get("amenity") or "Medical centre"
            searchable = f"{name} {place_type} {tags.get('healthcare:speciality', '')}".lower()
            if specialty != "all" and specialty not in searchable:
                continue
            centre = place.get("center", {})
            address = ", ".join(value for key in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city") if (value := tags.get(key)))
            results.append({
                "name": name,
                "specialty": tags.get("healthcare:speciality", place_type.replace("_", " ").title()),
                "facility": name,
                "area": location.get("display_name", query),
                "address": address or tags.get("addr:full") or location.get("display_name", query),
                "phone": tags.get("phone") or tags.get("contact:phone") or "Phone not listed",
                "hours": tags.get("opening_hours", "Hours not listed"),
                "fee": "Contact provider",
                "available": True,
                "distance": "Within 7 km",
                "distance_km": 7.0,
                "website": tags.get("website") or tags.get("contact:website", ""),
                "latitude": centre.get("lat", place.get("lat")),
                "longitude": centre.get("lon", place.get("lon")),
            })
            seen.add(name.lower())
            if len(results) >= 20:
                break
        return results
    except Exception:
        app.logger.exception("Remote healthcare search failed for %s", query)
        return []


@app.route("/api/doctors")
def api_doctors():
    query = request.args.get("q", "").strip()
    specialty = request.args.get("specialty", "all").strip().lower()
    if not query:
        return jsonify({
            "query": "",
            "specialty": specialty,
            "doctors": [],
            "message": "Enter an area or city to search for doctors.",
        }), 400

    doctors = get_doctor_directory()

    if query:
        matches = [doctor for doctor in doctors if _doctor_matches_query(doctor, query)]
        if matches:
            doctors = matches
        else:
            remote_doctors = search_openstreetmap_doctors(query, specialty)
            if remote_doctors:
                return jsonify({"query": query, "specialty": specialty, "source": "OpenStreetMap", "doctors": _with_doctor_locations(remote_doctors)})

    if specialty != "all":
        doctors = [doctor for doctor in doctors if specialty in doctor["specialty"].lower()]

    doctors = sorted(doctors, key=lambda d: float(d.get("distance_km", 99)))

    if not doctors:
        return jsonify({"query": query, "specialty": specialty, "doctors": []})

    return jsonify({"query": query, "specialty": specialty, "doctors": _with_doctor_locations(doctors)})


@app.route("/api/consult-doctors")
def api_consult_doctors():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    doctors = get_doctor_directory()
    consult_doctors = []
    for doctor in doctors:
        doctor_id = re.sub(r"[^a-z0-9]+", "-", doctor["name"].casefold()).strip("-")
        consult_doctors.append({
            "id": doctor_id,
            "name": doctor["name"],
            "specialty": doctor["specialty"],
            "facility": doctor["facility"],
            "city": doctor["city"],
            "area": doctor["area"],
            "available": bool(doctor.get("available")),
            "experience_years": doctor.get("experience_years"),
            "verified": bool(doctor.get("verified")),
        })
    return jsonify({
        "doctors": consult_doctors,
        "specialties": sorted({doctor["specialty"] for doctor in consult_doctors}),
        "directory_is_demo_data": True,
    })


@app.route("/api/doctor-recommendations")
def api_doctor_recommendations():
    query = request.args.get("q", "").strip()
    specialty = request.args.get("specialty", "all").strip().lower()
    facility_type = request.args.get("facility_type", "all").strip().lower()
    emergency = request.args.get("emergency", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not query:
        return jsonify({"recommendations": [], "message": "Enter an area or city first."}), 400
    recommendations = recommend_doctors(query, specialty, facility_type, emergency)
    return jsonify({
        "query": query,
        "specialty": specialty,
        "facility_type": facility_type,
        "emergency": emergency,
        "recommendations": recommendations,
        "message": "For severe symptoms, call local emergency services immediately." if emergency else "",
    })


def default_asha_data():
    return {
        "worker": {"name": "Kiran Kumari", "area": "Ward 12 Community Health", "status": "Online"},
        "stats": {"assigned": 52, "urgent": 4, "followups": 8, "completed": 35},
        "patients": [
            {"id": "P-101", "name": "Rahul Kumar", "condition": "Post-natal follow-up", "status": "Urgent", "last": "Today", "priority": "High", "note": "Needs same-day check on blood pressure and rest."},
            {"id": "P-102", "name": "Sita Devi", "condition": "Diabetes check-in", "status": "Follow-up", "last": "Yesterday", "priority": "Medium", "note": "Medication adherence review scheduled."},
            {"id": "P-103", "name": "Om Prasad Behera", "condition": "Blood pressure monitoring", "status": "Stable", "last": "05 Sep", "priority": "Low", "note": "No urgent symptoms reported."},
        ],
        "updated_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }


def default_asha_workers():
    return [
        {
            "id": "ASHA-001", "name": "Kiran Kumari", "area": "Ward 12 Community Health",
            "phone": "+91 98765 43210", "status": "Available", "languages": ["Hindi", "Odia", "English"],
            "services": ["Home visits", "Maternal care", "Medicine follow-up"],
            "schedule": "Mon-Sat, 8:00 AM - 4:00 PM", "experience": "8 years", "last_seen": "Online now",
        },
        {
            "id": "ASHA-002", "name": "Sabitri Behera", "area": "Patia and Chandrasekharpur",
            "phone": "+91 98765 43211", "status": "Available", "languages": ["Odia", "Hindi"],
            "services": ["Newborn care", "Immunization", "Home visits"],
            "schedule": "Mon-Fri, 9:00 AM - 5:00 PM", "experience": "6 years", "last_seen": "Online now",
        },
        {
            "id": "ASHA-003", "name": "Mamata Das", "area": "Khandagiri and Old Town",
            "phone": "+91 98765 43212", "status": "Available", "languages": ["Odia", "English"],
            "services": ["Chronic care", "Blood pressure checks", "Care coordination"],
            "schedule": "Tue-Sun, 8:30 AM - 3:30 PM", "experience": "10 years", "last_seen": "Online now",
        },
        {
            "id": "ASHA-004", "name": "Anita Naik", "area": "Cuttack Road and Rasulgarh",
            "phone": "+91 98765 43213", "status": "On visit", "languages": ["Odia", "Hindi", "English"],
            "services": ["Home visits", "Nutrition counselling", "Care coordination"],
            "schedule": "Mon-Sat, 10:00 AM - 6:00 PM", "experience": "5 years", "last_seen": "On a patient visit",
        },
    ]


@app.route("/api/asha/workers")
def api_asha_workers():
    query = " ".join((request.args.get("q") or "").lower().split())
    workers = default_asha_workers()
    if query:
        workers = [
            worker for worker in workers
            if query in worker["area"].lower() or query in worker["name"].lower()
        ]
    available = [worker for worker in workers if worker["status"] == "Available"]
    return jsonify({
        "success": True,
        "query": query,
        "workers": available,
        "total": len(available),
        "message": "Available ASHA workers found." if available else "No available ASHA worker found for this area.",
    })


@app.route("/api/asha")
def api_asha():
    data = session.get("asha_data")
    if not data:
        data = default_asha_data()
        session["asha_data"] = data
    return jsonify(data)


@app.route("/api/asha/patients/<patient_id>", methods=["PATCH", "PUT"])
def api_asha_patient_update(patient_id):
    data = session.get("asha_data") or default_asha_data()
    patient = next((item for item in data["patients"] if item.get("id") == patient_id), None)
    if not patient:
        return jsonify({"success": False, "message": f"Patient {patient_id} not found."}), 404

    payload = request.get_json() or {}
    if "status" in payload:
        status = (payload.get("status") or "").strip()
        if status not in {"Urgent", "Follow-up", "Stable", "Completed"}:
            return jsonify({"success": False, "message": "Unsupported patient status."}), 400
        patient["status"] = status
    if "note" in payload:
        patient["note"] = (payload.get("note") or "").strip()[:500]
    if "priority" in payload:
        priority = (payload.get("priority") or "").strip()
        if priority not in {"High", "Medium", "Low"}:
            return jsonify({"success": False, "message": "Unsupported patient priority."}), 400
        patient["priority"] = priority
    if "last" in payload:
        patient["last"] = (payload.get("last") or "").strip()[:40] or patient["last"]

    data["stats"]["urgent"] = sum(item.get("status") == "Urgent" for item in data["patients"])
    data["stats"]["followups"] = sum(item.get("status") == "Follow-up" for item in data["patients"])
    data["stats"]["completed"] = max(data["stats"].get("completed", 0), sum(item.get("status") == "Completed" for item in data["patients"]))
    data["updated_at"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
    session["asha_data"] = data
    return jsonify({"success": True, "patient": patient, "updated_at": data["updated_at"]})


TOLLFREE_MESSAGES = {
    "en": {
        "normal": "Thank you for calling 1800-ORBIX-HEALTH. Please drink water, rest, and monitor your symptoms. If you have fever, high temperature, worsening weakness, or other concerning signs, contact a health worker or nearby clinic.",
        "emergency": "Emergency symptoms detected. Please call 112 immediately or go to the nearest hospital without delay."
    },
    "hi": {
        "normal": "ArogyaX Health से कॉल करने के लिए धन्यवाद। कृपया पानी पिएँ, आराम करें और अपने लक्षणों पर ध्यान रखें। अगर स्थिति बिगड़े तो नज़दीकी क्लिनिक या स्वास्थ्य कर्मी से संपर्क करें।",
        "emergency": "आपके लक्षणों से आपातकालीन स्थिति का संकेत मिल रहा है। कृपया तुरंत 112 पर कॉल करें या निकटतम अस्पताल जाएँ।"
    },
    "or": {
        "normal": "ArogyaX Health-କୁ କଲ୍ କରିଥିବାରୁ ଧନ୍ୟବାଦ। ଦୟାକରି ପାଣି ପିଅନ୍ତୁ, ଆରାମ କରନ୍ତୁ, ଏବଂ ନିଜର ଲକ୍ଷଣଗୁଡ଼ିକୁ ତଦାର୍ଥ କରନ୍ତୁ। ଯଦି ଅବସ୍ଥା ଖରାପ ହୁଏ, ନିକଟସ୍ଥ କ୍ଲିନିକ୍ କିମ୍ବା ସ୍ୱାସ୍ଥ୍ୟ କର୍ମୀଙ୍କୁ ସମ୍ପର୍କ କରନ୍ତୁ।",
        "emergency": "ଜରୁରୀ ଅବସ୍ଥା ଚିହ୍ନିତ ହୋଇଛି। ଦୟାକରି ତୁରନ୍ତ 112 କୁ କଲ୍ କରନ୍ତୁ କିମ୍ବା ନିକଟସ୍ଥ ହସପିତାଳକୁ ଯାଆନ୍ତୁ।"
    },
    "es": {
        "normal": "Gracias por llamar a 1800-ORBIX-HEALTH. Tome agua, descanse y vigile sus síntomas. Si empeoran, contacte a un centro de salud cercano.",
        "emergency": "Se detectaron síntomas de emergencia. Llame al 112 de inmediato o vaya al hospital más cercano sin demora."
    },
    "fr": {
        "normal": "Merci d'avoir appelé 1800-ORBIX-HEALTH. Buvez de l'eau, reposez-vous et surveillez vos symptômes. Si votre état s'aggrave, contactez un centre de santé proche.",
        "emergency": "Des symptômes urgents ont été détectés. Appelez immédiatement le 112 ou rendez-vous au plus proche hôpital sans délai."
    }
}


PHONE_IVR_MESSAGES = {
    "en": {
        "welcome": "Welcome to Orbix Health. Please press 1 for English, 2 for Hindi, 3 for Odia, 4 for Spanish, or 5 for French.",
        "symptom": "Please tell us your health problem after the tone."
    },
    "hi": {
        "welcome": "Orbix Health में आपका स्वागत है। कृपया अंग्रेज़ी के लिए 1, हिंदी के लिए 2, ओड़िया के लिए 3, स्पेनिश के लिए 4, या फ्रेंच के लिए 5 दबाएँ।",
        "symptom": "टोन के बाद अपनी स्वास्थ्य समस्या बताइए।"
    },
    "or": {
        "welcome": "Orbix Health-କୁ ସ୍ୱାଗତ। ଅନ୍ୟାସ୍ଥାରେ 1, ହିନ୍ଦୀ ପାଇଁ 2, ଓଡ଼ିଆ ପାଇଁ 3, ସ୍ପାନିଶ ପାଇଁ 4, କିମ୍ବା ଫ୍ରେଞ୍ଚ ପାଇଁ 5 କ୍ଲିକ୍ କରନ୍ତୁ।",
        "symptom": "ଟୋନ୍ ଅନ୍ତରେ ନିଜର ସ୍ୱାସ୍ଥ୍ୟ ସମସ୍ୟା କହନ୍ତୁ।"
    },
    "es": {
        "welcome": "Bienvenido a Orbix Health. Presione 1 para inglés, 2 para hindi, 3 para odia, 4 para español o 5 para francés.",
        "symptom": "Por favor, describa su problema de salud después del tono."
    },
    "fr": {
        "welcome": "Bienvenue chez Orbix Health. Appuyez sur 1 pour l'anglais, 2 pour le hindi, 3 pour l'odia, 4 pour l'espagnol ou 5 pour le français.",
        "symptom": "Veuillez décrire votre problème de santé après le bip."
    }
}


def normalize_tollfree_language(language):
    if language is None:
        return "en"

    lang = str(language).strip().lower().replace("_", "-")
    aliases = {
        "en": "en",
        "english": "en",
        "en-us": "en",
        "en-in": "en",
        "hi": "hi",
        "hindi": "hi",
        "hi-in": "hi",
        "or": "or",
        "odia": "or",
        "odiya": "or",
        "or-in": "or",
        "or_in": "or",
        "es": "es",
        "spanish": "es",
        "es-es": "es",
        "fr": "fr",
        "french": "fr",
        "fr-fr": "fr",
    }
    if lang in {item["code"] for item in INDIAN_LANGUAGES}:
        return lang if lang in TOLLFREE_MESSAGES else "en"
    return aliases.get(lang, "en")


def detect_tollfree_emergency(problem):
    if not problem:
        return False

    text = problem.lower()
    emergency_patterns = [
        "chest pain",
        "trouble breathing",
        "shortness of breath",
        "can\'t breathe",
        "cannot breathe",
        "severe bleeding",
        "unconscious",
        "fainting",
        "seizure",
        "stroke",
        "heart attack",
        "hard to breathe",
        "very high fever",
        "loss of consciousness",
        "severe weakness",
        "sudden weakness",
        "difficulty breathing",
        "pain in chest",
        "chest pressure",
    ]
    hindi_patterns = [
        "सीने में दर्द",
        "साँस लेने में दिक्कत",
        "बहुत तेज बुखार",
        "बेहोशी",
        "भारी bleed",
        "गंभीर कमजोरी",
        "खून बह रहा",
        "सांस लेने में परेशानी",
        "दर्द",
    ]
    odia_patterns = [
        "ଛାତିରେ ବେଦନା",
        "ଚେଷ୍ଟରେ ବେଦନା",
        "ବେଦନା",
        "ଶ୍ୱାସ ନେବାରେ କଷ୍ଟ",
        "ସ୍ୱାସ ନେବାରେ କଷ୍ଟ",
        "ସ୍ୱାସ ନେବାରେ",
        "ଶ୍ୱାସ",
        "ସ୍ୱାସ",
        "କଷ୍ଟ",
        "ଅତ୍ୟଧିକ ଜର",
        "ଜର",
        "ବେହୋଶ",
        "ଗଭୀର ଦୁର୍ବଳତା",
        "ନିର୍ବାଣ",
        "ରକ୍ତପାତ",
        "ରକ୍ତ",
        "ଉଚ୍ଚ ଜର",
        "କ୍ଷୀଣତା",
        "ସଂକଟ",
        "ମନ୍ଦତା",
    ]
    spanish_patterns = [
        "dolor en el pecho",
        "dificultad para respirar",
        "sangrado severo",
        "desmayo",
        "fiebre alta",
        "debilidad intensa",
    ]
    french_patterns = [
        "douleur thoracique",
        "difficulté à respirer",
        "saignement important",
        "évanouissement",
        "forte fièvre",
        "faiblesse intense",
    ]

    patterns = emergency_patterns + hindi_patterns + odia_patterns + spanish_patterns + french_patterns
    return any(pattern in text for pattern in patterns)


@app.route("/api/tollfree", methods=["POST"])
def api_tollfree():
    data = request.get_json() or {}
    language = normalize_tollfree_language(data.get("language"))
    problem = (data.get("problem") or data.get("message") or "").strip()
    mode = (data.get("mode") or "voice").strip().lower()
    caller_number = data.get("caller_number") or "anonymous"

    if not problem:
        return jsonify({
            "success": False,
            "message": "Please tell us the health problem so we can guide you.",
            "language": language,
            "emergency": False,
            "demo_number": "1800-ORBIX-HEALTH",
            "mode": mode,
            "caller_number": caller_number,
        }), 400

    emergency = detect_tollfree_emergency(problem)
    message = TOLLFREE_MESSAGES[language]["emergency" if emergency else "normal"]
    call_record = {
        "id": f"CALL-{random.randint(100000, 999999)}",
        "caller_number": caller_number,
        "language": language,
        "problem": problem,
        "mode": mode,
        "emergency": emergency,
        "message": message,
        "status": "new" if not emergency else "priority",
        "created_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
    }

    logs = session.get("tollfree_logs", [])
    logs.insert(0, call_record)
    session["tollfree_logs"] = logs[:20]
    save_call_record(call_record)

    return jsonify({
        "success": True,
        "message": message,
        "language": language,
        "emergency": emergency,
        "demo_number": "1800-ORBIX-HEALTH",
        "problem": problem,
        "mode": mode,
        "caller_number": caller_number,
        "call_id": call_record["id"],
    })


@app.route("/api/tollfree/logs", methods=["GET", "POST"])
def api_tollfree_logs():
    logs = load_call_records(limit=25)
    if request.method == "POST":
        data = request.get_json() or {}
        log = {
            "id": data.get("id") or f"CALL-{random.randint(100000, 999999)}",
            "caller_number": data.get("caller_number") or "anonymous",
            "language": normalize_tollfree_language(data.get("language")),
            "problem": (data.get("problem") or "").strip(),
            "mode": (data.get("mode") or "voice").strip().lower(),
            "emergency": bool(data.get("emergency")),
            "message": (data.get("message") or "").strip(),
            "status": data.get("status") or ("priority" if bool(data.get("emergency")) else "new"),
            "created_at": data.get("created_at") or datetime.now().strftime("%d %b %Y, %I:%M %p"),
        }
        if log["problem"]:
            save_call_record(log)
            session["tollfree_logs"] = logs[:20]
        return jsonify({"success": True, "logs": load_call_records(limit=25)})
    return jsonify({"logs": logs})


@app.route("/api/call-records")
def api_call_records():
    records = load_call_records(limit=100)
    emergency_count = sum(1 for item in records if item.get("emergency"))
    return jsonify({
        "records": records,
        "summary": {
            "total": len(records),
            "emergency": emergency_count,
            "normal": len(records) - emergency_count,
        },
    })


@app.route("/api/phone/ivr", methods=["GET", "POST"])
def api_phone_ivr():
    language = normalize_tollfree_language(request.values.get("language") or request.args.get("language"))
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
    <Response>
      <Gather input="dtmf speech" timeout="7" numDigits="1" action="/api/phone/ivr/handle" method="POST" language="{language}">
        <Say>{PHONE_IVR_MESSAGES.get(language, PHONE_IVR_MESSAGES['en'])['welcome']}</Say>
      </Gather>
      <Say>We did not receive your input. Please call again.</Say>
      <Hangup />
    </Response>'''
    response = make_response(twiml, 200)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/api/twilio/voice", methods=["GET", "POST"])
def api_twilio_voice():
    return api_phone_ivr()


@app.route("/api/phone/ivr/handle", methods=["POST"])
def api_phone_ivr_handle():
    selected = (request.values.get("Digits") or "").strip()
    speech_result = (request.values.get("SpeechResult") or request.values.get("speechResult") or "").strip()
    caller_input = speech_result or selected

    language = normalize_tollfree_language(request.values.get("language"))
    if selected in {"1", "2", "3", "4", "5"}:
        mapping = {"1": "en", "2": "hi", "3": "or", "4": "es", "5": "fr"}
        language = mapping[selected]

    if not caller_input:
        message = PHONE_IVR_MESSAGES.get(language, PHONE_IVR_MESSAGES['en'])['symptom']
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
          <Gather input="speech" timeout="8" action="/api/phone/ivr/final" method="POST" language="{language}">
            <Say>{message}</Say>
          </Gather>
          <Say>We did not receive your problem. Please try again.</Say>
          <Hangup />
        </Response>'''
        response = make_response(twiml, 200)
        response.headers["Content-Type"] = "application/xml"
        return response

    problem = caller_input
    emergency = detect_tollfree_emergency(problem)
    response_message = TOLLFREE_MESSAGES[language]["emergency" if emergency else "normal"]

    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
    <Response>
      <Say>{response_message}</Say>
      <Hangup />
    </Response>'''
    response = make_response(twiml, 200)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/api/phone/ivr/final", methods=["POST"])
def api_phone_ivr_final():
    language = normalize_tollfree_language(request.values.get("language"))
    problem = (request.values.get("SpeechResult") or request.values.get("speechResult") or "").strip()
    if not problem:
        problem = (request.values.get("Digits") or "").strip()

    if not problem:
        response_message = "We did not hear your problem. Please call again."
    else:
        emergency = detect_tollfree_emergency(problem)
        response_message = TOLLFREE_MESSAGES[language]["emergency" if emergency else "normal"]

    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
    <Response>
      <Say>{response_message}</Say>
      <Hangup />
    </Response>'''
    response = make_response(twiml, 200)
    response.headers["Content-Type"] = "application/xml"
    return response


@app.route("/api/twilio/voice/handle", methods=["POST"])
def api_twilio_voice_handle():
    return api_phone_ivr_handle()


@app.route("/api/twilio/voice/final", methods=["POST"])
def api_twilio_voice_final():
    return api_phone_ivr_final()


# ══════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/auth/login")
def login_page():
    if is_logged_in():
        return redirect("/")
    return render_template("auth/login.html")

@app.route("/auth/signup")
def signup_page():
    if is_logged_in():
        return redirect("/")
    return render_template("auth/signup.html")

@app.route("/auth/profile")
def profile_page():
    if not is_logged_in():
        return redirect("/auth/login")
    return render_template("auth/profile.html", user=get_current_user())

@app.route("/auth/login", methods=["POST"])
def handle_login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"}), 400

    users = load_users()
    for uid, user in users.items():
        if user.get("email") == email:
            pwd_hash = user.get("password_hash", "")
            if isinstance(pwd_hash, str):
                pwd_hash = pwd_hash.encode()
            if bcrypt.checkpw(password.encode(), pwd_hash):
                session["user_id"] = uid
                session["username"] = user.get("first_name", "User")
                session["primary_profile"] = {
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "age": user.get("age"),
                    "gender": user.get("gender", ""),
                }
                return jsonify({"success": True, "user": user})
            return jsonify({"success": False, "message": "Invalid password"}), 401

    return jsonify({"success": False, "message": "Email not registered"}), 404

@app.route("/auth/signup", methods=["POST"])
def handle_signup():
    raw_first_name = request.form.get("first_name", "").strip()
    raw_last_name = request.form.get("last_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    age = request.form.get("age", "")
    gender = request.form.get("gender", "")

    if not all([raw_first_name, email, password]):
        return jsonify({"success": False, "message": "Required fields missing"}), 400

    if not is_valid_name(raw_first_name) or not is_valid_name(raw_last_name):
        return jsonify({"success": False, "message": "First name and last name must contain only letters"}), 400

    first_name = sanitize_name(raw_first_name)
    last_name = sanitize_name(raw_last_name)

    if password != confirm_password:
        return jsonify({"success": False, "message": "Passwords do not match"}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters"}), 400

    users = load_users()
    for _, user in users.items():
        if user.get("email") == email:
            return jsonify({"success": False, "message": "Email already registered"}), 409

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    users[user_id] = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password_hash": password_hash.decode(),
        "age": int(age) if age else None,
        "gender": gender,
        "weight": None,
        "height": None,
        "blood_group": None,
        "allergies": None,
        "emergency_name": None,
        "emergency_phone": None,
        "created_at": datetime.now().isoformat(),
    }
    save_users(users)

    session["user_id"] = user_id
    session["username"] = first_name
    session["primary_profile"] = {
        "first_name": first_name,
        "last_name": last_name,
        "age": users[user_id].get("age"),
        "gender": gender,
    }
    return jsonify({"success": True, "user_id": user_id})

@app.route("/auth/logout")
def logout():
    session.clear()
    return redirect("/auth/login")

@app.route("/api/me")
def api_me():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    user = get_current_user()
    if user:
        safe = {k: v for k, v in user.items() if k != "password_hash"}
        return jsonify({"user": safe})
    return jsonify({"error": "User not found"}), 404


def family_risk_alerts(members, records):
    recent_cutoff = datetime.now() - timedelta(days=2)
    reports = {}
    member_names = {member["id"]: member["name"] for member in members}
    for member_id, member_records in records.items():
        for record in member_records:
            if record.get("type") != "symptom":
                continue
            symptom = str(record.get("symptom", "")).strip()
            try:
                created_at = datetime.fromisoformat(record.get("created_at", ""))
            except (TypeError, ValueError):
                continue
            normalized = symptom.casefold()
            if symptom and created_at >= recent_cutoff:
                reports.setdefault(normalized, {"symptom": symptom, "members": set()})["members"].add(member_id)

    return [
        {
            "symptom": report["symptom"],
            "member_count": len(report["members"]),
            "member_names": [member_names.get(member_id, "Family member") for member_id in report["members"]],
        }
        for report in reports.values()
        if len(report["members"]) >= 2
    ]


@app.route("/api/family", methods=["GET"])
def api_family():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    owner_id = session["user_id"]
    store = read_family_data()
    account = family_account(store, owner_id)
    members = family_members(owner_id, account)
    records = {
        member_id: [record for record in member_records if isinstance(record, dict)]
        for member_id, member_records in account["records"].items()
        if isinstance(member_records, list)
    }
    vaccinations = [item for item in account["vaccinations"] if isinstance(item, dict)]
    vaccinations.sort(key=lambda item: item.get("due_date", ""))
    return jsonify({
        "members": members,
        "selected_member_id": active_family_member_id(owner_id),
        "records": records,
        "vaccinations": vaccinations,
        "alerts": family_risk_alerts(members, records),
    })


@app.route("/api/family/members", methods=["POST"])
def api_family_members():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json() or {}
    name = " ".join(str(data.get("name", "")).split())
    relation = str(data.get("relation", "")).strip().lower()
    gender = str(data.get("gender", "")).strip().lower()
    age_value = str(data.get("age", "")).strip()
    if not name or len(name) > 80:
        return jsonify({"success": False, "message": "Enter a name up to 80 characters."}), 400
    if relation not in {"spouse", "child", "parent", "other"}:
        return jsonify({"success": False, "message": "Choose a valid family relation."}), 400
    if gender not in {"", "female", "male", "other", "prefer_not_to_say"}:
        return jsonify({"success": False, "message": "Choose a valid gender option."}), 400
    try:
        age = int(age_value) if age_value else None
    except ValueError:
        return jsonify({"success": False, "message": "Age must be a number from 0 to 120."}), 400
    if age is not None and not 0 <= age <= 120:
        return jsonify({"success": False, "message": "Age must be a number from 0 to 120."}), 400

    owner_id = session["user_id"]
    store = read_family_data()
    account = family_account(store, owner_id)
    if len(account["members"]) >= 20:
        return jsonify({"success": False, "message": "A household can have up to 20 added profiles."}), 400
    member = {
        "id": str(uuid.uuid4()),
        "name": name,
        "age": age,
        "gender": gender,
        "relation": relation,
        "is_primary": False,
        "created_at": datetime.now().isoformat(),
    }
    account["members"].append(member)
    write_family_data(store)
    session["active_member_id"] = member["id"]
    return jsonify({"success": True, "member": member}), 201


@app.route("/api/family/active", methods=["POST"])
def api_family_active():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    owner_id = session["user_id"]
    store = read_family_data()
    account = store.get(owner_id, {})
    member_id = str((request.get_json() or {}).get("member_id", ""))
    allowed_ids = {member["id"] for member in family_members(owner_id, account)}
    if member_id not in allowed_ids:
        return jsonify({"success": False, "message": "Family profile not found."}), 404
    session["active_member_id"] = member_id
    return jsonify({"success": True, "selected_member_id": member_id})


@app.route("/api/family/vaccinations", methods=["POST"])
def api_family_vaccinations():
    if not is_logged_in():
        return jsonify({"error": "Not logged in"}), 401
    data = request.get_json() or {}
    name = " ".join(str(data.get("name", "")).split())
    due_date = str(data.get("due_date", "")).strip()
    owner_id = session["user_id"]
    store = read_family_data()
    account = family_account(store, owner_id)
    member_id = str(data.get("member_id") or active_family_member_id(owner_id))
    allowed_ids = {member["id"] for member in family_members(owner_id, account)}
    if not name or len(name) > 100:
        return jsonify({"success": False, "message": "Enter a vaccination name."}), 400
    try:
        datetime.strptime(due_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"success": False, "message": "Choose a valid due date."}), 400
    if member_id not in allowed_ids:
        return jsonify({"success": False, "message": "Family profile not found."}), 404
    member = next(member for member in family_members(owner_id, account) if member["id"] == member_id)
    reminder = {
        "id": str(uuid.uuid4()),
        "member_id": member_id,
        "member_name": member["name"],
        "name": name,
        "due_date": due_date,
        "created_at": datetime.now().isoformat(),
    }
    account["vaccinations"].append(reminder)
    write_family_data(store)
    return jsonify({"success": True, "vaccination": reminder}), 201


@app.route("/api/save-consultation", methods=["POST"])
def api_save_consultation():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Sign in to save this consultation."}), 401

    data = request.get_json() or {}
    doctor_name = " ".join(str(data.get("doctor_name", "")).split())
    doctor_id = str(data.get("doctor_id", "")).strip()
    call_type = str(data.get("call_type", "")).strip().lower()
    duration_value = data.get("duration_seconds")
    doctor = next((
        item for item in get_doctor_directory()
        if re.sub(r"[^a-z0-9]+", "-", item["name"].casefold()).strip("-") == doctor_id
    ), None)
    if not doctor or doctor_name.casefold() != doctor["name"].casefold():
        return jsonify({"success": False, "message": "Choose a doctor from the consultation directory."}), 400
    if call_type not in {"video", "voice"}:
        return jsonify({"success": False, "message": "Call type must be video or voice."}), 400
    if isinstance(duration_value, bool):
        return jsonify({"success": False, "message": "Call duration must be a whole number of seconds."}), 400
    try:
        duration_seconds = int(duration_value)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Call duration must be a whole number of seconds."}), 400
    if duration_seconds < 0 or duration_seconds > 86400:
        return jsonify({"success": False, "message": "Call duration must be between 0 and 86400 seconds."}), 400

    minutes, seconds = divmod(duration_seconds, 60)
    consultation = save_family_record("consultation", {
        "title": f"{call_type.title()} doctor consultation",
        "summary": f"{doctor_name} · {minutes:02d}:{seconds:02d}",
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "duration_seconds": duration_seconds,
        "call_type": call_type,
    })
    return jsonify({"success": True, "consultation": consultation}), 201


@app.route("/auth/profile", methods=["POST"])
def handle_profile_update():
    if not is_logged_in():
        return jsonify({"success": False, "message": "Not logged in"}), 401

    user_id = session["user_id"]
    users = load_users()
    if user_id not in users:
        return jsonify({"success": False, "message": "User not found"}), 404

    first_name = request.form.get("first_name", "").strip()
    last_name = request.form.get("last_name", "").strip()

    if not is_valid_name(first_name) or not is_valid_name(last_name):
        return jsonify({"success": False, "message": "First name and last name must contain only letters"}), 400

    users[user_id]["first_name"] = sanitize_name(first_name)
    users[user_id]["last_name"] = sanitize_name(last_name)
    users[user_id]["age"] = int(request.form.get("age", "")) if request.form.get("age", "").isdigit() else None
    users[user_id]["gender"] = request.form.get("gender", "")
    users[user_id]["weight"] = float(request.form.get("weight", "")) if request.form.get("weight", "").replace(".","").isdigit() else None
    users[user_id]["height"] = int(request.form.get("height", "")) if request.form.get("height", "").isdigit() else None
    users[user_id]["blood_group"] = request.form.get("blood_group", "")
    users[user_id]["allergies"] = request.form.get("allergies", "").strip() or None
    users[user_id]["emergency_name"] = request.form.get("emergency_name", "").strip() or None
    users[user_id]["emergency_phone"] = request.form.get("emergency_phone", "").strip() or None

    save_users(users)
    session["primary_profile"] = {
        "first_name": users[user_id]["first_name"],
        "last_name": users[user_id]["last_name"],
        "age": users[user_id]["age"],
        "gender": users[user_id]["gender"],
    }
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=False, port=5000)
