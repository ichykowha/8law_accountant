# backend/ai_assistant.py
"""
In-app AI assistant/chatbot for 8law (scaffold).
"""
import os
import requests
import json

def ask_ai_assistant(user_id, message):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "AI assistant unavailable: API key not set."
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    prompt = f"You are 6law, an expert AI accounting assistant. User context: user_id={user_id}. Message: {message}"
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 256}
    }
    try:
        resp = requests.post(f"{endpoint}?key={api_key}", headers=headers, data=json.dumps(data), timeout=10)
        resp.raise_for_status()
        out = resp.json()
        return out["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI assistant error: {e}"
