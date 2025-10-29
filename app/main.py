# import easyocr

# reader = easyocr.Reader(['ja','en'], gpu=False, detail = 0) # this needs to run only once to load the model into memory
# result = reader.readtext(r'D:\captura_identificar.png')

from config import *
from main_classes import *
import telebot
import easyocr
import threading
import time
import os
import logging
from datetime import datetime
from flask import Flask, request
import requests



# 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
# Configuración


# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocr_bot.log'),
        logging.StreamHandler(),
    ],
)

# Inicializar EasyOCR para japonés e inglés
reader = easyocr.Reader(['ja', 'en'], gpu=True)

# Inicializar bot de Telegram
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, "html", disable_web_page_preview=True)

bot.send_message(admin, "El bot de reconocimiento de texto está online :D")


# Inicializar el bot
ocr_bot = OCRBot(reader)

# Handlers de Telegram
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 *Bot de Reconocimiento de Texto OCR*

*Comandos disponibles:*
/start - Mostrar este mensaje
/help - Ayuda
/texto - Procesar una imagen con texto

*Idiomas soportados:* 🇯🇵 Japonés | 🇺🇸 Inglés

*También puedes usar por email:*
Envía un email a {} con:
- Asunto o cuerpo que contenga "/texto"
- Una imagen adjunta con texto

*Desarrollado con EasyOCR*
    """.format(EMAIL)
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['texto'])
def request_photo(message):
    bot.reply_to(message, "📸 Por favor, envía una imagen con texto para reconocer (japonés o inglés)")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        # Informar que se está procesando
        processing_msg = bot.reply_to(message, "🔄 Procesando imagen...")
        
        # Obtener la foto en la mejor calidad
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Procesar la imagen
        texto_extraido = ocr_bot.procesar_imagen(downloaded_file)
        
        # Preparar respuesta
        respuesta = f"📝 *Texto reconocido:*\n\n{texto_extraido}"
        
        # Editar el mensaje de procesamiento con el resultado
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            text=respuesta,
            parse_mode='Markdown'
        )
        
        logging.info(f"OCR completado para usuario {message.from_user.id}")
        
    except Exception as e:
        error_msg = f"❌ Error al procesar la imagen: {str(e)}"
        bot.reply_to(message, error_msg)
        logging.error(f"Error en handle_photo: {e}")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        # Verificar si es una imagen
        mime_type = message.document.mime_type
        if mime_type and mime_type.startswith('image/'):
            # Informar que se está procesando
            processing_msg = bot.reply_to(message, "🔄 Procesando imagen adjunta...")
            
            # Descargar el archivo
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Procesar la imagen
            texto_extraido = ocr_bot.procesar_imagen(downloaded_file)
            
            # Preparar respuesta
            respuesta = f"📝 <b>Texto reconocido:</b>\n\n<code>{texto_extraido}</code>"
            
            # Editar el mensaje de procesamiento con el resultado
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=processing_msg.message_id,
                text=respuesta,
            )
        else:
            bot.reply_to(message, "❌ Por favor, envía una imagen (JPEG, PNG, etc.)")
            
    except Exception as e:
        error_msg = f"❌ Error al procesar el documento: {str(e)}"
        bot.reply_to(message, error_msg)
        logging.error(f"Error en handle_document: {e}")

# Función para monitorear emails en segundo plano
def email_monitor():
    """
    Monitorear emails en intervalos regulares
    """
    while True:
        try:
            ocr_bot.procesar_emails()
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
        bot.send_message(admin, "El bot de publicaciones de Facebook está listo :)\n\nEstoy usando el método polling")
    
    try:
        bot.infinity_polling(timeout=80,)
    except Exception as e:
        logging.error(f"Error en bot de Telegram: {e}")