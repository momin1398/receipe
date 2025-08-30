import jwt
import bcrypt
from datetime import datetime, timedelta
from tinydb import TinyDB, Query

# -------------------------
# DB Setup
# -------------------------
db = TinyDB("db.json")
users_table = db.table("users")
recipes_table = db.table("recipes")

JWT_SECRET = "super_secret_jwt_key_123"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60


# -------------------------
# User Functions
# -------------------------
def create_superuser():
    """Ensure a superuser exists"""
    User = Query()
    if not users_table.get(User.username == "admin"):
        hashed_pw = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        users_table.insert({
            "username": "admin",
            "password": hashed_pw,
            "name": "Super Admin",
            "email": "admin@example.com",
            "phone": "0000000000",
            "role": "superuser",
            "approved": True,
        })


def register_user(username, password, name, email, phone):
    """Register a new user (needs approval by superuser)"""
    User = Query()
    if users_table.get(User.username == username):
        return False

    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users_table.insert({
        "username": username,
        "password": hashed_pw,
        "name": name,
        "email": email,
        "phone": phone,
        "role": "user",
        "approved": False,  # superuser must approve
    })
    return True


def login_user(username, password):
    """Login user and return JWT"""
    User = Query()
    user = users_table.get(User.username == username)
    if not user or not user.get("approved"):
        return None

    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return None

    payload = {
        "username": username,
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_user(username):
    User = Query()
    return users_table.get(User.username == username)


def get_all_users():
    return users_table.all()


def approve_user(username):
    User = Query()
    users_table.update({"approved": True}, User.username == username)


def delete_user(username):
    """Delete user but not superuser"""
    if username == "admin":
        return False
    User = Query()
    users_table.remove(User.username == username)
    return True


def change_password(username, new_password):
    """Change password, superuser password cannot be changed"""
    if username == "admin":
        return False
    User = Query()
    hashed_pw = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    users_table.update({"password": hashed_pw}, User.username == username)
    return True


# -------------------------
# Recipe Functions
# -------------------------
def add_recipe(username, title, content):
    recipes_table.insert({"username": username, "title": title, "content": content})


def get_recipes(username):
    Recipe = Query()
    return recipes_table.search(Recipe.username == username)


def delete_recipe(username, title):
    Recipe = Query()
    recipes_table.remove((Recipe.username == username) & (Recipe.title == title))


def update_recipe(username, old_title, new_title, new_content):
    Recipe = Query()
    recipes_table.update(
        {"title": new_title, "content": new_content},
        (Recipe.username == username) & (Recipe.title == old_title),
    )


# Ensure superuser exists
create_superuser()
