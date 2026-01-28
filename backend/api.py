# backend/api.py
from fastapi import FastAPI
from backend.admin import list_users, get_logs, get_system_health
from backend.notifications import get_user_notifications

app = FastAPI(title="8law API", description="API for 8law platform.")

@app.get("/users")
def api_list_users():
    return list_users()

@app.get("/logs")
def api_get_logs():
    return get_logs()

@app.get("/health")
def api_get_health():
    return get_system_health()

@app.get("/notifications/{user_id}")
def api_get_notifications(user_id: str):
    return get_user_notifications(user_id)

# To run: uvicorn backend.api:app --reload
