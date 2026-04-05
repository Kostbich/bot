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

def remove_subscriber(user_id, topic=None):
    subs = load_subscribers()
    existing = next((s for s in subs if s["id"] == user_id), None)
    if existing:
        if topic and topic in existing["topics"]:
            existing["topics"].remove(topic)
            if not existing["topics"]:
                subs.remove(existing)
        elif not topic:
            subs.remove(existing)
        else:
            return False
        
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
        return True
    return False

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
    
    # Рассылка всем подписанным
    result = broadcast_to_all(message, topic=landing_key)
    print(f"📢 Разослано {result} подписчикам")
    return True

# ========== ОТПРАВКА СООБЩЕНИЯ ==========
def send_message(chat_id, text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Ошибка отправки {chat_id}: {e}")
        return False

# ========== FLASK ПРИЛОЖЕНИЕ ==========
app = Flask(__name__)
CORS(app)

# ========== ВЕБХУК ДЛЯ TELEGRAM (ПРИНИМАЕТ КОМАНДЫ) ==========
@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Telegram отправляет сюда все сообщения от пользователей"""
    update = request.json
    print(f"📨 Получено от Telegram: {update}")
    
    if 'message' in update:
        chat_id = update['message']['chat']['id']
        username = update['message']['chat'].get('username', 'no_username')
        first_name = update['message']['chat'].get('first_name', '')
        text = update['message'].get('text', '')
        
        print(f"📩 Сообщение от @{username} ({chat_id}): {text}")
        
        # ===== ОБРАБОТКА КОМАНД =====
        if text == '/start':
            save_subscriber(chat_id, ["all"])
            welcome_msg = f"""🎯 <b>Добро пожаловать в CS2 Academy!</b>

Привет, {first_name}!

✅ Вы подписаны на уведомления о новых заявках.

<b>Доступные команды:</b>
/subscribe [тема] - подписаться на тему
/unsubscribe [тема] - отписаться
/my_topics - мои подписки
/help - помощь

<i>Пример: /subscribe cs2-kids</i>"""
            send_message(chat_id, welcome_msg)
            print(f"✅ Отправлено приветствие {chat_id}")
        
        elif text == '/help':
            help_msg = """📖 <b>Помощь по боту</b>

<b>Доступные темы:</b>
• cs2-kids - CS2 Академия (дети 12-16)
• cs2-adults - DST Academy (мужчины 30+)
• all - все новости

<b>Команды:</b>
/subscribe cs2-kids - подписаться на детей
/subscribe cs2-adults - подписаться на взрослых
/subscribe all - подписаться на всё
/unsubscribe cs2-kids - отписаться
/my_topics - мои подписки
/start - начать заново
/help - эта справка"""
            send_message(chat_id, help_msg)
        
        elif text.startswith('/subscribe'):
            parts = text.split()
            if len(parts) > 1:
                topic = parts[1]
                if topic in LANDINGS or topic == "all":
                    save_subscriber(chat_id, [topic])
                    send_message(chat_id, f"✅ Вы подписались на тему: {topic}")
                    print(f"📌 Подписал {chat_id} на {topic}")
                else:
                    send_message(chat_id, f"❌ Неизвестная тема: {topic}\nДоступно: cs2-kids, cs2-adults, all")
            else:
                send_message(chat_id, "❌ Укажите тему\nПример: /subscribe cs2-kids")
        
        elif text.startswith('/unsubscribe'):
            parts = text.split()
            if len(parts) > 1:
                topic = parts[1]
                if remove_subscriber(chat_id, topic):
                    send_message(chat_id, f"❌ Вы отписались от темы: {topic}")
                else:
                    send_message(chat_id, f"⚠️ Вы не были подписаны на {topic}")
            else:
                send_message(chat_id, "❌ Укажите тему\nПример: /unsubscribe cs2-kids")
        
        elif text == '/my_topics':
            subs = load_subscribers()
            user = next((s for s in subs if s["id"] == chat_id), None)
            if user and user["topics"]:
                topics_list = "\n".join([f"• {t}" for t in user["topics"]])
                send_message(chat_id, f"📋 <b>Ваши подписки:</b>\n{topics_list}")
            else:
                send_message(chat_id, "📋 У вас нет активных подписок.\nИспользуйте /subscribe [тема]")
        
        elif text == '/stats' and str(chat_id) == ADMIN_ID:
            subs = load_subscribers()
            stats = f"📊 <b>Статистика</b>\n\nВсего подписчиков: {len(subs)}"
            for key in LANDINGS:
                count = len(get_subscribers_by_topic(key))
                stats += f"\n• {key}: {count}"
            stats += f"\n• all: {len(get_subscribers_by_topic('all'))}"
            send_message(chat_id, stats)
        
        else:
            # Неизвестная команда
            if not text.startswith('/'):
                send_message(chat_id, "❓ Неизвестная команда. Напишите /help для списка команд")
    
    return {"ok": True}

# ========== ВЕБХУК ДЛЯ ЛЕНДИНГОВ ==========
@app.route('/webhook/<landing_key>', methods=['POST'])
def webhook_landing(landing_key):
    """Принимает заявки с лендингов"""
    print(f"📨 Webhook лендинга: {landing_key}")
    
    if landing_key not in LANDINGS:
        return {"status": "error"}, 404
    
    try:
        data = request.json
        print(f"📨 Данные: {data}")
        send_new_lead_notification(landing_key, data)
        return {"status": "ok"}, 200
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return {"status": "error"}, 500

# ========== УСТАНОВКА WEBHOOK ДЛЯ TELEGRAM ==========
def set_telegram_webhook():
    webhook_url = "https://zayavki-bot-xquz.onrender.com/webhook/telegram"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    try:
        response = requests.post(url, json={"url": webhook_url})
        print(f"📢 Telegram webhook: {response.json()}")
    except Exception as e:
        print(f"❌ Ошибка установки webhook: {e}")

@app.route('/')
def index():
    return {
        "status": "Bot is running",
        "landings": list(LANDINGS.keys()),
        "subscribers": len(load_subscribers())
    }

# ========== ПИНГ ДЛЯ ПРОБУЖДЕНИЯ ==========
def keep_alive():
    while True:
        time.sleep(240)
        try:
            requests.get('https://zayavki-bot-xquz.onrender.com/')
            print("💓 Пинг")
        except:
            pass

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    import threading
    
    # Устанавливаем webhook для Telegram
    set_telegram_webhook()
    
    # Запускаем пингер
    threading.Thread(target=keep_alive, daemon=True).start()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Бот запущен на порту {port}")
    print(f"📢 Доступные лендинги: {', '.join(LANDINGS.keys())}")
    
    app.run(host='0.0.0.0', port=port)