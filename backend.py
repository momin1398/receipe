import os
import psycopg2
import bcrypt
import jwt
from datetime import datetime, timedelta

# -------------------------
# Config
# -------------------------
DB_URL = os.getenv("DATABASE_URL")  # Your Aiven PostgreSQL URL
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_jwt_key_123")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", 60))
SUPERUSER_PASSWORD = os.getenv("PAS", "admin123")

# -------------------------
# Connect to PostgreSQL
# -------------------------
conn = psycopg2.connect(DB_URL, sslmode='require')
cursor = conn.cursor()

# -------------------------
# Create Tables
# -------------------------
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

# -------------------------
# User Functions
# -------------------------
def create_superuser():
    cursor.execute("SELECT * FROM users WHERE username = %s", ("admin",))
    if not cursor.fetchone():
        hashed_pw = bcrypt.hashpw(SUPERUSER_PASSWORD.encode(), bcrypt.gensalt()).decode()
        cursor.execute("""
        INSERT INTO users (username, password, name, email, phone, role, approved)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, ("admin", hashed_pw, "Super Admin", "admin@example.com", "0000000000", "superuser", 1))
        conn.commit()

def register_user(username, password, name, email, phone):
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        return False
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("""
    INSERT INTO users (username, password, name, email, phone, role, approved)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (username, hashed_pw, name, email, phone, "user", 0))
    conn.commit()
    return True

def login_user(username, password):
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if not user:
        return None

    approved = int(user[6])
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
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
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
    cursor.execute("UPDATE users SET approved = 1 WHERE username = %s", (username,))
    conn.commit()

def delete_user(username):
    if username == "admin":
        return False
    cursor.execute("DELETE FROM users WHERE username = %s", (username,))
    conn.commit()
    return True

def change_password(username, new_password):
    hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    cursor.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_pw, username))
    conn.commit()
    return True

# -------------------------
# Recipe Functions
# -------------------------
def add_recipe(username, title, content):
    cursor.execute("""
    INSERT INTO recipes (username, title, content)
    VALUES (%s, %s, %s)
    """, (username, title, content))
    conn.commit()

def get_recipes(username):
    cursor.execute("SELECT * FROM recipes WHERE username = %s", (username,))
    recipes = cursor.fetchall()
    return [{"id": r[0], "username": r[1], "title": r[2], "content": r[3]} for r in recipes]

def delete_recipe(username, title):
    cursor.execute("DELETE FROM recipes WHERE username = %s AND title = %s", (username, title))
    conn.commit()

def update_recipe(username, old_title, new_title, new_content):
    cursor.execute("""
    UPDATE recipes
    SET title = %s, content = %s
    WHERE username = %s AND title = %s
    """, (new_title, new_content, username, old_title))
    conn.commit()

# -------------------------
# Ensure superuser exists
# -------------------------
create_superuser()
