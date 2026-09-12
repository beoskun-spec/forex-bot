from datetime import datetime, timezone
import os
import threading
import time
from flask import Flask
import requests

# --- CREDENTIALS ---
BOT_TOKEN = "8966884656:AAElv4PlazAeaXynH7Nxijq9tngnGs6F_uo"
CHAT_ID = "1041714540"
ALERT_MINUTES_BEFORE = 15

CALENDAR_URL = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json?version=1"
)
sent_alerts = set()
last_update_id = 0

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


def handle_incoming_messages():
  """Polls Telegram for incoming user messages and responds."""
  global last_update_id
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

  try:
    res = requests.get(
        url, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10
    )
    data = res.json()

    if data.get("ok"):
      for update in data.get("result", []):
        last_update_id = update["update_id"]

        if "message" in update and "text" in update["message"]:
          incoming_text = update["message"]["text"].strip().lower()
          user_chat_id = update["message"]["chat"]["id"]

          # Handle simple chat commands
          if incoming_text in ["/start", "hello", "hi"]:
            reply = "👋 Hello! I'm monitoring high-impact USD economic events for your XAUUSD trades."
          elif incoming_text == "/status":
            reply = "✅ Bot is online, active, and checking ForexFactory every 60 seconds."
          else:
            reply = f"Received: '{incoming_text}'. Use /status to check system health."

          # Send reply back to user
          reply_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
          requests.post(
              reply_url, json={"chat_id": user_chat_id, "text": reply}
          )
  except Exception as e:
    print(f"Error reading incoming messages: {e}")


def run_bot():
  print("Bot background loops started...")
  while True:
    check_calendar()
    handle_incoming_messages()
    time.sleep(3)  # Fast loop to respond quickly to chat messages


# Run background loop
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
