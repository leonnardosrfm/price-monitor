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

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    interval = int(raw.get("check_interval_seconds", 300))
    items = []
    for it in raw.get("items", []):
        items.append(ItemConfig(**it))
    if not items:
        raise ValueError("config.yaml sem items. Adicione pelo menos 1 produto.")
    return interval, items

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

def parse_price_from_html(html: str, selector: str) -> float:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one(selector)
    if not el:
        raise ValueError(f"Não achei o elemento do preço com selector: {selector}")

    text = el.get_text(" ", strip=True)

    # Extrai número no padrão BR: "R$ 1.234,56" ou "1234,56"
    # 1) pega a parte numérica
    m = re.search(r"(\d[\d\.\s]*,\d{2}|\d[\d\.\s]*)", text)
    if not m:
        raise ValueError(f"Não consegui extrair número do texto do preço: {text}")

    num = m.group(1).replace(" ", "")
    # Se tiver vírgula decimal, converte "1.234,56" => "1234.56"
    if "," in num:
        num = num.replace(".", "").replace(",", ".")
    else:
        # "1.234" pode ser milhar; nesse caso removemos pontos
        num = num.replace(".", "")

    return float(num)

def save_price(item: ItemConfig, price: float):
    fetched_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO price_history (item_name, url, price, currency, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item.name, item.url, price, item.currency, fetched_at),
        )

def get_last_price(item_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT price, fetched_at
            FROM price_history
            WHERE item_name = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (item_name,),
        ).fetchone()
    return row  # (price, fetched_at) ou None

def maybe_notify_drop(item: ItemConfig, new_price: float, old_price: float):
    if old_price <= 0:
        return
    drop_pct = ((old_price - new_price) / old_price) * 100.0
    if item.notify_on_drop and drop_pct >= item.drop_threshold_percent:
        print(
            f"[ALERTA] {item.name} caiu {drop_pct:.2f}%: "
            f"{old_price:.2f} -> {new_price:.2f} ({item.currency})"
        )

def run_once(items):
    for item in items:
        try:
            last = get_last_price(item.name)
            html = fetch_html(item.url)
            price = parse_price_from_html(html, item.price_selector)

            if last:
                old_price = float(last[0])
                maybe_notify_drop(item, price, old_price)

            save_price(item, price)
            print(f"[OK] {item.name}: {price:.2f} {item.currency}")

        except Exception as e:
            print(f"[ERRO] {item.name}: {e}")

def main():
    init_db()
    interval, items = load_config()
    print(f"Monitor iniciado. Intervalo: {interval}s. Itens: {len(items)}")

    while True:
        run_once(items)
        time.sleep(interval)

if __name__ == "__main__":
    main()
