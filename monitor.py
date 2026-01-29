import os
import re
import time
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

DB_PATH = "prices.db"
CONFIG_PATH = "config.yaml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

ALERT_COOLDOWN_SECONDS = 3600
LAST_ALERT_AT = {}


@dataclass
class ItemConfig:
    name: str
    url: str
    price_selector: str
    currency: str = "BRL"
    notify_on_drop: bool = True
    drop_threshold_percent: float = 3.0


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                url TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_item_time
            ON price_history (item_name, fetched_at)
            """
        )


def save_price(item, price):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO price_history (item_name, url, price, currency, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                item.name,
                item.url,
                price,
                item.currency,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_last_price(item_name):
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            """
            SELECT price
            FROM price_history
            WHERE item_name = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (item_name,),
        ).fetchone()


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    interval = int(raw.get("check_interval_seconds", 300))
    items = [ItemConfig(**item) for item in raw.get("items", [])]

    if not items:
        raise ValueError("Nenhum item configurado no config.yaml")

    return interval, items


def fetch_html(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def parse_price(html, selector):
    soup = BeautifulSoup(html, "html.parser")
    element = soup.select_one(selector)

    if not element:
        raise ValueError(f"Selector não encontrado: {selector}")

    text = element.get_text(" ", strip=True)

    match = re.search(r"(\d[\d\.\s]*,\d{2}|\d[\d\.\s]*)", text)
    if not match:
        raise ValueError(f"Preço inválido: {text}")

    value = match.group(1).replace(" ", "")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(".", "")

    return float(value)


def send_discord_alert(item, old_price, new_price, drop_pct):
    if not DISCORD_WEBHOOK_URL:
        return

    payload = {
        "username": "Price Monitor",
        "embeds": [
            {
                "title": "Queda de preço detectada",
                "description": item.name,
                "color": 15158332,
                "fields": [
                    {
                        "name": "Preço anterior",
                        "value": f"{old_price:.2f} {item.currency}",
                        "inline": True,
                    },
                    {
                        "name": "Preço atual",
                        "value": f"{new_price:.2f} {item.currency}",
                        "inline": True,
                    },
                    {
                        "name": "Variação",
                        "value": f"-{drop_pct:.2f}%",
                        "inline": False,
                    },
                    {
                        "name": "Link",
                        "value": item.url,
                        "inline": False,
                    },
                ],
            }
        ],
    }

    requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)


def should_alert(item_name):
    now = time.time()
    last = LAST_ALERT_AT.get(item_name, 0)

    if now - last < ALERT_COOLDOWN_SECONDS:
        return False

    LAST_ALERT_AT[item_name] = now
    return True


def check_price(item):
    last = get_last_price(item.name)
    html = fetch_html(item.url)
    price = parse_price(html, item.price_selector)

    if last:
        old_price = float(last[0])
        drop_pct = ((old_price - price) / old_price) * 100

        if (
            item.notify_on_drop
            and drop_pct >= item.drop_threshold_percent
            and should_alert(item.name)
        ):
            send_discord_alert(item, old_price, price, drop_pct)

    save_price(item, price)
    print(f"{item.name}: {price:.2f} {item.currency}")


def run_once(items):
    for item in items:
        try:
            check_price(item)
        except Exception as e:
            print(f"{item.name}: erro ao processar ({e})")


def main():
    init_db()
    interval, items = load_config()

    print(f"Monitor iniciado | Intervalo {interval}s")

    while True:
        run_once(items)
        time.sleep(interval)


if __name__ == "__main__":
    main()
