import os
import psycopg2
import bcrypt
import jwt
from datetime import datetime, timedelta

# ------------------------- Environment -------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://avnadmin:MyPass123@pg-xxxx.aivencloud.com:28853/defaultdb?sslmode=require"
)
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_123")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", 60))
SUPERUSER_PASSWORD = os.getenv("PAS", "admin123")

# ------------------------- Database Connection -------------------------
try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
except Exception as e:
    print("Database connection failed:", e)
    cursor = None

# ------------------------- Tables Setup -------------------------
if cursor:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        name TEXT,
        email TEXT,
        phone TEXT,
        role TEXT,
        approved INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id SERIAL PRIMARY KEY,
        username TEXT,
        title TEXT,
        content TEXT,
        FOREIGN KEY(username) REFERENCES users(username)
    )
    """)
    conn.commit()

# ------------------------- Transaction-safe Helpers -------------------------
def safe_execute(query, params=None):
    """Executes a query safely with rollback on failure."""
    if not cursor:
        return None
    try:
        cursor.execute(query, params or ())
        conn.commit()
        return cursor
    except Exception as e:
        print("DB Error:", e)
        conn.rollback()
        return None

# ------------------------- User Functions -------------------------
def create_superuser():
    if not cursor: return
    cur = safe_execute("SELECT * FROM users WHERE username=%s", ("admin",))
    if cur and not cur.fetchone():
        hashed_pw = bcrypt.hashpw(SUPERUSER_PASSWORD.encode(), bcrypt.gensalt()).decode()
        safe_execute(
            "INSERT INTO users (username,password,name,email,phone,role,approved) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("admin", hashed_pw, "Super Admin", "admin@example.com", "0000000000", "superuser", 1)
        )

def register_user(username, password, name, email, phone):
    if not cursor: return False
    cur = safe_execute("SELECT * FROM users WHERE username=%s", (username,))
    if cur and cur.fetchone(): return False
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    safe_execute(
        "INSERT INTO users (username,password,name,email,phone,role,approved) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (username, hashed_pw, name, email, phone, "user", 0)
    )
    return True

def login_user(username, password):
    if not cursor: return None
    cur = safe_execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone() if cur else None
    if not user: return None
    if int(user[6]) != 1: return None
    if not bcrypt.checkpw(password.encode(), user[1].encode()): return None
    payload = {
        "username": username,
        "role": user[5],
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_user(username):
    if not cursor: return None
    cur = safe_execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone() if cur else None
    if not user: return None
    return {
        "username": user[0],
        "name": user[2],
        "email": user[3],
        "phone": user[4],
        "role": user[5],
        "approved": user[6]
    }

def get_all_users():
    if not cursor: return []
    cur = safe_execute("SELECT * FROM users")
    users = cur.fetchall() if cur else []
    return [{"username": u[0], "name": u[2], "email": u[3], "phone": u[4], "role": u[5], "approved": u[6]} for u in users]

def approve_user(username):
    safe_execute("UPDATE users SET approved=1 WHERE username=%s", (username,))

def delete_user(username):
    if not cursor or username=="admin": return False
    safe_execute("DELETE FROM users WHERE username=%s", (username,))
    return True

def change_password(username, new_password):
    if not cursor: return False
    hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    safe_execute("UPDATE users SET password=%s WHERE username=%s", (hashed_pw, username))
    return True

# ------------------------- Recipe Functions -------------------------
def add_recipe(username, title, content):
    """Add a recipe for a user. Returns True if success, False otherwise."""
    if not cursor:
        print("DB cursor not available")
        return False

    # Ensure the user exists
    cur = safe_execute("SELECT username FROM users WHERE username=%s", (username,))
    user = cur.fetchone() if cur else None
    if not user:
        print(f"User {username} does not exist. Cannot add recipe.")
        return False

    try:
        cursor.execute(
            "INSERT INTO recipes (username,title,content) VALUES (%s,%s,%s,%s)",
            (username, title, content)
        )
        conn.commit()
        print(f"Recipe '{title}' added successfully for {username}")
        return True
    except Exception as e:
        print("Failed to add recipe:", e)
        conn.rollback()
        return False


def get_recipes(username):
    """Return a list of recipes for a user."""
    if not cursor:
        print("DB cursor not available")
        return []

    try:
        cursor.execute(
            "SELECT id,username,title,content FROM recipes WHERE username=%s",
            (username,)
        )
        rows = cursor.fetchall()
        recipes = [
            {"id": r[0], "username": r[1], "title": r[2], "content": r[3]}
            for r in rows
        ]
        print(f"Fetched {len(recipes)} recipes for {username}")
        return recipes
    except Exception as e:
        print("Failed to fetch recipes:", e)
        return []


def delete_recipe(username,title):
    safe_execute("DELETE FROM recipes WHERE username=%s AND title=%s", (username,title))

def update_recipe(username, old_title, new_title, new_content):
    safe_execute("UPDATE recipes SET title=%s, content=%s WHERE username=%s AND title=%s",
                 (new_title,new_content,username,old_title))

# Ensure superuser exists
create_superuser()