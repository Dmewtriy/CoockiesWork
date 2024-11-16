import telebot
import requests
import json

# Настройка токена вашего бота
TELEGRAM_API_TOKEN = '7763432669:AAFLq98WvZk0RNpZXgJmlO6dyPoL7djRe74'
DOMOFON_API_URL = 'https://domo-dev.profintel.ru/tg-bot/'  # Замените на реальный URL API домофона

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

headers = {'x-api-key' : 'SecretToken',
           'Content-Type' : 'application/json'}

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Добро пожаловать! Пожалуйста, авторизуйтесь с помощью команды /login <номер_телефона>.')

# Команда для авторизации пользователя
@bot.message_handler(commands=['login'])
def login(message):
    phone_number = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not phone_number:
        bot.send_message(message.chat.id, 'Используйте: /login <номер_телефона>')
        return

    payload = json.dumps({'phone' : phone_number})

    response = requests.request("POST", f'{DOMOFON_API_URL}check-tenant', headers=headers, data=payload)

    if response.status_code == 200:
        bot.send_message(message.chat.id, 'Вы успешно авторизованы!')
    else:
        error_message = 'Ошибка авторизации. Введите корректный номер телефона'
        bot.send_message(message.chat.id, error_message)

# Команда для получения списка домофонов
@bot.message_handler(commands=['list'])
def list_domofons(message):
    
    phone_number = 70018937644
    if not phone_number:
        bot.send_message(message.chat.id, 'Сначала авторизуйтесь с помощью /login <номер_телефона>.')
        return

    response_apartments = requests.request("GET", f'{DOMOFON_API_URL}domo.apartment?tenant_id={1064}', headers=headers)

    if response_apartments.status_code == 200:
        apartmens = response_apartments.json()
        domofons_id = set()
        if apartmens:
            message_text = "Список доступных домофонов:\n"
            for apartment in apartmens:
                responce_domofon = requests.request("GET", f'{DOMOFON_API_URL}domo.apartment/{apartment['id']}/domofon?tenant_id={1064}', headers=headers)
                domofons = responce_domofon.json()
                for domofon in domofons:
                    if (domofon['id'] not in domofons_id):
                        domofons_id.add(domofon['id'])
                        message_text += f"id = {domofon['id']}: {domofon['name']}\n"
            bot.send_message(message.chat.id, message_text)
        else:
            bot.send_message(message.chat.id, 'Нет доступных домофонов.')
    else:
        error_message = 'Ошибка получения списка домофонов.'
        bot.send_message(message.chat.id, error_message)

# Команда для получения снимка с камеры домофона
@bot.message_handler(commands=['snapshot'])
def get_camera_snapshot(message):
    phone_number = getattr(message.from_user, 'phone', None)

    if not phone_number:
        bot.send_message(message.chat.id, 'Сначала авторизуйтесь с помощью /login.')
        return

    domofon_id = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not domofon_id:
        bot.send_message(message.chat.id, 'Используйте: /snapshot <id_домофона>')
        return

    response = requests.get(f'{DOMOFON_API_URL}/domofons/{domofon_id}/snapshot?phone={phone_number}')

    if response.status_code == 200:
        snapshot_url = response.json().get('snapshot_url')
        bot.send_photo(message.chat.id, photo=snapshot_url)
    else:
        error_message = response.json().get('error', 'Ошибка получения снимка.')
        bot.send_message(message.chat.id, error_message)

# Команда для открытия домофона
@bot.message_handler(commands=['open'])
def open_domofon(message):
    phone_number = getattr(message.from_user, 'phone', None)

    if not phone_number:
        bot.send_message(message.chat.id, 'Сначала авторизуйтесь с помощью /login.')
        return

    domofon_id = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not domofon_id:
        bot.send_message(message.chat.id, 'Используйте: /open <id_домофона>')
        return

    url = f'{DOMOFON_API_URL}domo.domofon/{domofon_id}/relay/on'
    response = requests.post(url, headers={'x-api-key': 'SecretToken'}, json={'phone': phone_number})

    if response.status_code == 200:
        bot.send_message(message.chat.id, 'Дверь успешно открыта!')
    else:
        error_message = response.json().get('error', 'Ошибка при открытии двери.')
        bot.send_message(message.chat.id, error_message)




bot.polling(none_stop=True)
