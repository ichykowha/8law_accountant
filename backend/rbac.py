# backend/rbac.py
from typing import Dict

# Define roles and permissions
ROLES = {
    "admin": ["view_users", "edit_users", "view_logs", "view_health", "manage_settings"],
    "accountant": ["view_users", "view_logs", "view_health"],
    "client": ["view_health"]
}

# Example user store (should be in DB)
USER_ROLES: Dict[str, str] = {
    "1": "admin",
    "2": "client"
}

def get_user_role(user_id: str) -> str:
    return USER_ROLES.get(user_id, "client")

def has_permission(user_id: str, permission: str) -> bool:
    role = get_user_role(user_id)
    return permission in ROLES.get(role, [])
