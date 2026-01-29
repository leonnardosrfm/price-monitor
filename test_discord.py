import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("DISCORD_WEBHOOK_URL")

payload = {
    "content": "Teste de webhook funcionando!"
}

r = requests.post(url, json=payload)
print(r.status_code)
