import requests
import json
import os
import time
from flask import Flask, request
from datetime import datetime

# ========== НАСТРОЙКИ - ЗАМЕНИ НА СВОИ! ==========
BOT_TOKEN = "8602377968:AAFYIH_d7KDZBuW4yaQIkePga7uEQC87eSA"  # ЗАМЕНИ!
ADMIN_ID = "732672980"  # ЗАМЕНИ!
# =================================================

SUBSCRIBERS_FILE = "subscribers.json"

# ========== КОНФИГУРАЦИЯ ЛЕНДИНГОВ ==========
LANDINGS = {
    "cs2-kids": {
        "name": "CS2 Академия (дети 12-16)",
        "emoji": "🎮",
        "admin_chat_id": ADMIN_ID,
        "format_message": lambda data: f"""🎮 <b>НОВАЯ ЗАЯВКА - CS2 ДЕТИ 12-16!</b>

👨‍👩 Родитель: {data.get('parentName', '-')}
🧒 Ребёнок: {data.get('childName', '-')}
📞 Телефон: {data.get('phone', '-')}
📱 Telegram: {data.get('telegramUsername', 'не указан')}
🎯 FaceIt уровень: {data.get('mmr', '-')}

⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""
    },
    "cs2-adults": {
        "name": "DST Academy (мужчины 30+)",
        "emoji": "💼",
        "admin_chat_id": ADMIN_ID,
        "format_message": lambda data: f"""💼 <b>НОВАЯ ЗАЯВКА - DST ACADEMY 30+!</b>

👤 Имя: {data.get('name', '-')}
📞 Телефон: {data.get('phone', '-')}
📱 Telegram: {data.get('telegram', 'не указан')}
🎮 Ранг: {data.get('rank', '-')}

⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""
    },
}

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_subscriber(user_id, topics=None):
    subs = load_subscribers()
    existing = next((s for s in subs if s["id"] == user_id), None)
    if existing:
        if topics:
            existing["topics"] = list(set(existing["topics"] + topics))
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
        return False
    else:
        subs.append({
            "id": user_id,
            "topics": topics or ["all"],
            "subscribed_at": datetime.now().isoformat()
        })
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
        return True

def get_subscribers_by_topic(topic):
    subs = load_subscribers()
    return [s["id"] for s in subs if "all" in s["topics"] or topic in s["topics"]]

def broadcast_to_all(message, topic=None):
    if topic:
        user_ids = get_subscribers_by_topic(topic)
    else:
        subs = load_subscribers()
        user_ids = [s["id"] for s in subs]
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for user_id in user_ids:
        try:
            requests.post(url, json={"chat_id": user_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            print(f"Ошибка {user_id}: {e}")
        time.sleep(0.05)
    return len(user_ids)

def send_new_lead_notification(landing_key, lead_data):
    landing = LANDINGS.get(landing_key)
    if not landing:
        return False
    
    message = landing["format_message"](lead_data)
    
    # Админу
    admin_msg = f"""{landing['emoji']} <b>НОВАЯ ЗАЯВКА!</b>

<b>Проект:</b> {landing['name']}
{message}"""
    
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                 json={"chat_id": landing["admin_chat_id"], "text": admin_msg, "parse_mode": "HTML"})
    
    # Всем подписанным
    return broadcast_to_all(message, topic=landing_key)

# ========== ОБРАБОТКА КОМАНД ==========
def handle_updates():
    last_update_id = 0
    url_get = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    print("🤖 Бот запущен!")
    
    while True:
        try:
            response = requests.get(url_get, params={"offset": last_update_id + 1, "timeout": 30})
            updates = response.json()
            
            if "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update:
                        chat_id = update["message"]["chat"]["id"]
                        text = update["message"].get("text", "")
                        
                        if text == "/start":
                            save_subscriber(chat_id, ["all"])
                            welcome = """🎯 Добро пожаловать в рассылку CS2 Академий!

Доступные темы:
/subscribe cs2-kids - Дети 12-16
/subscribe cs2-adults - Мужчины 30+
/subscribe all - Всё

Команды:
/my_topics - Мои подписки
/unsubscribe [тема] - Отписаться
/help - Помощь"""
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                        json={"chat_id": chat_id, "text": welcome})
                        
                        elif text == "/help":
                            help_msg = """📖 Помощь

/subscribe cs2-kids - Дети 12-16
/subscribe cs2-adults - Мужчины 30+
/my_topics - Мои подписки
/unsubscribe all - Отписаться от всего"""
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                        json={"chat_id": chat_id, "text": help_msg})
                        
                        elif text.startswith("/subscribe"):
                            parts = text.split()
                            if len(parts) > 1:
                                topic = parts[1]
                                if topic in LANDINGS or topic == "all":
                                    save_subscriber(chat_id, [topic])
                                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                                json={"chat_id": chat_id, "text": f"✅ Подписан на {topic}"})
                        
                        elif text == "/my_topics":
                            subs = load_subscribers()
                            user = next((s for s in subs if s["id"] == chat_id), None)
                            if user:
                                topics = ", ".join(user["topics"])
                                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                            json={"chat_id": chat_id, "text": f"📋 Ваши подписки: {topics}"})
                        
                        elif text == "/stats" and str(chat_id) == ADMIN_ID:
                            subs = load_subscribers()
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                        json={"chat_id": chat_id, "text": f"📊 Подписчиков: {len(subs)}"})
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)

# ========== WEBHOOK ==========
app = Flask(__name__)

@app.route('/webhook/<landing_key>', methods=['POST'])
def webhook(landing_key):
    if landing_key not in LANDINGS:
        return {"status": "error"}, 404
    try:
        data = request.json
        send_new_lead_notification(landing_key, data)
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "error"}, 500

@app.route('/')
def index():
    return {"status": "Bot is running", "landings": list(LANDINGS.keys())}

if __name__ == "__main__":
    import threading
    thread = threading.Thread(target=handle_updates, daemon=True)
    thread.start()
    app.run(host='0.0.0.0', port=5000)