# 8law Python SDK (example)
import requests

class EightLawClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')

    def list_users(self):
        return requests.get(f"{self.base_url}/users").json()

    def get_logs(self):
        return requests.get(f"{self.base_url}/logs").json()

    def get_health(self):
        return requests.get(f"{self.base_url}/health").json()

    def get_notifications(self, user_id):
        return requests.get(f"{self.base_url}/notifications/{user_id}").json()

# Usage:
# client = EightLawClient("http://localhost:8000")
# print(client.list_users())
