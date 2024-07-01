import requests
import telebot
import json
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import re

TELEGRAM_TOKEN = ''
COZE_TOKEN = ''
BOT_ID = ''

bot = telebot.TeleBot(TELEGRAM_TOKEN)

chat_histories = {}

def call_coze_api(user_id, query, chat_history, message=None):
    url = 'https://api.coze.com/open_api/v2/chat'
    headers = {
        'Authorization': f'Bearer {COZE_TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        'bot_id': BOT_ID,
        'user': str(user_id),
        'query': query,
        'stream': True,
        'chat_history': chat_history
    }
    response = requests.post(url, headers=headers, json=data, stream=True)

    if response.status_code != 200:
        print(f"Error: {response.status_code}, {response.text}")
        return

    full_message = ""
    previous_message = ""
    last_update_time = time.time()
    follow_up_questions = []

    for line in response.iter_lines():
        if line:
            try:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data:"):
                    decoded_line = decoded_line[5:]  # Убираем префикс "data:"
                print(f"Decoded Line: {decoded_line}")  # Логирование содержимого строки
                json_line = json.loads(decoded_line)
                if 'message' in json_line:
                    message_content = json_line['message']
                    content = message_content['content']
                    if message_content['type'] == 'follow_up':
                        follow_up_questions.append(content)
                    elif message_content['type'] == 'answer':
                        if "{" in content and "}" in content:
                            content = json.loads(content).get('data', content)
                        full_message += content

                    current_time = time.time()
                    if current_time - last_update_time >= 2:
                        if full_message != previous_message and message:
                            try:
                                bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id,
                                                      text=full_message)
                                previous_message = full_message
                                last_update_time = current_time
                            except telebot.apihelper.ApiTelegramException as e:
                                if e.result.status_code == 429:
                                    retry_after = int(e.result.json()['parameters']['retry_after'])
                                    print(f"Too Many Requests: retry after {retry_after} seconds")
                                    time.sleep(retry_after)
                                else:
                                    raise e
                time.sleep(0.00001)  
            except json.JSONDecodeError as e:
                print(f"JSON Decode Error: {e}")
                continue

   
    full_message = apply_markdown(full_message)

    
    markup = create_markup(follow_up_questions)
    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id, text=full_message,
                          reply_markup=markup)

    return full_message, follow_up_questions


def create_markup(follow_up_questions):
    markup = InlineKeyboardMarkup()
    for question in follow_up_questions:
        try:
           
            callback_data = re.sub(r'\W+', '_', question)[:64]
            markup.add(InlineKeyboardButton(question, callback_data=callback_data))
        except Exception as e:
            print(f"Error creating button for question '{question}': {e}")
            continue
    return markup


def apply_markdown(text):
    
    text = text.replace('\n', '\n\n')  
    return text



@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Hi, I'm created by @vt72983")


@bot.message_handler(commands=['clear'])
def clear_history(message):
    user_id = message.from_user.id
    if user_id in chat_histories:
        del chat_histories[user_id]
    bot.reply_to(message, "The current dialog has been cleared!")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    query = message.text

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append({'role': 'user', 'content': query, 'content_type': 'text'})

    
    sent_message = bot.reply_to(message, "Request processing...")

    
    call_coze_api(user_id, query, chat_histories[user_id], sent_message)

    
    chat_histories[user_id].append({'role': 'assistant', 'content': "Request has been processed.", 'content_type': 'text'})


@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    query = call.data

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append({'role': 'user', 'content': query, 'content_type': 'text'})

   
    sent_message = bot.send_message(call.message.chat.id, "Request processing...")

    
    call_coze_api(user_id, query, chat_histories[user_id], sent_message)

   
    chat_histories[user_id].append({'role': 'assistant', 'content': "Request has been processed.", 'content_type': 'text'})


if __name__ == '__main__':
    bot.polling(none_stop=True)
 
