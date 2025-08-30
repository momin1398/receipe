import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta
import os

# -------------------------
# DB & JWT Setup
# -------------------------
DB_FILE = os.getenv("DB_FILE", "/mnt/data/app.db")  # persistent storage on Render
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_123")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
pas = os.getenv("pas", "admin123")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", 60))

# Connect to DB and create tables if they don't exist
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# Users table
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

# Recipes table
cursor.execute("""
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    title TEXT,
    content TEXT,
    FOREIGN KEY(username) REFERENCES users(username)
)
""")
conn.commit()

# -------------------------
# User Functions
# -------------------------
def create_superuser():
    cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    if not cursor.fetchone():
        hashed_pw = bcrypt.hashpw(pas.encode(), bcrypt.gensalt()).decode()
        cursor.execute("""
        INSERT INTO users (username, password, name, email, phone, role, approved)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("admin", hashed_pw, "Super Admin", "admin@example.com", "0000000000", "superuser", 1))
        conn.commit()

def register_user(username, password, name, email, phone):
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return False
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("""
    INSERT INTO users (username, password, name, email, phone, role, approved)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (username, hashed_pw, name, email, phone, "user", 0))
    conn.commit()
    return True

def login_user(username, password):
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if not user:
        return None

    approved = int(user[6])  # ensure integer
    if approved != 1:
        return None

    if not bcrypt.checkpw(password.encode(), user[1].encode()):
        return None

    payload = {
        "username": username,
        "role": user[5],
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_user(username):
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user:
        return {
            "username": user[0],
            "name": user[2],
            "email": user[3],
            "phone": user[4],
            "role": user[5],
            "approved": user[6]
        }
    return None

def get_all_users():
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return [
        {
            "username": u[0],
            "name": u[2],
            "email": u[3],
            "phone": u[4],
            "role": u[5],
            "approved": u[6]
        } for u in users
    ]

def approve_user(username):
    cursor.execute("UPDATE users SET approved = 1 WHERE username = ?", (username,))
    conn.commit()

def delete_user(username):
    if username == "admin":
        return False
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    return True

def change_password(username, new_password):
    hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, username))
    conn.commit()
    return True

# -------------------------
# Recipe Functions
# -------------------------
def add_recipe(username, title, content):
    cursor.execute("""
    INSERT INTO recipes (username, title, content)
    VALUES (?, ?, ?)
    """, (username, title, content))
    conn.commit()

def get_recipes(username):
    cursor.execute("SELECT * FROM recipes WHERE username = ?", (username,))
    recipes = cursor.fetchall()
    return [{"id": r[0], "username": r[1], "title": r[2], "content": r[3]} for r in recipes]

def delete_recipe(username, title):
    cursor.execute("DELETE FROM recipes WHERE username = ? AND title = ?", (username, title))
    conn.commit()

def update_recipe(username, old_title, new_title, new_content):
    cursor.execute("""
    UPDATE recipes
    SET title = ?, content = ?
    WHERE username = ? AND title = ?
    """, (new_title, new_content, username, old_title))
    conn.commit()

# Ensure superuser exists
create_superuser()
