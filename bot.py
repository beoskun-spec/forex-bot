from datetime import datetime, timezone
import os
import threading
import time
from flask import Flask
import requests

# --- YOUR CREDENTIALS ---
BOT_TOKEN = "8966884656:AAElv4PlazAeaXynH7Nxijq9tngnGs6F_uo"
CHAT_ID = "1041714540"
ALERT_MINUTES_BEFORE = 15

CALENDAR_URL = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json?version=1"
)
sent_alerts = set()

# Web server bound to Render's environment port
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is running live!"


def send_telegram_alert(event):
  title = event.get("title", "Economic Event")
  forecast = event.get("forecast", "N/A")
  previous = event.get("previous", "N/A")

  message = (
      f"⏰ *High-impact USD event in ~{ALERT_MINUTES_BEFORE} min*\n"
      f"*{title}*\n"
      f"Forecast {forecast} · Previous {previous}\n"
      f"Watch *XAUUSD* for volatility."
  )

  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}

  try:
    res = requests.post(url, json=payload)
    res.raise_for_status()
    print(f"[{datetime.now()}] Alert sent for {title}")
  except Exception as e:
    print(f"Error sending alert: {e}")


def check_calendar():
  try:
    response = requests.get(CALENDAR_URL, timeout=10)
    events = response.json()
    now = datetime.now(timezone.utc)

    for event in events:
      if event.get("impact") == "High" and event.get("country") == "USD":
        event_date_str = event["date"].replace("Z", "+00:00")
        event_time = datetime.fromisoformat(event_date_str)
        time_diff = (event_time - now).total_seconds() / 60

        event_id = f"{event.get('title')}_{event.get('date')}"
        if 0 < time_diff <= ALERT_MINUTES_BEFORE and event_id not in sent_alerts:
          send_telegram_alert(event)
          sent_alerts.add(event_id)

  except Exception as e:
    print(f"Error checking calendar: {e}")


def run_bot():
  print("Bot started checking events...")
  while True:
    check_calendar()
    time.sleep(60)


# Run background calendar check thread
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
