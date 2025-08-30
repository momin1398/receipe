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
    try:
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
            type TEXT,
            FOREIGN KEY(username) REFERENCES users(username)
        )
        """)
        conn.commit()
    except Exception as e:
        print("Error creating tables:", e)
        conn.rollback()

# ------------------------- Transaction-safe helpers -------------------------
def execute_commit(query, params=None):
    """For INSERT, UPDATE, DELETE queries."""
    if not cursor: return False
    try:
        cursor.execute(query, params or ())
        conn.commit()
        return True
    except Exception as e:
        print("DB Error:", e)
        conn.rollback()
        return False

def execute_fetch(query, params=None):
    """For SELECT queries."""
    if not cursor: return []
    try:
        cursor.execute(query, params or ())
        return cursor.fetchall()
    except Exception as e:
        print("DB Error:", e)
        conn.rollback()
        return []

# ------------------------- User Functions -------------------------
def create_superuser():
    if not cursor: return
    rows = execute_fetch("SELECT * FROM users WHERE username=%s", ("admin",))
    if not rows:
        hashed_pw = bcrypt.hashpw(SUPERUSER_PASSWORD.encode(), bcrypt.gensalt()).decode()
        execute_commit(
            "INSERT INTO users (username,password,name,email,phone,role,approved) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("admin", hashed_pw, "Super Admin", "admin@example.com", "0000000000", "superuser", 1)
        )

def register_user(username, password, name, email, phone):
    if not cursor: return False
    if execute_fetch("SELECT * FROM users WHERE username=%s", (username,)):
        return False
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return execute_commit(
        "INSERT INTO users (username,password,name,email,phone,role,approved) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (username, hashed_pw, name, email, phone, "user", 0)
    )

def login_user(username, password):
    rows = execute_fetch("SELECT * FROM users WHERE username=%s", (username,))
    user = rows[0] if rows else None
    if not user or int(user[6]) != 1: 
        return None
    if not bcrypt.checkpw(password.encode(), user[1].encode()): 
        return None
    payload = {
        "username": username,
        "role": user[5],
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_user(username):
    rows = execute_fetch("SELECT * FROM users WHERE username=%s", (username,))
    user = rows[0] if rows else None
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
    rows = execute_fetch("SELECT * FROM users")
    return [{"username": u[0], "name": u[2], "email": u[3], "phone": u[4], "role": u[5], "approved": u[6]} for u in rows]

def approve_user(username):
    execute_commit("UPDATE users SET approved=1 WHERE username=%s", (username,))

def delete_user(username):
    if username == "admin": return False
    return execute_commit("DELETE FROM users WHERE username=%s", (username,))

def change_password(username, new_password):
    hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    return execute_commit("UPDATE users SET password=%s WHERE username=%s", (hashed_pw, username))

# ------------------------- Recipe Functions -------------------------
def add_recipe(username, title, content, type="manual"):
    return execute_commit("INSERT INTO recipes (username,title,content,type) VALUES (%s,%s,%s,%s)",
                 (username,title,content,type))

def get_recipes(username):
    rows = execute_fetch("SELECT id,username,title,content,type FROM recipes WHERE username=%s", (username,))
    return [{"id": r[0],"username":r[1],"title":r[2],"content":r[3],"type":r[4]} for r in rows]

def delete_recipe(username,title):
    return execute_commit("DELETE FROM recipes WHERE username=%s AND title=%s", (username,title))

def update_recipe(username, old_title, new_title, new_content):
    return execute_commit("UPDATE recipes SET title=%s, content=%s WHERE username=%s AND title=%s",
                 (new_title,new_content,username,old_title))

# ------------------------- Ensure superuser exists -------------------------
create_superuser()
