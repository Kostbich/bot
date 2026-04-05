import requests
import json
import os
import time
from flask import Flask, request
from datetime import datetime
from flask_cors import CORS

# ========== НАСТРОЙКИ - ТВОЙ РАБОЧИЙ БОТ ==========
BOT_TOKEN = "8602377968:AAFYIH_d7KDZBuW4yaQIkePga7uEQC87eSA"
ADMIN_ID = "732672980"
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

# ========== РАБОТА С ПОДПИСЧИКАМИ ==========
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
    success = 0
    for user_id in user_ids:
        try:
            requests.post(url, json={"chat_id": user_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            success += 1
        except Exception as e:
            print(f"Ошибка {user_id}: {e}")
        time.sleep(0.05)
    return success

def send_new_lead_notification(landing_key, lead_data):
    landing = LANDINGS.get(landing_key)
    if not landing:
        return False
    
    message = landing["format_message"](lead_data)
    
    # Админу
    admin_msg = f"""{landing['emoji']} <b>НОВАЯ ЗАЯВКА!</b>

<b>Проект:</b> {landing['name']}
{message}"""
    
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                     json={"chat_id": landing["admin_chat_id"], "text": admin_msg, "parse_mode": "HTML"}, timeout=10)
        print(f"✅ Отправлено админу {landing['admin_chat_id']}")
    except Exception as e:
        print(f"❌ Ошибка отправки админу: {e}")
    
    # Рассылка всем подписанным на тему
    result = broadcast_to_all(message, topic=landing_key)
    print(f"📢 Разослано {result} подписчикам")
    return True

# ========== FLASK ПРИЛОЖЕНИЕ ==========
app = Flask(__name__)
CORS(app)  # Разрешаем запросы с любых доменов

@app.route('/webhook/<landing_key>', methods=['POST'])
def webhook_landing(landing_key):
    """Принимает заявки с лендингов"""
    print(f"📨 Webhook лендинга вызван: {landing_key}")
    
    if landing_key not in LANDINGS:
        print(f"❌ Неизвестный лендинг: {landing_key}")
        return {"status": "error", "message": "Unknown landing"}, 404
    
    try:
        data = request.json
        print(f"📨 Получены данные: {data}")
        
        send_new_lead_notification(landing_key, data)
        
        return {"status": "ok", "message": "Lead sent"}, 200
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route('/')
def index():
    return {
        "status": "Bot is running",
        "landings": list(LANDINGS.keys()),
        "subscribers": len(load_subscribers())
    }

# ========== ПИНГ ДЛЯ ПРОБУЖДЕНИЯ (Render не засыпает) ==========
def keep_alive():
    """Пинг самого себя каждые 4 минуты"""
    while True:
        time.sleep(240)  # 4 минуты
        try:
            requests.get('https://zayavki-bot-xquz.onrender.com/')
            print("💓 Пинг отправлен")
        except Exception as e:
            print(f"❌ Ошибка пинга: {e}")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    import threading
    
    # Запускаем пингер
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Бот запущен на порту {port}")
    print(f"📢 Доступные лендинги: {', '.join(LANDINGS.keys())}")
    print(f"🔗 Webhook URL: https://zayavki-bot-xquz.onrender.com/webhook/<landing>")
    
    app.run(host='0.0.0.0', port=port)