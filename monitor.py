import os
import json
import re
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

STATE_FILE = "seen_products.json"

URLS = [
    "https://mediamarkt.pl/",
]

MIN_DISCOUNT = 70


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=20,
    )


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_discount(text):
    matches = re.findall(r"(\d{1,3})\s*%", text)
    values = [int(x) for x in matches if int(x) <= 100]
    return max(values) if values else 0


def is_unavailable(text):
    text = text.lower()

    phrases = [
        "wkrótce dostępne",
        "trwale wyprzedane",
        "chwilowo niedostępny",
        "produkt niedostępny",
        "wyprzedane",
        "brak w magazynie",
    ]

    return any(phrase in text for phrase in phrases)


def scan_page(url, state):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
        )
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a", href=True):
        name = link.get_text(" ", strip=True)

        if not name or len(name) < 5:
            continue

        parent = link
        for _ in range(4):
            if parent.parent:
                parent = parent.parent

        text = parent.get_text(" ", strip=True)

        discount = get_discount(text)

        if discount < MIN_DISCOUNT:
            continue

        product_url = link["href"]

        if product_url.startswith("/"):
            product_url = "https://mediamarkt.pl" + product_url

        product_id = product_url.split("?")[0]

        unavailable = is_unavailable(text)

        old = state.get(product_id)

        current_state = {
            "name": name,
            "url": product_url,
            "discount": discount,
            "unavailable": unavailable,
        }

        # Powiadomienie tylko przy nowym produkcie
        # albo zmianie stanu z niedostępnego na dostępny.
        should_alert = False

        if old is None:
            should_alert = True
        elif old.get("unavailable") and not unavailable:
            should_alert = True
        elif discount > old.get("discount", 0):
            should_alert = True

        if should_alert:
            status = (
                "🟡 WKRÓTCE / NIEDOSTĘPNY"
                if unavailable
                else "🟢 DOSTĘPNY"
            )

            message = (
                f"🔥 MEDIA MARKT — PRZECENA {discount}%\n\n"
                f"📦 {name}\n"
                f"📌 {status}\n\n"
                f"🔗 {product_url}"
            )

            send_telegram(message)

        state[product_id] = current_state


def main():
    state = load_state()

    for url in URLS:
        try:
            scan_page(url, state)
        except Exception as e:
            print(f"Błąd podczas skanowania {url}: {e}")

    save_state(state)


if __name__ == "__main__":
    main()
