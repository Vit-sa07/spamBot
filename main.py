import configparser
import asyncio
import tenacity
import os
import re
from telethon.sync import TelegramClient
from telethon.events import NewMessage
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import ChannelPrivateError, InvalidBufferError
from tenacity import retry, stop_after_attempt
import g4f


# Функции для вывода
def cls_cmd():
    os.system('cls' if os.name == 'nt' else 'clear')


def gd_print(value):
    green_color = '\033[32m'
    reset_color = '\033[0m'
    result = f"\n>{green_color} {value} {reset_color}\n"
    print(result)


def bd_print(value):
    red_color = '\033[31m'
    reset_color = '\033[0m'
    result = f"\n>{red_color} {value} {reset_color}\n"
    print(result)


# Чтение конфигурации
config = configparser.ConfigParser()
config.read('settings.ini')
cls_cmd()

# Настройки Telegram
api_id = config['Telegram'].get('api_id')
api_hash = config['Telegram'].get('api_hash')
device_model = config['Telegram'].get('device_model')
app_version = config['Telegram'].get('app_version')
channel_usernames = config['Telegram'].get('channel_usernames').split(', ')
auto_join = config['Telegram'].get('auto_join').lower() == 'true'

# Настройки Proxy
# PROXY_LOGIN = config['Telegram'].get('PROXY_LOGIN')
# PROXY_PASSWORD = config['Telegram'].get('PROXY_PASSWORD')
# PROXY_IP = config['Telegram'].get('PROXY_IP')
# PROXY_PORT = config['Telegram'].get('PROXY_PORT')

# Настройки уведомлений
notification_users = config['Notifications'].get('users', '').split(', ')
notification_users = [user.strip() for user in notification_users if user]

# Инициализация клиента Telegram
client = TelegramClient('SESSION_FOR_TELEGRAM_COMMENTOR', api_id, api_hash, device_model=device_model,
                        app_version=app_version, system_version="4.16.30-vxCUSTOM")


# Функция отправки уведомлений
async def send_notifications(client, users, message_link, comment_text):
    for user in users:
        try:
            await client.send_message(user, f"Комментарий оставлен: {comment_text}\nСсылка на пост: {message_link}")
            gd_print(f"Уведомление отправлено пользователю {user}")
        except Exception as e:
            bd_print(f"Ошибка при отправке уведомления пользователю {user}: {e}")


# Обработка комментариев
async def chatgpt_ai(text):
    try:
        response = await g4f.ChatCompletion.create_async(
            model=g4f.models.default,
            messages=[{"role": "user", "content": f"""Сейчас ты играешь роль обычного пользователя в Telegram. 
            Я предоставлю тебе текст поста, на который ты должен будешь отреагировать. Реагируй кратко и эмоционально, как обычный пользователь.
            Вне зависимости от контекста предоставленного тебе текста поста ты должен отреагировать на него. 
            Никогда не говори, кто ты и зачем ты здесь. Никогда не повторяй заголовок поста. Никогда не говори, что ты готов помочь. Не используй смайлики Не используй ХЭШТЕГИ и @. Отвечай, как обычный пользователь. 
            Если ты не знаешь, как реагировать на пост или текст поста пуст или не имеет никакого смысла, то ответь только: '...'. 
            Отвечай только на том языке, который используется в посте. Помни: ты не отвечаешь, а комментируешь. Старайся именно комментировать запись.. 
            Будь саркастичным и остроумным, стеби но не оскорбляй, напиши комментарий строго ДО 15 слов, и ВАЖНО, если тебе отправляют пост на который ты не можешь дать комментрий по тем или иным причинам, отправляй комментарий который можно ассоциировать с любым постом: 

            `{text}`
            """}],
            timeout=120
        )
        gd_print(f"Коммент создан")
        print(response)
        return response
    except Exception as e:
        print(e)
        raise e


@retry(stop=stop_after_attempt(5), wait=tenacity.wait_fixed(60))
async def main():
    try:
        name = await client.get_me()
        gd_print(f"Бот запущен ({name.first_name}). Мониторим канал(ы)...")

        channel_entities = [await client.get_entity(username) for username in channel_usernames]
        commented_messages = {entity.id: set() for entity in channel_entities}

        if auto_join:
            for username in channel_usernames:
                try:
                    await client(JoinChannelRequest(username))
                    gd_print(f"Присоединились к каналу @{username}")
                except Exception as e:
                    bd_print(f"Не удалось присоединиться к каналу @{username}: {e}")

        last_comment_times = {entity.id: 0 for entity in channel_entities}

        async def handle_new_posts(event):
            loop = asyncio.get_event_loop()
            message = event.message
            for entity in channel_entities:
                if entity.id == message.peer_id.channel_id:
                    current_time = loop.time()
                    if current_time - last_comment_times[entity.id] >= 60:
                        last_comment_times[entity.id] = current_time
                        if not message.out and message.id not in commented_messages[entity.id]:
                            try:
                                comment_text = await chatgpt_ai(message.text)
                                await client.send_message(entity=entity, message=comment_text, comment_to=message)
                                message_link = f"https://t.me/{entity.username}/{message.id}"
                                if notification_users:
                                    await send_notifications(client, notification_users, message_link, comment_text)
                                commented_messages[entity.id].add(message.id)
                                gd_print(f"Комментарий оставлен.")
                            except ChannelPrivateError as e:
                                bd_print(f"Ошибка: {e}")
                            except Exception as e:
                                bd_print(f"Ошибка при комментировании: {e}")

        for entity in channel_entities:
            client.add_event_handler(handle_new_posts, event=NewMessage(incoming=True, chats=entity))

        await client.run_until_disconnected()

    except InvalidBufferError as e:
        bd_print(f"Ошибка: {e}")


if __name__ == "__main__":
    cls_cmd()
    with client:
        client.loop.run_until_complete(main())
