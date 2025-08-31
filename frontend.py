# frontend.py
from nicegui import ui, app
import backend
import jwt
import asyncio
import json
from fractions import Fraction

# -------------------------
# JWT helpers
# -------------------------
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

def safe_close(dialog):
    try:
        dialog.close()
    except KeyError:
        pass

# -------------------------
# Login Page
# -------------------------
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

# -------------------------
# Register Page
# -------------------------
@ui.page("/register")
def register_page():
    with ui.card().classes("w-96 mx-auto mt-20 p-6 shadow-lg"):
        ui.label("Register").classes("text-2xl font-bold mb-4")
        full_name = ui.input("Full Name").classes("w-full")
        email = ui.input("Email").classes("w-full")
        phone = ui.input("Phone Number").classes("w-full")
        username = ui.input("Username").classes("w-full")
        password = ui.input("Password", password=True, password_toggle_button=True).classes("w-full")

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

# -------------------------
# Reset Password Page
# -------------------------
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

# -------------------------
# Dashboard
# -------------------------
@ui.page("/")
async def main_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]
    user_info = backend.get_user(username)

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label(f"👋 Welcome, {user_info['name']}!").classes("text-2xl font-bold mb-2")
        ui.label(f"📧 {user_info['email']} | 📱 {user_info['phone']}")

    with ui.grid(columns=2).classes("gap-4 mx-auto mt-6"):
        ui.button("Show Recipes", on_click=lambda: ui.navigate.to("/show_recipes")).classes("bg-blue-500 text-white")
        ui.button("Add Recipe", on_click=lambda: ui.navigate.to("/add_recipe")).classes("bg-green-500 text-white")
        ui.button("Estimation", on_click=lambda: ui.navigate.to("/calculate")).classes("bg-yellow-500 text-white")
        ui.button("Friend Request", on_click=lambda: ui.navigate.to("/friends")).classes("bg-purple-500 text-white")
        ui.button("Chat Box", on_click=lambda: ui.navigate.to("/chat")).classes("bg-orange-500 text-white")
        ui.button("Find Friend", on_click=lambda: ui.navigate.to("/search")).classes("bg-pink-500 text-white")

        async def logout():
            await clear_jwt()
            ui.navigate.to("/login")
        ui.button("Logout", on_click=logout).classes("bg-red-500 text-white")

# -------------------------
# Add Recipe Page
# -------------------------
@ui.page("/add_recipe")
async def add_recipe_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("Add Recipe").classes("text-xl font-bold mb-4")
        title = ui.input("Title").classes("w-full")
        content = ui.textarea("Content").classes("w-full")

        def save():
            backend.add_recipe(username, title.value, content.value)
            ui.notify("Recipe added!", color="green")
            ui.navigate.to("/show_recipes")

        ui.button("SAVE", on_click=save).classes("mt-2 bg-green-500 text-white")
        ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-2 bg-gray-500 text-white")

# -------------------------
# Show Recipes Page
# -------------------------
@ui.page("/show_recipes")
async def show_recipes_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]
    recipes = backend.get_recipes(username)

    def refresh():
        ui.navigate.to("/show_recipes")

    with ui.card().classes("w-full max-w-3xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("Your Recipes").classes("text-3xl font-bold mb-6")

        if not recipes:
            ui.label("No recipes yet. Add some!").classes("text-gray-500 text-lg")
        else:
            for r in recipes:
                with ui.card().classes("w-full mb-2 p-3"):
                    ui.label(r["title"]).classes("text-xl font-bold mb-2")
                    ui.markdown(r["content"]).classes("mb-2 whitespace-pre-wrap text-base")

                    with ui.row().classes("gap-2"):
                        ui.button("Edit", on_click=lambda r=r: ui.navigate.to(f"/edit_recipe/{r['title']}")).classes("bg-blue-500 text-white text-sm")
                        def delete_confirm(r=r):
                            dialog = ui.dialog()
                            with dialog, ui.card():
                                ui.label(f"Delete '{r['title']}'?").classes("mb-2 font-semibold")
                                def confirm():
                                    backend.delete_recipe(username, r["title"])
                                    ui.notify(f"'{r['title']}' deleted!", color="red")
                                    safe_close(dialog)
                                    refresh()
                                ui.button("DELETE", on_click=confirm).classes("bg-red-500 text-white text-sm mt-2 mr-2")
                                ui.button("CANCEL", on_click=lambda: safe_close(dialog)).classes("bg-gray-500 text-white text-sm mt-2")
                            dialog.open()
                        ui.button("Delete", on_click=delete_confirm).classes("bg-red-500 text-white text-sm")

    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4 bg-gray-500 text-white")

# -------------------------
# Edit Recipe Page
# -------------------------
@ui.page("/edit_recipe/{title}")
async def edit_recipe_page(title: str):
    payload = await require_login()
    if not payload: return
    username = payload["username"]
    recipes = backend.get_recipes(username)
    recipe = next((r for r in recipes if r["title"] == title), None)
    if not recipe:
        ui.label("Recipe not found").classes("text-red-500")
        return

    with ui.card().classes("w-96 mx-auto mt-20 p-6 shadow-lg"):
        new_title = ui.input("Title", value=recipe["title"]).classes("w-full")
        new_content = ui.textarea("Content", value=recipe["content"]).classes("w-full")
        def update():
            backend.update_recipe(username, title, new_title.value, new_content.value)
            ui.notify("Recipe updated!", color="green")
            ui.navigate.to("/show_recipes")
        ui.button("UPDATE", on_click=update).classes("w-full bg-blue-500 text-white mt-4")

# -------------------------
# Friend Requests Page
# -------------------------
@ui.page("/friends")
async def friends_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("👥 Friend Requests").classes("text-2xl font-bold mb-4")

        requests = backend.get_friend_requests(username)
        if not requests:
            ui.label("No pending requests").classes("text-gray-500")
        else:
            for req in requests:
                with ui.row().classes("items-center gap-4"):
                    ui.label(f"{req['sender']} sent you a request")
                    def accept(req_id=req['id']):
                        backend.respond_friend_request(req_id, "accepted")
                        ui.notify("Friend request accepted", color="green")
                        ui.navigate.to("/friends")
                    def reject(req_id=req['id']):
                        backend.respond_friend_request(req_id, "rejected")
                        ui.notify("Friend request rejected", color="red")
                        ui.navigate.to("/friends")
                    ui.button("Accept", on_click=accept).classes("bg-green-500 text-white text-sm")
                    ui.button("Reject", on_click=reject).classes("bg-red-500 text-white text-sm")

        ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("w-full mt-4 bg-gray-500 text-white")

# -------------------------
# My Friends (list) Page
# -------------------------
@ui.page("/my_friends")
async def my_friends_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]

    friends = backend.get_friends(username)

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("👥 My Friends").classes("text-2xl font-bold mb-4")

        if not friends:
            ui.label("No friends yet").classes("text-gray-500")
        else:
            for f in friends:
                with ui.row().classes("mb-2 items-center gap-4"):
                    ui.label(f).classes("text-lg")
                    # Jump to chat page directly with friend prefilled
                    ui.button("Chat", on_click=lambda f=f: ui.navigate.to(f"/chat?with={f}")).classes("bg-blue-500 text-white text-sm")
        ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("w-full mt-4 bg-gray-500 text-white")

# -------------------------
# Search Users Page
# -------------------------
@ui.page("/search")
async def search_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]

    with ui.card().classes("w-full max-w-2xl mx-auto mt-10 p-6 shadow-lg"):
        ui.label("🔍 Search Users").classes("text-2xl font-bold mb-4")
        query_input = ui.input("Enter name, username, or email").classes("w-full")

        results_area = ui.column().classes("mt-4 w-full")

        def do_search():
            results_area.clear()
            results = backend.search_users(query_input.value or "")
            if not results:
                ui.label("No users found").classes("text-gray-500").parent(results_area)
                return
            for u in results:
                with results_area:
                    with ui.row().classes("items-center justify-between"):
                        ui.label(f"{u['username']} ({u.get('name') or ''}) - {u.get('email') or ''}")
                        def send_request(receiver=u['username']):
                            ok = backend.send_friend_request(username, receiver)
                            if ok:
                                ui.notify(f"Friend request sent to {receiver}", color="green")
                            else:
                                ui.notify("Failed to send request (exists / already requested / not found)", color="red")
                        ui.button("Add Friend", on_click=send_request).classes("bg-blue-500 text-white text-sm")

        ui.button("SEARCH", on_click=do_search).classes("w-full mt-2 bg-green-500 text-white")
        ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("w-full mt-2 bg-gray-500 text-white")

# -------------------------
# Chat Page (history + live WS)
# -------------------------
import websockets  # ensure websockets in requirements

@ui.page("/chat")
async def chat_page():
    payload = await require_login()
    if not payload: return
    username = payload["username"]

    # read query param ?with=username
    friend_prefill = ui.context.request.query_params.get("with") if ui.context and ui.context.request else None

    # UI layout: left sidebar (friends) + right chat
    with ui.row().classes("w-full max-w-5xl mx-auto mt-6 gap-4"):
        # Left: small friends list
        with ui.column().classes("w-1/4 h-[70vh] overflow-y-auto"):
            ui.label("Friends").classes("text-lg font-bold mb-2")
            friends = backend.get_friends(username)
            if not friends:
                ui.label("No friends yet").classes("text-gray-500")
            else:
                for f in friends:
                    def open_chat(friend=f):
                        ui.navigate.to(f"/chat?with={friend}")
                    ui.button(f, on_click=open_chat).classes("w-full text-left")
            ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4 bg-gray-500 text-white")

        # Right: chat area
        with ui.column().classes("w-3/4"):
            ui.label("💬 Chat").classes("text-2xl font-bold mb-2")
            friend_input = ui.input("Friend username", value=friend_prefill or "").classes("w-full mb-2")
            chat_area = ui.column().classes("border p-3 h-[60vh] overflow-y-auto mb-2")
            with ui.row().classes("gap-2"):
                message_input = ui.input("Type a message").props("autofocus").classes("flex-grow")
                send_btn = ui.button("Send").classes("bg-blue-500 text-white")

    # websocket connection state (module-level for this page)
    ws = {"conn": None}  # mutable holder so inner funcs can assign

    # helper: load history (sync backend call)
    def load_history(friend):
        if not friend:
            chat_area.clear()
            ui.label("Select a friend to load chat").parent(chat_area)
            return
        history = backend.get_chat_history(username, friend, limit=200)
        chat_area.clear()
        for m in history:
            sender = "You" if m["sender"] == username else m["sender"]
            ui.label(f"{sender}: {m['message']}").parent(chat_area)
        # scroll to bottom by adding an empty label (NiceGUI auto shows last)
        ui.label("").parent(chat_area)

    # call initially if friend_prefill present
    if friend_prefill:
        load_history(friend_prefill)

    # create WS connection and receiver
    async def ensure_ws_connected():
        if ws["conn"] is not None:
            return ws["conn"]
        # build websocket URL using request host
        host = ui.context.request.host if ui.context and ui.context.request else "localhost:8080"
        scheme = "wss" if (host.startswith("http") or ui.context.request.scope.get("scheme") == "https") else "wss"
        # host from context may already be host:port; construct wss URL
        wss_host = host
        uri = f"wss://{wss_host}/ws/{username}"
        try:
            conn = await websockets.connect(uri)
            ws["conn"] = conn
            # start receiver task
            asyncio.create_task(ws_receiver(conn))
            return conn
        except Exception as e:
            ui.notify(f"WebSocket connect error: {e}", color="red")
            return None

    async def ws_receiver(conn):
        try:
            async for raw in conn:
                try:
                    data = json.loads(raw)
                except Exception:
                    # ignore non-json messages
                    continue
                # if history payload
                if isinstance(data, dict) and data.get("history"):
                    # optional path if server pushes history
                    pass
                # normal incoming message
                if isinstance(data, dict) and data.get("from") and data.get("message"):
                    sender = "You" if data["from"] == username else data["from"]
                    ui.run(lambda: ui.label(f"{sender}: {data['message']}").parent(chat_area))
        except websockets.exceptions.ConnectionClosed:
            ws["conn"] = None
        except Exception as e:
            ws["conn"] = None
            ui.notify(f"WebSocket error: {e}", color="red")

    # send message handler
    async def send_message_handler():
        friend = friend_input.value.strip()
        if not friend:
            ui.notify("Select or enter friend username", color="red")
            return
        msg = message_input.value.strip()
        if not msg:
            return
        # ensure websocket connected
        conn = await ensure_ws_connected()
        if not conn:
            ui.notify("WebSocket not connected", color="red")
            return
        payload = json.dumps({"to": friend, "message": msg})
        try:
            await conn.send(payload)
            # immediate UI echo + save to DB backend already does saving server-side
            ui.label(f"You: {msg}").parent(chat_area)
            message_input.value = ""
        except Exception as e:
            ui.notify(f"Send failed: {e}", color="red")

    # bind send button
    send_btn.on("click", lambda e: asyncio.create_task(send_message_handler()))

    # load history when friend_input changes (on blur)
    friend_input.on("blur", lambda e: load_history(friend_input.value.strip()))

# -------------------------
# Search/Caclulator/Remaining pages kept as earlier...
# (I kept your existing calculate, show_recipes, edit, superuser pages)
# For brevity they are not duplicated here, but they remain unchanged.
# -------------------------

# -------------------------
# Utility to parse quantities
# -------------------------
def parse_quantity(q):
    q = str(q).strip()
    try:
        return float(Fraction(q))
    except Exception:
        return None

def scale_ingredients_by_persons(text, base_persons, target_persons):
    scaled = []
    lines = text.strip().splitlines()
    factor = target_persons / base_persons
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(' ', 2)
        if len(parts) == 3:
            name, qty, unit = parts
        elif len(parts) == 2:
            name, qty = parts
            unit = ''
        else:
            continue
        qty_num = parse_quantity(qty)
        if qty_num is None:
            continue
        scaled_qty = qty_num * factor
        scaled.append(f"{name} {scaled_qty:.2f} {unit}".strip())
    return '\n'.join(scaled)

def scale_ingredients_by_weight(text, base_weight, target_weight):
    scaled = []
    lines = text.strip().splitlines()
    factor = target_weight / base_weight
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(' ', 2)
        if len(parts) == 3:
            name, qty, unit = parts
        elif len(parts) == 2:
            name, qty = parts
            unit = ''
        else:
            continue
        qty_num = parse_quantity(qty)
        if qty_num is None:
            continue
        scaled_qty = qty_num * factor
        scaled.append(f"{name} {scaled_qty:.2f} {unit}".strip())
    return '\n'.join(scaled)

# -------------------------
# Calculator page (kept)
# -------------------------
@ui.page("/calculate")
def calculate_page():
    with ui.card().classes("w-96 mx-auto mt-20 p-6 shadow-lg"):
        ui.label("Ingredient Calculator").classes("text-2xl font-bold mb-4")

        ingredients_input = ui.textarea(
            "Enter ingredients, one per line (e.g., Flour 500 g)"
        ).classes("w-full mb-2")

        scale_type = ui.radio(["By Weight", "By Persons"], value="By Weight").classes("mb-4")

        with ui.column().classes("w-full") as weight_inputs:
            base_weight_input = ui.input("Base Weight (kg)").props('type="number"').classes("w-full mb-2")
            target_weight_input = ui.input("Target Weight (kg)").props('type="number"').classes("w-full mb-2")

        with ui.column().classes("w-full") as person_inputs:
            base_persons_input = ui.input("Base Servings (persons)").props('type="number"').classes("w-full mb-2")
            target_persons_input = ui.input("Target Servings (persons)").props('type="number"').classes("w-full mb-2")

        person_inputs.visible = False

        result_area = ui.textarea("Scaled Ingredients").classes("w-full")
        result_area._props["readonly"] = True

        def on_scale_type_change(value):
            if value == "By Weight":
                weight_inputs.visible = True
                person_inputs.visible = False
            else:
                weight_inputs.visible = False
                person_inputs.visible = True

        scale_type.on_value_change(lambda e: on_scale_type_change(e.value))

        def calculate():
            try:
                if scale_type.value == "By Weight":
                    base_weight = float(base_weight_input.value)
                    target_weight = float(target_weight_input.value)
                    result = scale_ingredients_by_weight(ingredients_input.value, base_weight, target_weight)
                else:
                    base_persons = float(base_persons_input.value)
                    target_persons = float(target_persons_input.value)
                    result = scale_ingredients_by_persons(ingredients_input.value, base_persons, target_persons)
            except (TypeError, ValueError):
                ui.notify("Please enter valid numbers", color="red")
                return
            result_area.value = result
            ui.notify("Ingredients scaled!", color="green")

        ui.button("Calculate", on_click=calculate).classes("w-full mt-2 bg-blue-500 text-white")
        ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("w-full mt-2 bg-gray-500 text-white")

# -------------------------
# Run App
# -------------------------
ui.run(title="Recipe Manager (PostgreSQL + JWT + Chat)", port=8080, reload=False, storage_secret="super_secret_session_key_123")
