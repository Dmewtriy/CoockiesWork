import telebot
import requests
import json
from dotenv import load_dotenv
import os
from database import session
import models

load_dotenv()

# Настройка токена вашего бота
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_TOKEN')
DOMOFON_API_URL = os.getenv('DOMOFON_API_URL')

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

headers = {'x-api-key' : 'SecretToken', 'Content-Type' : 'application/json'}

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    button = telebot.types.KeyboardButton("Отправить номер телефона", request_contact=True)
    keyboard.add(button)
    bot.send_message(message.chat.id, 'Добро пожаловать! Пожалуйста, отправьте свой номер телефона.', reply_markup=keyboard)


# Обработка полученного контакта
@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    phone_number = message.contact.phone_number
    user_already_exist = session.query(models.User).filter_by(phone_number=phone_number).first()
    if user_already_exist is not None:
        bot.send_message(message.from_user.id, 'Вы уже зарегистрированы.')
        return
    tenant_id = 1064 #get_tenant_id(phone_number) 
    if tenant_id is None:
        bot.send_message(message.chat.id, 'Ошибка авторизации. Введите корректный номер телефона.')
        return

    # Создаем пользователя и добавляем его в БД
    user = models.User(phone_number=phone_number, tenant_id=tenant_id, telegram_id=message.from_user.id)
    session.add(user)
    session.commit()
    bot.send_message(message.chat.id, 'Вы успешно авторизованы!')

    # Получаем квартиры и домофоны
    add_domofons(user)

def add_domofons(user):
    tenant_id = user.tenant_id

    # Запрос квартир
    response_apartments = requests.get(f'{DOMOFON_API_URL}domo.apartment?tenant_id={tenant_id}', headers=headers)

    if response_apartments.status_code == 200:
        apartments = response_apartments.json()
        if apartments:
            for apartment in apartments:
                # Запрос домофонов для квартиры
                response_domofons = requests.get(f'{DOMOFON_API_URL}domo.apartment/{apartment["id"]}/domofon?tenant_id={tenant_id}', headers=headers)
                if response_domofons.status_code == 200:
                    domofons = response_domofons.json()
                    for domofon in domofons:
                        # Добавляем домофон в БД
                        domofon_record = models.Domofon(user_id=tenant_id, domofon_name=domofon['name'], domofon_id=domofon['id'])
                        session.add(domofon_record)
                else:
                    return

            # Сохраняем все изменения в БД за один раз
            session.commit()
        else:
            return
    else:
        return

    if response.status_code == 200:
        return response.json()['tenant_id']
    else:
        return None
    

# Команда для получения списка домофонов
@bot.message_handler(commands=['list'])
def list_domofons(message):
    user = session.query(models.User).filter_by(telegram_id=message.from_user.id).first()
    if user is None:
        bot.send_message(message.chat.id, 'Вы не авторизованы. Пожалуйста, отправьте свой номер телефона с помощью команды /start.')
        return

    # Запрашиваем домофоны, связанные с пользователем
    domofons = session.query(models.Domofon).filter_by(user_id=user.tenant_id).all()

    if domofons:
        message_text = "Список ваших домофонов:\n"
        for domofon in domofons:
            message_text += f"id = {domofon.domofon_id}: {domofon.domofon_name}\n"
        bot.send_message(message.chat.id, message_text)
    else:
        bot.send_message(message.chat.id, 'У вас нет домофонов в базе данных.')

# Команда для получения снимка с камеры домофона
@bot.message_handler(commands=['snapshot'])
def get_camera_snapshot(message):
    user = session.query(models.User).filter_by(telegram_id=message.from_user.id).first()
    if user is None:
        bot.send_message(message.chat.id, 'Вы не авторизованы. Пожалуйста, отправьте свой номер телефона с помощью команды /start.')
        return
    tenant_id = user.tenant_id

    domofon_id = message.text.split()[1] if len(message.text.split()) > 1 else None

    if not domofon_id:
        bot.send_message(message.chat.id, 'Используйте: /snapshot <id_домофона>')
        return

    valid_intercom = session.query(models.Domofon).filter_by(domofon_id=domofon_id, user_id=tenant_id).first()
    if valid_intercom is None:
        bot.send_message(message.chat.id, 'Вам не доступен этот домофон или такого домофона не сущесвтует.')
        return

    payload = json.dumps({'intercoms_id' : [domofon_id], 'media_type' : ['JPEG']})

    response = requests.request("POST", f'{DOMOFON_API_URL}domo.domofon/urlsOnType?tenant_id={tenant_id}', headers=headers, data=payload)

    photo = response.json()[0]['jpeg']
    
    if not photo:
        bot.send_message(message.from_user.id, 'У домофона нет камер.')
        return

    if response.status_code == 200:
        snapshot_url = photo
        bot.send_photo(message.chat.id, photo=snapshot_url)
    else:
        error_message = 'Ошибка получения снимка.'
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
