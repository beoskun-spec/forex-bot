from datetime import datetime, timezone
import os
import threading
import time
from flask import Flask
from google import genai
import requests

# --- CREDENTIALS & SYSTEM CONFIG ---
BOT_TOKEN = "8966884656:AAElv4PlazAeaXynH7Nxijq9tngnGs6F_uo"
CHAT_ID = "1041714540"
ALERT_MINUTES_BEFORE = 15

# Get API key securely from environment variable
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CALENDAR_URL = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json?version=1"
)
sent_alerts = set()
last_update_id = 0

# Initialize Gemini AI Client
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

app = Flask(__name__)


@app.route("/")
def home():
  return "Bot with Gemini AI is running live!"


def get_ai_analysis(title, forecast, previous):
  """Generates a brief market impact preview for XAUUSD using Gemini AI."""
  if not ai_client:
    return "AI analysis unavailable (Missing GEMINI_API_KEY)."

  prompt = (
      f"Analyze the potential impact of this economic event on XAUUSD"
      f" (Gold):\nEvent: {title}\nForecast: {forecast}\nPrevious:"
      f" {previous}\nProvide a 2-3 sentence summary covering potential market"
      f" bias, volatility expectations, and key risks for traders."
  )
  try:
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    return response.text.strip()
  except Exception as e:
    print(f"Gemini API Error: {e}")
    return "Could not generate AI analysis at this time."


def send_telegram_alert(event):
  title = event.get("title", "Economic Event")
  forecast = event.get("forecast", "N/A")
  previous = event.get("previous", "N/A")

  # Generate AI market commentary
  ai_insight = get_ai_analysis(title, forecast, previous)

  message = (
      f"⏰ *High-Impact USD Event in ~{ALERT_MINUTES_BEFORE} min*\n\n"
      f"📌 *Event:* {title}\n"
      f"📊 *Forecast:* {forecast} | *Previous:* {previous}\n\n"
      f"💡 *AI Market Insight (XAUUSD):*\n{ai_insight}"
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
  """Polls Telegram for incoming user messages and responds using Gemini AI."""
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
          incoming_text = update["message"]["text"].strip()
          user_chat_id = update["message"]["chat"]["id"]

          # Handle predefined commands
          if incoming_text.lower() in ["/start", "hello", "hi"]:
            reply = "👋 Hi! I monitor high-impact USD events and analyze XAUUSD setups using Gemini AI."
          elif incoming_text.lower() == "/status":
            reply = "✅ Bot is online, active, and integrated with Gemini AI."
          else:
            # Send custom user queries to Gemini AI
            if ai_client:
              try:
                ai_resp = ai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=(
                        "Act as an experienced XAUUSD trader. Answer concise:"
                        f" {incoming_text}"
                    ),
                )
                reply = ai_resp.text.strip()
              except Exception as e:
                reply = f"Error processing AI response: {e}"
            else:
              reply = "Gemini API key is missing in Render environment variables."

          # Send reply back to Telegram
          reply_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
          requests.post(
              reply_url, json={"chat_id": user_chat_id, "text": reply}
          )
  except Exception as e:
    print(f"Error reading incoming messages: {e}")


def run_bot():
  print("Bot and AI background loops running...")
  while True:
    check_calendar()
    handle_incoming_messages()
    time.sleep(3)


# Run background loop
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
