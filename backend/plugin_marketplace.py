# backend/plugin_marketplace.py
"""
Secure plugin marketplace for 8law (scaffold).
"""
PLUGINS = [
    {"name": "AI Invoice Classifier", "author": "8law", "description": "Classifies invoices using AI."},
    {"name": "Compliance Checker", "author": "8law", "description": "Automated compliance checks."}
]

def list_plugins():
    return PLUGINS

def install_plugin(name):
    # Placeholder: just return success
    return f"Plugin '{name}' installed."
