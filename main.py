import telebot
import requests
import json
from dotenv import load_dotenv
import os
from database import session
import models
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import threading

load_dotenv()

# Настройка токена вашего бота
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_TOKEN')
DOMOFON_API_URL = os.getenv('DOMOFON_API_URL')

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

app = FastAPI()

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
    user_already_exist = session.query(models.User).filter_by(phone_number=phone_number, telegram_id=message.from_user.id).first()
    if user_already_exist is not None:
        bot.send_message(message.from_user.id, 'Вы уже зарегистрированы.')
        return
    tenant_id = get_tenant_id(phone_number) 
    if tenant_id is None:
        bot.send_message(message.chat.id, 'Ошибка авторизации. Введите корректный номер телефона.')
        return

    # Создаем пользователя и добавляем его в БД
    user = models.User(phone_number=phone_number, tenant_id=tenant_id, telegram_id=message.from_user.id)
    session.add(user)
    session.commit()

    # Получаем домофоны
    add_domofons(user)
    
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    button = telebot.types.KeyboardButton("Список домофонов")
    keyboard.add(button)
    bot.send_message(message.chat.id, 'Вы успешно авторизованы!', reply_markup=keyboard)
    help(message)


def get_tenant_id(phone_number):
    payload = json.dumps({'phone' : phone_number})
    response = requests.request("POST", f'{DOMOFON_API_URL}check-tenant', headers=headers, data=payload)
    if response.status_code == 200:
        return response.json()['tenant_id']
    else:
        return None


def add_domofons(user):
    tenant_id = user.tenant_id

    response_apartments = requests.get(f'{DOMOFON_API_URL}domo.apartment?tenant_id={tenant_id}', headers=headers)

    if response_apartments.status_code == 200:
        apartments = response_apartments.json()
        if apartments:
            for apartment in apartments:
                response_domofons = requests.get(f'{DOMOFON_API_URL}domo.apartment/{apartment["id"]}/domofon?tenant_id={tenant_id}', headers=headers)
                if response_domofons.status_code == 200:
                    domofons = response_domofons.json()
                    for domofon in domofons:
                        if session.query(models.Domofon).filter_by(domofon_id=domofon['id'], user_id=tenant_id).first():
                            continue
                        domofon_record = models.Domofon(user_id=tenant_id, domofon_name=domofon['name'], domofon_id=domofon['id'])
                        session.add(domofon_record)
                else:
                    return

            session.commit()
        else:
            return
    else:
        return
    

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
        bot.send_message(message.chat.id, 'У вас нет доступных домофонов.')

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

    if response.status_code != 200:
        bot.send_message(message.chat.id, 'Ошибка получения снимков.')
        return

    photo1 = response.json()[0].get('jpeg')
    photo2 = response.json()[0].get('alt_jpeg')

    if not photo1 and not photo2:
        bot.send_message(message.from_user.id, 'У домофона нет камер.')
        return

    # Проверка изображений
    valid_photos = []
    if photo1 and check_image_url(photo1):
        valid_photos.append(telebot.types.InputMediaPhoto(photo1, caption=f'Снимки с домофона id={domofon_id}'))
    if photo2 and check_image_url(photo2):
        valid_photos.append(telebot.types.InputMediaPhoto(photo2))

    if valid_photos:
        bot.send_media_group(message.from_user.id, media=valid_photos)
    else:
        bot.send_message(message.chat.id, 'Не удалось получить действительные изображения.')


def check_image_url(url):
    response = requests.get(url)
    if response.status_code != 200:
        return None
    return url

# Команда для открытия домофона
@bot.message_handler(commands=['open'])
def open_domofon(message):
    user = session.query(models.User).filter_by(telegram_id=message.from_user.id).first()
    if user is None:
        bot.send_message(message.chat.id, 'Вы не авторизованы. Пожалуйста, отправьте свой номер телефона с помощью команды /start.')
        return
    tenant_id = user.tenant_id

    msg = message.text.split()
    if len(msg) != 3:
        bot.send_message(message.chat.id, 'Используйте: /open <id_домофона> <номер_двери>')
        return
    
    domofon_id = msg[1] if len(message.text.split()) > 1 else None
    door_id = msg[2] if len(message.text.split()) > 1 else None

    if not domofon_id or not door_id:
        bot.send_message(message.chat.id, 'Используйте: /open <id_домофона> <номер_двери>')
        return

    valid_intercom = session.query(models.Domofon).filter_by(domofon_id=domofon_id, user_id=tenant_id).first()
    if valid_intercom is None:
        bot.send_message(message.chat.id, 'Вам не доступен этот домофон или такого домофона не сущесвтует.')
        return

    payload = json.dumps({'door_id' : door_id})

    url = f'{DOMOFON_API_URL}domo.domofon/{domofon_id}/open?tenant_id={tenant_id}'
    response = requests.post(url, headers=headers, data=payload)

    if response.status_code == 200:
        bot.send_message(message.chat.id, f'Домофон id = {domofon_id} успешно открыт!')
    else:
        error_message = 'Ошибка при открытии двери.'
        bot.send_message(message.chat.id, error_message)



# Команда помощи
@bot.message_handler(commands=['help'])
def help(message):
    msg_text = ("Доступные команды:\n"
    "/start - Начать работу с ботом\n"
    "/help - Показать это меню помощи\n"
    "/list - Показать список доступных домофонов\n"
    "/open <id_домофона> <номер_двери> - Открыть указанную дверь домофона\n"
    "/snapshot <id_домофона> - Отправить снимки с указанного домофона\n")
    bot.send_message(message.chat.id, msg_text)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text
    
    if text == 'Список домофонов':
        list_domofons(message)
    else:
        bot.send_message(message.chat.id, 'Я не знаю такой команды.\nВведите /help, чтобы узнать список доступных команд.')


class CallNotification(BaseModel):
    domofon_id: int
    tenant_id: int
    
@app.post("/notify_call/")
async def notify_call(notification: CallNotification):
    # Проверяем, существует ли домофон и доступен ли он для пользователя
    domofon = session.query(models.Domofon).filter_by(domofon_id=notification.domofon_id, user_id=notification.tenant_id).first()
    if not domofon:
        raise HTTPException(status_code=404, detail="Домофон не найден или недоступен")
    # Получаем снимок с камеры домофона
    payload = json.dumps({'intercoms_id': [notification.domofon_id], 'media_type': ['JPEG']})
    response = requests.post(f'{DOMOFON_API_URL}domo.domofon/urlsOnType?tenant_id={notification.tenant_id}', headers=headers, data=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Ошибка получения снимка с камеры")
    photo_url1 = response.json()[0]['jpeg']
    photo_url2 = response.json()[0]['alt_jpeg']
    if not photo_url1 or not photo_url2:
        raise HTTPException(status_code=404, detail="У домофона нет камер")
    
    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton("Открыть", callback_data=f'open_{notification.domofon_id}_{notification.tenant_id}')
    keyboard.add(button)
    
    # Отправляем сообщение пользователю в Telegram
    chat_id = domofon.user.telegram_id  # Получаем ID чата пользователя
    snapshot = [telebot.types.InputMediaPhoto(photo_url1 , caption="Кто-то звонит в домофон!"), 
                telebot.types.InputMediaPhoto(photo_url2)]

    bot.send_media_group(chat_id, snapshot)
    # Отправляем сообщение с клавиатурой
    bot.send_message(chat_id, "Нажмите кнопку, чтобы открыть дверь:", reply_markup=keyboard)
    return {"detail": "Уведомление отправлено"}


@bot.callback_query_handler(func=lambda call: call.data.startswith('open_'))
def handle_open(call):
    # Обработка нажатия кнопки
    domofon_id = call.data.split("_")[1]
    tenant_id = call.data.split("_")[2]
    # Проверяем, существует ли домофон
    domofon = session.query(models.Domofon).filter_by(domofon_id=domofon_id, user_id=tenant_id).first()
    if not domofon:
        raise HTTPException(status_code=404, detail="Домофон не найден или недоступен")
    # Отправляем команду на открытие двери
    door_id = 0 # Замените на реальный ID двери, если необходимо
    payload = json.dumps({'door_id': door_id})
    response = requests.post(f'{DOMOFON_API_URL}domo.domofon/{domofon_id}/open?tenant_id={tenant_id}', headers=headers, data=payload)
    if response.status_code == 200:
        return {"detail": "Дверь успешно открыта"}
    else:
        raise HTTPException(status_code=500, detail="Ошибка при открытии двери")


# Функция для запуска бота в отдельном потоке
def run_bot():
    bot.polling(none_stop=True)

# Запуск бота в отдельном потоке
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
