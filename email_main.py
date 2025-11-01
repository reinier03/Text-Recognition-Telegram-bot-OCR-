from deltachat2 import MsgData, events
from deltabot_cli import BotCli
import threading
import time
import os
import logging
from flask import Flask, request
from main_classes import *
from deltachat2 import MsgData, events
from config import *
from main_classes import *
import sys


traductor = main_class(correo_only = True)


app = Flask(__name__)

@app.route("/", methods=['POST', 'GET'])
def webhook():

    return "<a href='https://t.me/mistakedelalaif'>Contáctame</a>"
        
@app.route("/healthz")
def check():
    return "200 OK"


def flask():
    app.run(host="0.0.0.0", port=5000)


try:
    print("La dirección del servidor es:{}".format(request.host_url))
    
except:
    if "serve" in sys.argv and os.environ.get("webhook_url"):
        threading.Thread(name="hilo_flask", target=flask).start()



@traductor.email.on(events.RawEvent)
def log_event(bot, accid, event):
    pass
    # bot.logger.info(event)

@traductor.email.on(events.NewMessage)
def echo(bot, accid, event):

    if "/help" in event.msg.text.lower():
        bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="""
Ayuda con los comandos:
/help - Este mensaje de ayuda
/ia [Texto] - Le pregunta a la ia según el [Texto] ingresado y devuelve una respuesta
/texto [eng | jpn] - Este comando debe ser enviado adjunto a una foto, es para transcribir el texto hayado en la imagen, por ahora los lenguajes disponibles son Inglés (eng) y Japonés (jpn)
                                                           
Este bot fué creado por Reima :D
Email -> reiniermayea@gmail.com
Telegram -> https://t.me/mistakedelalaig
""".strip()))
        return

    elif event.msg.text.lower().startswith("/ia"):
        if re.search(r"/ia\s+([^/]*?)(?=\s*/|$)", event.msg.text.lower()):
            traductor.ia.send_message(re.search(r"/ia\s+([^/]*?)(?=\s*/|$)", event.msg.text.lower()).group().replace("/ia", "").strip(), informacion_mensaje_correo(bot, event, accid), accid)

        else:
            bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="¡No has ingresado un texto para la IA!\n\nEnvíame /help para mas información"))

    elif event.msg.text.lower().startswith("/texto"):

        if not event.msg.file:
            bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="¡Debes de enviar una imagen para reconocer su texto en el interior!\n\nEnvía /help para más información"))
            return

        if re.search(r"/texto\s+([^/]*?)(?=\s*/|$)", event.msg.text.lower()).group().replace("/texto", "").strip() in ["eng", "jpn", "spa"]:
            res = traductor.ocr.get_text(event.msg.file, re.search(r"/texto\s+([^/]*?)(?=\s*/|$)", event.msg.text.lower()).group().replace("/texto", "").strip())

            

        else:
            res = traductor.ocr.get_text(event.msg.file, "auto")
        

        if res[0] == "error":
            bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="¡Ha ocurrido un error!\n\nDescripción del error:\n" + res[1]))

        else:
            bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text=res[1]))

# Función para monitorear emails en segundo pla



logging.info("Iniciando Bot de OCR...")

# Iniciar monitoreo de emails en segundo plano
traductor.email.start()

logging.info("Bot iniciado. Monitoreando Telegram y emails...")
logging.info(f"Email del bot: {EMAIL}")
