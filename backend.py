import os
import psycopg2
import bcrypt
import jwt
from datetime import datetime, timedelta
import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query

# ------------------------- Environment -------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://avnadmin:MyPass123@pg-xxxx.aivencloud.com:28853/defaultdb?sslmode=require"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
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
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS friend_requests (
        id SERIAL PRIMARY KEY,
        sender TEXT,
        receiver TEXT,
        status TEXT, -- pending, accepted, rejected
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender TEXT,
            receiver TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    conn.commit()

# ------------------------- Transaction-safe Helpers -------------------------
def safe_execute(query, params=None):
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

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# ------------------------- FastAPI -------------------------
app = FastAPI()
active_connections = {}  # {username: websocket}
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
    if not cursor: return False
    cur = safe_execute(
        "INSERT INTO recipes (username,title,content) VALUES (%s,%s,%s)",
        (username, title, content)
    )
    return bool(cur)

def get_recipes(username):
    if not cursor: return []
    cur = safe_execute("SELECT id,username,title,content FROM recipes WHERE username=%s", (username,))
    rows = cur.fetchall() if cur else []
    return [{"id": r[0], "username": r[1], "title": r[2], "content": r[3]} for r in rows]

def delete_recipe(username,title):
    safe_execute("DELETE FROM recipes WHERE username=%s AND title=%s", (username,title))

def update_recipe(username, old_title, new_title, new_content):
    safe_execute("UPDATE recipes SET title=%s, content=%s WHERE username=%s AND title=%s",
                 (new_title,new_content,username,old_title))
    

# ------------------------- Friend Request Functions -------------------------
def send_friend_request(sender, receiver):
    if sender == receiver: return False
    cur = safe_execute("SELECT * FROM users WHERE username=%s", (receiver,))
    if not cur or not cur.fetchone(): return False
    safe_execute(
        "INSERT INTO friend_requests (sender,receiver,status) VALUES (%s,%s,'pending')",
        (sender, receiver)
    )
    return True

def respond_friend_request(request_id, status):
    if status not in ["accepted", "rejected"]: return False
    safe_execute("UPDATE friend_requests SET status=%s WHERE id=%s", (status, request_id))
    return True

def get_friend_requests(username):
    cur = safe_execute("SELECT id,sender,receiver,status,created_at FROM friend_requests WHERE receiver=%s AND status='pending'", (username,))
    rows = cur.fetchall() if cur else []
    return [{"id": r[0], "sender": r[1], "receiver": r[2], "status": r[3], "created_at": r[4]} for r in rows]

# ------------------------- Search User -------------------------
def search_users(query: str):
    q = f"%{query}%"
    cur = safe_execute("SELECT username,name,email FROM users WHERE username ILIKE %s OR name ILIKE %s OR email ILIKE %s", (q,q,q))
    rows = cur.fetchall() if cur else []
    return [{"username": r[0], "name": r[1], "email": r[2]} for r in rows]

# ------------------------- Chat with WebSockets -------------------------
async def connect_user(username, websocket: WebSocket):
    await websocket.accept()
    active_connections[username] = websocket

async def disconnect_user(username: str):
    active_connections.pop(username, None)

def save_message(sender, receiver, message):
    safe_execute(
        "INSERT INTO messages (sender, receiver, message) VALUES (%s, %s, %s)",
        (sender, receiver, message)
    )

def get_chat_history(user1, user2, limit=50):
    cur = safe_execute("""
        SELECT sender, receiver, message, created_at
        FROM messages
        WHERE (sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s)
        ORDER BY created_at DESC
        LIMIT %s
    """, (user1, user2, user2, user1, limit))
    
    rows = cur.fetchall() if cur else []
    return [
        {"sender": r[0], "receiver": r[1], "message": r[2], "created_at": r[3]}
        for r in rows
    ][::-1]  # reverse so oldest → newest


async def send_personal_message(sender, receiver, message):
    save_message(sender, receiver, message)
    if receiver in active_connections:
        await active_connections[receiver].send_json({"from": sender, "message": message})
    r.publish("chat", f"{sender}|{receiver}|{message}")

@app.websocket("/ws/{username}")
async def chat_ws(websocket: WebSocket, username: str):
    await connect_user(username, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await send_personal_message(username, data["to"], data["message"])
    except WebSocketDisconnect:
        await disconnect_user(username)


# Ensure superuser exists
create_superuser()
