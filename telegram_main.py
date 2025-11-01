from config import *
from main_classes import *
import telebot
import threading
import time
import os
import logging
from flask import Flask, request
import requests
from deltachat2 import MsgData, events



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
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="html", disable_web_page_preview=True)

traductor = main_class(bot)

# Handlers de Telegram
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 *Bot de Reconocimiento de Texto OCR*

*Comandos disponibles:*
/start - Mostrar este mensaje
/help - Ayuda
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



@bot.message_handler(content_types=['photo'])
def handle_photo(message: telebot.types.Message):

    try:
        # Informar que se está procesando
        processing_msg = bot.reply_to(message, "🔄 Procesando imagen...")
        
        # Obtener la foto en la mejor calidad

        temp_dict = {message.from_user.id: {"lang": "jpn"}}

        if message.caption:
            if re.search(r"/texto\s+([^/]*?)(?=\s*/|$)", message.caption.lower()):
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
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            text=respuesta,
        )
        
        logging.info(f"OCR completado para usuario {message.from_user.id}")
        
    except Exception as e:
        error_msg = f"❌ Error al procesar la imagen: {str(e)}"
        bot.reply_to(message, error_msg)
        logging.error(f"Error en handle_photo: {e}")



@bot.message_handler(func=lambda x: True)
def cmd_message(m):
    traductor.ia.send_message(m.text.strip(), bot, m.chat.id)


@traductor.email.on(events.RawEvent)
def log_event(bot, accid, event):
    pass
    # bot.logger.info(event)

@traductor.email.on(events.NewMessage)
def echo(bot, accid, event):

    if event.msg.text.lower().starswith("/ia"):
        if re.search(r"/ia\s+([^/]*?)(?=\s*/|$)", event.msg.text.lower()):
            traductor.ia.send_message(re.search(r"/ia\s+([^/]*?)(?=\s*/|$)", event.msg.text.lower()).group().replace("/ia", "").strip(), informacion_mensaje_correo(bot, event, accid, MsgData))

        else:
            bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="¡No has ingresado un texto para la IA!\n\nEnvíame /help para mas información"))

    elif event.msg.text.lower().starswith("/texto"):

        if not event.msg.file:
            bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="¡Debes de enviar una imagen para reconocer su texto en el interior!\n\nEnvía /help para más información"))
            return

        if not re.search(r"/texto\s+([^/]*?)(?=\s*/|$)", event.msg.text.lower()).group().replace("/lang", "").strip() in ["esp", "eng", "jpn"]:
            res = traductor.ocr.get_text(event.msg.file, "jpn")

            if res[0] == "error":
                bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="¡Ha ocurrido un error!\n\nDescripción del error:\n" + res[1]))

            else:
                bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text=res[1]))


# Función para monitorear emails en segundo pla



logging.info("Iniciando Bot de OCR...")

# Iniciar monitoreo de emails en segundo plano
threading.Thread(name="email_hilo" ,target=traductor.email.start, daemon=True).start()

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