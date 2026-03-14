import os

import telebot.types
import telebot.types
from config import *
from main_classes import *
import telebot
from telebot.types import *
import threading
import time
import os
import logging
from flask import Flask, request
import requests


historial_borrar = {} #diccionario que almacenará el historial de deteccion de OCR, almacenará el ID de los mensajes para luego borrarlos y limpiar el chat



# Configurar logging
logging.basicConfig(
    # level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocr_bot.log'),
        logging.StreamHandler(),
    ],
)

# Inicializar bot de Telegram
telebot.apihelper.ENABLE_MIDDLEWARE = True
bot = TelegramBot(TELEGRAM_BOT_TOKEN, parse_mode="html", disable_web_page_preview=True)

traductor = main_class(bot)


bot.set_my_commands(
    [
        BotCommand("/start", "Ayuda sobre el bot"),
        BotCommand("/historial", "Administrar tu historial de chat con la IA"),
        BotCommand("/panel", "SOLO admin")
    ]
)

# @bot.middleware_handler()
# def middleware(bot, update):
#     pass


# Handlers de Telegram
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 *Bot de Reconocimiento de Texto OCR*

*Comandos disponibles:*
/start - Mostrar este mensaje
/help - Ayuda
/contexto - para darle contexto a la IA
/ia [Texto] - Le envía un texto a la IA para que te responda

Envíame una captura de un texto en algún idioma y te lo transcribiré / traduciré al español
Para especificar el idioma de las letras en la captura envia el texto adjunto a la foto:
*/texto jpn* para el japonés
*/texto eng* para el inglés

*Idiomas soportados:* 🇯🇵 Japonés | 🇺🇸 Inglés

*También puedes usar por email:*
Envía un email a {} con:
- Asunto o cuerpo que contenga "/ia [TEXTO]"

*Desarrollado con EasyOCR*
    """.format(EMAIL)
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')


@bot.message_handler(commands=["historial"])
def historial(m: telebot.types.Message):
    if not traductor.ia:
        bot.send_message(m.chat.id, "Ahora mismo no hay ninguna IA activada de la cual trabajar el historial")
        return 

    bot.send_message(m.chat.id, f"Aquí puedes administrar tu historial de conversacion con {traductor.ia.ia_nombre}",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Mostrar historial", callback_data="h/mostrar")],
        [InlineKeyboardButton("Limpiar historial", callback_data="h/limpiar")],
    ]))

@bot.callback_query_handler(func=lambda c: c.data == "h/limpiar")
def historial_limpiar(c):
    global traductor

    traductor.ia.mensajes_de_contexto.clear()
    bot.send_message(c.message.chat.id, "Historial de mensajes de IA limpio")

@bot.callback_query_handler(func=lambda c: c.data == "h/mostrar")
def historial_mostrar(c):
    global traductor

    if traductor.ia.mensajes_de_contexto:
        bot.send_message(c.message.chat.id, "\n\n--------------------------------\n\n".join(diccionario_valores["content"] for diccionario_valores in traductor.ia.mensajes_de_contexto))

    else:
        bot.send_message(c.message.chat.id, "El chat está vacío")


@bot.message_handler(content_types=['photo'])
def handle_photo(message: telebot.types.Message):

    if not historial_borrar.get(message.from_user.id):
        historial_borrar[message.from_user.id] = []

    historial_borrar[message.from_user.id].append(message.message_id)

    try:
        # Informar que se está procesando
        processing_msg = bot.reply_to(message, "🔄 Procesando imagen...")
        
        # Obtener la foto en la mejor calidad

        temp_dict = {message.from_user.id: {"lang": "jpn"}}

        if message.caption:
            if re.search(r"/texto\s+([^/]*?)(?=\s*/|$)", message.caption.lower()):
                if  re.search(r"/texto \w+", message.caption.lower()).group().replace("/texto", "").strip() in ["eng", "jpn", "spa"]:
                    temp_dict[message.from_user.id]["lang"] = re.search(r"/texto \w+", message.caption.lower()).group().replace("/texto", "").strip()

        # Procesar la imagen
        texto_extraido = traductor.ocr.get_text(bot.download_file(bot.get_file(message.photo[-1].file_id).file_path), temp_dict[message.from_user.id]["lang"])
        
        if texto_extraido[0].lower() == "error":
            bot.send_message(message.chat.id, "ERROR:\n\n" + texto_extraido[1])
            return
        
        else:
            texto_extraido = texto_extraido[1]

        # Preparar respuesta
        respuesta = f"📝 <b>Texto reconocido:</b>\n\n<code>{texto_extraido}</code>"
        
        # Editar el mensaje de procesamiento con el resultado
        msg = bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            text=respuesta,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Limpiar Chat", callback_data="clear_" + str(message.from_user.id))]])
        )
        
        logging.info(f"OCR completado para usuario {message.from_user.id}")
        
    except Exception as e:
        msg = bot.reply_to(message, f"❌ Error al procesar la imagen: {str(e)}")
        logging.error(f"Error en handle_photo: {e}")

    historial_borrar[message.from_user.id].append(msg.message_id)

#para limpiar el chat de los OCRs
@bot.callback_query_handler(func=lambda c: c.data.startswith("clear_"))
def limpiar_chat(c: telebot.types.CallbackQuery):
    for id_mensaje in historial_borrar[int(re.search(r"\d+", c.data).group())]:
        try:
            bot.delete_message(c.message.chat.id, id_mensaje)

        except:
            pass
    
    historial_borrar[int(re.search(r"\d+", c.data).group())].clear()



# @bot.message_handler(commands=["panel"], func=lambda m: m.from_user.id == int(os.environ["admin"]))
@bot.message_handler(commands=["panel"])
def panel(m):

    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Activar IA", callback_data="p/ia") if not traductor.ia else InlineKeyboardButton("Desactivar IA", callback_data="p/ia")]
        ]
    )

    if traductor.ia:
        markup.row(InlineKeyboardButton("Cambiar IA", callback_data="p/cambiar_ia")) 
    
    # if traductor.ia and traductor.ia.mensajes_de_contexto:
    #     markup.row(InlineKeyboardButton("Ver contexto completo", callback_data="p/context"))

    bot.send_message(m.chat.id, "Hola, que pretendes hacer?", reply_markup=markup)

#------------------Para investigar acerca de kanjis
@bot.message_handler(func=lambda m: True if re.search(r"^(k:)", m.text.lower()) else False)
def buscar_kanji(m):
    m.text = m.text.lower()
    m.text = m.text.replace(" ", "")
    res = requests.get("https://kanjiapi.dev/v1/kanji/" + re.search(r"^(k:.*)", m.text).group().strip().split("k:")[-1].strip())

    #Agregar al historial de cosas por borrar
    if not historial_borrar.get(m.from_user.id):
        historial_borrar[m.from_user.id] = []

    if res.status_code == 200:
        res = json.loads(res.content)
        m = bot.send_message(m.chat.id, f"""
Kanji {res["kanji"]}

🗣Lectura(s) kun: 
<blockquote>{"\n".join([lecturas for lecturas in res["kun_readings"]])}</blockquote>

📖Significado(s) [en]:
<blockquote>{"\n".join([ significados for significados in res["meanings"]])}</blockquote>
""")
    else:
        bot.reply_to(m , "Ese kanji no existe o has ingresado los datos inválidos")

    historial_borrar[m.from_user.id].append(m.message_id)

    
@bot.callback_query_handler(func=lambda x: True)
def cmd_callback_handler(c : CallbackQuery):
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass

    if c.data == "p/ia":
        if not traductor.ia:
            traductor.ia = "openrouter"
            bot.send_message(c.message.chat.id, "Los mensajes de la IA han sido activados")

        else:
            traductor.ia = False
            bot.send_message(c.message.chat.id, "Los mensajes de la IA han sido desactivados")

    elif c.data.startswith("p/ia/c/"):
        traductor.ia = c.data.split("c/")[-1]
        bot.send_message(c.message.chat.id, "La IA de " + traductor.ia.ia_nombre + " ha sido seleccionada")
        return

    elif c.data == "p/cambiar_ia":
        bot.send_message(c.message.chat.id, "Cuál IA deseas?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(ia, callback_data="p/ia/c/" + ia)] for ia in traductor._ia_disponibles]))

    return

@bot.message_handler(func=lambda x: True and traductor.ia)
def cmd_message(m):
    global traductor

    res = traductor.ia.send_message(m.text.strip(), bot, m.chat.id)

    if res:
        traductor.ia.agregar_contexto(m.text.strip())
        traductor.ia.agregar_contexto(res)

# Función para monitorear emails en segundo plano
def email_monitor():
    """
    Monitorear emails en intervalos regulares
    """
    while True:
        try:
            traductor.procesar_emails()
            time.sleep(30)  # Verificar cada 30 segundos
        except Exception as e:
            logging.error(f"Error en monitoreo de emails: {e}")
            time.sleep(60)


if __name__ == "__main__":
    logging.info("Iniciando Bot de OCR...")
    
    # Iniciar monitoreo de emails en segundo plano
    email_thread = threading.Thread(target=email_monitor, daemon=True)
    email_thread.start()
    
    logging.info("Bot iniciado. Monitoreando Telegram y emails...")
    logging.info(f"Email del bot: {EMAIL}")

        


app = Flask(__name__)

@app.route("/", methods=['POST', 'GET'])
def webhook():

    
    if request.method.lower() == "post":   
        
            
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            try:
                if "host" in update.message.text and update.message.chat.id == admin:
                    bot.send_message(update.message.chat.id, "El url del host es: <code>{}</code>".format(request.url))
                    
                    #en los host gratuitos, cuando pasa un tiempo de inactividad el servicio muere, entonces hago este GET a la url para que no muera  
                    if not list(filter(lambda i: i.name == "hilo_requests", threading.enumerate())):
                        
                        def hilo_requests():
                            while True:
                                requests.get(os.getenv("webhook_url"))
                                time.sleep(60)
                                

                        threading.Thread(target=hilo_requests, name="hilo_requests").start()

            except:
                pass
            
            bot.process_new_updates([update])


    else:
        return "<a href='https://t.me/{}'>Contáctame</a>".format(bot.user.username)
        
    return "<a href='https://t.me/{}'>Contáctame</a>".format(bot.user.username)

@app.route("/healthz")
def check():
    return "200 OK"


def flask():
    if os.getenv("webhook_url"):
        bot.remove_webhook()
        time.sleep(2)
        bot.set_webhook(url=os.environ["webhook_url"])
    
    app.run(host="0.0.0.0", port=5000)


try:
    print("La dirección del servidor es:{}".format(request.host_url))
    
except:
    hilo_flask=threading.Thread(name="hilo_flask", target=flask)
    hilo_flask.start()
    
if not os.getenv("webhook_url"):
    bot.remove_webhook()
    time.sleep(2)
    if os.environ.get("admin"):
        bot.send_message(admin, "El bot de reconocimiento de texto está listo :)\n\nEstoy usando el método polling")
    
    try:
        bot.infinity_polling(timeout=80,)
    except Exception as e:
        logging.error(f"Error en bot de Telegram: {e}")