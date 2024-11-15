import logging
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Константы
TELEGRAM_API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
DOMOFON_API_URL = 'https://domo-dev.profintel.ru/tg-bot/api'  # Замените на реальный URL API домофона

# Команда /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Добро пожаловать! Пожалуйста, авторизуйтесь с помощью команды /login <номер_телефона>.')

# Команда для авторизации пользователя
def login(update: Update, context: CallbackContext) -> None:
    if len(context.args) != 1:
        update.message.reply_text('Используйте: /login <номер_телефона>')
        return

    phone_number = context.args[0]
    response = requests.post(f'{DOMOFON_API_URL}/auth', json={'phone': phone_number})

    if response.status_code == 200:
        update.message.reply_text('Вы успешно авторизованы!')
        context.user_data['phone'] = phone_number
    else:
        error_message = response.json().get('error', 'Ошибка авторизации.')
        update.message.reply_text(error_message)

# Команда для получения списка домофонов
def list_domofons(update: Update, context: CallbackContext) -> None:
    if 'phone' not in context.user_data:
        update.message.reply_text('Сначала авторизуйтесь с помощью /login.')
        return

    response = requests.get(f'{DOMOFON_API_URL}/domofons?phone={context.user_data["phone"]}')
    
    if response.status_code == 200:
        domofons = response.json()
        if domofons:
            message = "Список доступных домофонов:\n"
            for domofon in domofons:
                message += f"{domofon['id']}: {domofon['name']}\n"
            update.message.reply_text(message)
        else:
            update.message.reply_text('Нет доступных домофонов.')
    else:
        error_message = response.json().get('error', 'Ошибка получения списка домофонов.')
        update.message.reply_text(error_message)

# Команда для получения снимка с камеры домофона
def get_camera_snapshot(update: Update, context: CallbackContext) -> None:
    if 'phone' not in context.user_data:
        update.message.reply_text('Сначала авторизуйтесь с помощью /login.')
        return

    if len(context.args) != 1:
        update.message.reply_text('Используйте: /snapshot <id_домофона>')
        return

    domofon_id = context.args[0]
    response = requests.get(f'{DOMOFON_API_URL}/domofons/{domofon_id}/snapshot?phone={context.user_data["phone"]}')

    if response.status_code == 200:
        snapshot_url = response.json().get('snapshot_url')
        update.message.reply_photo(photo=snapshot_url)
    else:
        error_message = response.json().get('error', 'Ошибка получения снимка.')
        update.message.reply_text(error_message)

# Команда для открытия домофона
def open_domofon(update: Update, context: CallbackContext) -> None:
    if 'phone' not in context.user_data:
        update.message.reply_text('Сначала авторизуйтесь с помощью /login.')
        return

    if len(context.args) != 1:
        update.message.reply_text('Используйте: /open <id_домофона>')
        return

    domofon_id = context.args[0]
    response = requests.post(f'{DOMOFON_API_URL}/domofons/{domofon_id}/open', json={'phone': context.user_data['phone']})

    if response.status_code == 200:
        update.message.reply_text('Дверь открыта!')
    else:
        error_message = response.json().get('error', 'Ошибка открытия двери. Возможно, у вас нет доступа.')
        update.message.reply_text(error_message)

def main() -> None:
    updater = Updater(TELEGRAM_API_TOKEN)

    # Получаем диспетчер для регистрации обработчиков
    dispatcher = updater.dispatcher

    # Регистрация обработчиков команд
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("login", login))
    dispatcher.add_handler(CommandHandler("list", list_domofons))
    dispatcher.add_handler(CommandHandler("snapshot", get_camera_snapshot))
    dispatcher.add_handler(CommandHandler("open", open_domofon))

    # Запуск бота
    updater.start_polling()

    # Ожидание завершения работы
    updater.idle()

if __name__ == '__main__':
    main()
