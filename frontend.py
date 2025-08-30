from nicegui import ui, app
import backend
import jwt
import asyncio

# ------------------------- JWT helpers -------------------------
async def get_jwt() -> str:
    return app.storage.user.get('jwt')

async def set_jwt(token: str):
    app.storage.user['jwt'] = token

async def clear_jwt():
    if 'jwt' in app.storage.user:
        del app.storage.user['jwt']

def decode_jwt(token: str):
    try:
        return jwt.decode(token, backend.JWT_SECRET, algorithms=[backend.JWT_ALGORITHM])
    except Exception:
        return None

async def require_login() -> dict:
    token = await get_jwt()
    if not token:
        ui.notify("Please log in first", color="red")
        ui.navigate.to("/login")
        return None
    payload = decode_jwt(token)
    if not payload:
        await clear_jwt()
        ui.notify("Session expired, please login again", color="red")
        ui.navigate.to("/login")
        return None
    return payload

# ------------------------- Login Page -------------------------
@ui.page("/login")
def login_page():
    with ui.card().classes("w-96 mx-auto mt-20 p-6 shadow-lg"):
        ui.label("Login").classes("text-2xl font-bold mb-4")
        username = ui.input("Username").classes("w-full")
        password = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")

        async def try_login():
            token = backend.login_user(username.value, password.value)
            if token:
                await set_jwt(token)
                payload = decode_jwt(token)
                ui.navigate.to("/superuser" if payload["role"]=="superuser" else "/")
            else:
                ui.notify("Invalid credentials or not approved yet", color="red")

        ui.button("LOGIN", on_click=try_login).classes("w-full mt-4 bg-blue-500 text-white")
        ui.button("REGISTER", on_click=lambda: ui.navigate.to("/register")).classes("w-full mt-2 bg-green-500 text-white")
        ui.button("Change Password", on_click=lambda: ui.navigate.to("/reset_password")).classes("w-full mt-2 bg-yellow-500 text-white")

# ------------------------- Register Page -------------------------
@ui.page("/register")
def register_page():
    with ui.card().classes("w-96 mx-auto mt-20 p-6 shadow-lg"):
        ui.label("Register").classes("text-2xl font-bold mb-4")
        full_name = ui.input("Full Name").classes("w-full")
        email = ui.input("Email").classes("w-full")
        phone = ui.input("Phone Number").classes("w-full")
        username = ui.input("Choose a username").classes("w-full")
        password = ui.input("Choose a password", password=True, password_toggle_button=True).classes("w-full")

        def do_register():
            if not (full_name.value and email.value and phone.value and username.value and password.value):
                ui.notify("All fields are required", color="red")
                return
            if backend.register_user(username.value, password.value, full_name.value, email.value, phone.value):
                ui.notify("Registration submitted. Waiting for approval.", color="green")
                ui.navigate.to("/login")
            else:
                ui.notify("Username already exists", color="red")

        ui.button("REGISTER", on_click=do_register).classes("w-full mt-4 bg-green-500 text-white")
        ui.button("BACK TO LOGIN", on_click=lambda: ui.navigate.to("/login")).classes("w-full mt-2 bg-gray-500 text-white")

# ------------------------- Reset Password Page -------------------------
@ui.page("/reset_password")
def reset_password_page():
    with ui.card().classes("w-96 mx-auto mt-20 p-6 shadow-lg"):
        ui.label("Change Password").classes("text-2xl font-bold mb-4")
        username = ui.input("Username").classes("w-full")
        old_password = ui.input("Old Password", password=True, password_toggle_button=True).classes("w-full")
        new_password = ui.input("New Password", password=True, password_toggle_button=True).classes("w-full")

        async def change():
            token = backend.login_user(username.value, old_password.value)
            if not token:
                ui.notify("Invalid username or old password", color="red")
                return
            backend.change_password(username.value, new_password.value)
            ui.notify("Password changed successfully", color="green")
            ui.navigate.to("/login")

        ui.button("CHANGE PASSWORD", on_click=change).classes("w-full mt-4 bg-blue-500 text-white")
        ui.button("BACK TO LOGIN", on_click=lambda: ui.navigate.to("/login")).classes("w-full mt-2 bg-gray-500 text-white")

# ------------------------- Main Dashboard -------------------------
@ui.page("/")
async def main_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]
    user_info = backend.get_user(username)

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label(f"👋 Welcome, {user_info['name']}!").classes("text-2xl font-bold mb-2")
        ui.label(f"📧 {user_info['email']} | 📱 {user_info['phone']}")

    with ui.row().classes("mx-auto mt-6"):
        ui.button("Show Recipes", on_click=lambda: ui.navigate.to("/show_recipes")).classes("bg-blue-500 text-white")
        ui.button("Add Recipe", on_click=lambda: ui.navigate.to("/add_recipe")).classes("bg-green-500 text-white")
        ui.button("Estimation", on_click=lambda: ui.navigate.to("/calculate")).classes("bg-yellow-500 text-white")

        async def logout():
            await clear_jwt()
            ui.navigate.to("/login")
        ui.button("Logout", on_click=logout).classes("bg-red-500 text-white")

# ------------------------- Add Recipe Page -------------------------
@ui.page("/add_recipe")
async def add_recipe_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("Add Recipe").classes("text-xl font-bold mb-4")
        title = ui.input("Title").classes("w-full")
        content = ui.textarea("Content").classes("w-full")

        async def save():
            if title.value.strip() and content.value.strip():
                backend.add_recipe(username, title.value, content.value)
                ui.notify("Recipe added!", color="green")
                await asyncio.sleep(0.1)  # allow DB commit
                ui.navigate.to("/show_recipes")
            else:
                ui.notify("Title and content cannot be empty!", color="red")

        ui.button("SAVE", on_click=save).classes("mt-2 bg-green-500 text-white")
        ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-2 bg-gray-500 text-white")

# ------------------------- Show Recipes Page -------------------------
@ui.page("/show_recipes")
async def show_recipes_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]

    recipes = backend.get_recipes(username)

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("Your Recipes").classes("text-xl font-bold mb-4")
        if not recipes:
            ui.label("No recipes yet. Add some!").classes("italic")
        for r in recipes:
            with ui.card().classes("w-full mb-2 p-3"):
                ui.label(r["title"]).classes("font-bold")
                ui.label(r["content"]).classes("whitespace-pre-line")

                def delete_recipe_action(r=r):
                    backend.delete_recipe(username, r["title"])
                    ui.notify("Recipe deleted!", color="red")
                    ui.navigate.refresh()  # refresh to reflect changes

                with ui.row():
                    ui.button("Edit", on_click=lambda r=r: ui.navigate.to(f"/edit_recipe/{r['title']}")).classes("bg-blue-500 text-white mr-2")
                    ui.button("Delete", on_click=lambda r=r: delete_recipe_action(r)).classes("bg-red-500 text-white")

    ui.button("Dashboard", on_click=lambda: ui.navigate.to("/")).classes("bg-gray-500 text-white mt-2")

# ------------------------- Edit Recipe Page -------------------------
@ui.page("/edit_recipe/{title}")
async def edit_recipe(title: str):
    payload = await require_login()
    if not payload: return
    username = payload["username"]
    recipe = next((r for r in backend.get_recipes(username) if r["title"] == title), None)
    if not recipe:
        ui.label("Recipe not found").classes("text-red-500")
        return

    with ui.card().classes("w-96 mx-auto mt-20 p-6 shadow-lg"):
        new_title = ui.input("Title", value=recipe["title"]).classes("w-full")
        new_content = ui.textarea("Content", value=recipe["content"]).classes("w-full")

        async def update():
            if new_title.value.strip() and new_content.value.strip():
                backend.update_recipe(username, title, new_title.value, new_content.value)
                ui.notify("Recipe updated!", color="green")
                await asyncio.sleep(0.1)
                ui.navigate.to("/show_recipes")
            else:
                ui.notify("Title and content cannot be empty!", color="red")

        ui.button("Update", on_click=update).classes("w-full bg-blue-500 text-white mt-4")
        ui.button("Back", on_click=lambda: ui.navigate.to("/show_recipes")).classes("w-full bg-gray-500 text-white mt-2")

# ------------------------- Superuser Page -------------------------
@ui.page("/superuser")
async def superuser_page():
    payload = await require_login()
    if not payload or payload["role"] != "superuser":
        ui.notify("Access denied", color="red")
        ui.navigate.to("/login")
        return

    users = backend.get_all_users()

    with ui.card().classes("w-full max-w-3xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("Superuser Dashboard").classes("text-2xl font-bold mb-4")
        for u in users:
            with ui.card().classes("w-full mb-2 p-3"):
                ui.label(f"{u['username']} ({u['role']}) - {u['email']} | {u['phone']}")
                if not u.get("approved"):
                    async def approve_user_action(uname=u["username"]):
                        backend.approve_user(uname)
                        ui.notify(f"User {uname} approved", color="green")
                        ui.navigate.refresh()
                    ui.button("Approve", on_click=approve_user_action).classes("bg-green-500 text-white")
                if u["username"] != "admin":
                    with ui.row():
                        def change_password_popup(uname=u["username"]):
                            with ui.dialog() as dialog, ui.card():
                                ui.label(f"Set new password for {uname}").classes("mb-2")
                                pwd_input = ui.input("New Password", password=True, password_toggle_button=True).classes("w-full")
                                async def set_password():
                                    backend.change_password(uname, pwd_input.value)
                                    ui.notify(f"Password for {uname} changed", color="green")
                                    dialog.close()
                                ui.button("SET PASSWORD", on_click=set_password).classes("mt-2 bg-yellow-500 text-white")
                                ui.button("CANCEL", on_click=lambda: dialog.close()).classes("mt-2 bg-gray-500 text-white")
                            dialog.open()
                        ui.button("Change Password", on_click=change_password_popup).classes("bg-yellow-500 text-white")

                        async def delete_user_action(uname=u["username"]):
                            backend.delete_user(uname)
                            ui.notify(f"User {uname} deleted", color="red")
                            ui.navigate.refresh()
                        ui.button("Delete", on_click=delete_user_action).classes("bg-red-500 text-white")

    async def logout():
        await clear_jwt()
        ui.navigate.to("/login")

    ui.button("Logout", on_click=logout).classes("bg-red-500 text-white mt-2")

# ------------------------- Run the app -------------------------
ui.run(title="Recipe Manager (PostgreSQL + JWT)", port=8080, reload=False, storage_secret="super_secret_session_key_123")
