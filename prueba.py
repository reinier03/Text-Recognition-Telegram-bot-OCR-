import telebot 
from telebot.types import *
import os
import requests
import re
import json

bot = telebot.TeleBot(os.environ["token"], parse_mode="html", disable_web_page_preview=True)

@bot.message_handler(func=lambda m: True if re.search(r"^(k:)", m.text.lower()) else False)
def buscar_kanji(m):
    m.text = m.text.lower()
    res = requests.get("https://kanjiapi.dev/v1/kanji/" + re.search(r"^(k:.*)", m.text).group().strip().split("k:")[-1].strip())

    if res.status_code == 200:
        res = json.loads(res.content)
        bot.send_message(m.chat.id, f"""
Kanji {res["kanji"]}

🗣Lectura(s) kun: 
<blockquote expandable>{"\n".join([lecturas for lecturas in res["kun_readings"]])}</blockquote>

📖Significado(s) [en]:
<blockquote expandable>{"\n".join([ significados for significados in res["meanings"]])}</blockquote>
""")
    else:
        bot.reply_to(m , "Ese kanji no existe o has ingresado los datos inválidos")


@bot.message_handler(func=lambda x: True )
def cmd_message(m):
    print("asdasd")

bot.infinity_polling()