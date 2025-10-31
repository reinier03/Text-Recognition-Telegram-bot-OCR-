from deeply import arliaiAPI
from config import *
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import Message
import logging
from logging import *
import os
from asyncio.events import get_event_loop
from asyncio.tasks import sleep
from DeeperSeek.internal.exceptions import *
import re
import requests
import json


class OCR:

    def get_text(self, file: str | bytes, language = "ja", remove_file = True):


        payload = {'isOverlayRequired': False,
        'apikey': ocr_token,
        'language': language,
        }


        if isinstance(file, bytes):
            with open("archivo.png", 'wb') as f:
                f.write(file)
                file = f.name


        with open(file, 'rb') as f:
            res = requests.post('https://api.ocr.space/parse/image', files={f.name: f}, data=payload)

        
        if remove_file:
            os.remove(file)

        if res.status_code == 200:
            return ("ok", json.loads(res.content)["ParsedResults"][0]["ParsedText"].strip())

        else:
            return ("error", res.reason)



class main_class:  

    def __init__(self, bot):
        self.processed_emails = set()
        self.bot = bot 
        self.intentos_red = 7
        self.ia = arliaiAPI(arliai_token)
        self.ocr = OCR()



    def enviar_respuesta_email(self, destinatario, texto_respuesta, asunto="", intentos_red = 7):
        """
        Enviar respuesta por correo electrónico
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL
            msg['To'] = destinatario
            msg['Subject'] = asunto
            
            # Cuerpo del mensaje
            cuerpo = MIMEText(texto_respuesta, 'plain', 'utf-8')
            msg.attach(cuerpo)
            
            # Enviar email
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL, EMAIL_PASSWORD)
                server.send_message(msg)
            
            logging.info(f"Email enviado a {destinatario}")
            return True
            
        except Exception as e:
            if "Network is unreachable" in str(e.args):
                if intentos_red > 0:
                    return self.enviar_respuesta_email(destinatario, texto_respuesta, asunto, intentos_red - 1)
                else:
                    pass

            logging.error(f"Error enviando email: {e}")
            return False
    
    def procesar_emails(self):
        """
        Verificar y procesar nuevos emails
        """
        try:
            # Conectar al servidor IMAP
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(EMAIL, EMAIL_PASSWORD)
            mail.select('inbox')
            
            # Buscar emails no leídos
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()
            
            for email_id in email_ids:
                if email_id in self.processed_emails:
                    continue
                    
                # Marcar como procesado
                self.processed_emails.add(email_id)
                
                # Obtener el email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                email_body = msg_data[0][1]
                mail_message = email.message_from_bytes(email_body)
                
                # Procesar el email
                self._procesar_email_individual(mail_message)
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            logging.error(f"Error procesando emails: {e}")
    
    def _procesar_email_individual(self, mail_message: Message, intentos_red = 7):
        """
        Procesar un email individual
        """
        try:
            # Obtener remitente y asunto
            remitente = mail_message['from']
            asunto = mail_message['subject'] or ""
            
            logging.info(f"Procesando email de: {remitente} - Asunto: {asunto}")
            
            texto = self._es_comando_ocr(mail_message)

            if not texto:
                return False

            texto = texto.lower()

            if "/help" in texto:

                self.enviar_respuesta_email(remitente, """
Comandos Disponibles:
/help - Esta ayuda
/texto [eng | jpn] - Este comando es para transcribir el texto de una foto, la foto debe estar adjunta al mensaje, las letras envueltas en las llaves son para especificar el idioma de transcripción [inglés | japonés]
/ia [Texto de la Solicitud] - Le envía el texto a la IA, se te responderá lo antes posible (No incluyas las llaves en el texto)
""".strip(),)
                return

# /texto [/lang] - Este texto va adjunto a una imagen para transcribir dicha imagen
# /lang [en|ja] - Este comando va con /texto, es para definir el lenguaje en el que se encuentra el texto en la imagen, por ahora solo soportamos japones e inglés
            
                

            elif "/ia" in texto.lower():
                if re.search(r"/ia\s+([^/]*?)(?=\s*/|$)", texto.lower()):
                    self.ia.send_message(re.search(r"/ia\s+([^/]*?)(?=\s*/|$)", texto.lower()).group().replace("/ia", "").replace("/", "").strip(), "correo", remitente)

                    return


                else:
                    self.enviar_respuesta_email(remitente, "No has ingresado un texto válido luego de /ia\n\nEnvíame /help para obtener ayuda")

                    return
                
            
            #Buscar imágenes adjuntas
            imagen_data = self._extraer_imagenes_email(mail_message)

            mail_message['datos'] = {"lang": "jpn"}
            
            if imagen_data:
                texto = self._es_comando_ocr(mail_message)

                if re.search(r"/texto\s+([^/]*?)(?=\s*/|$)", texto.lower()):
                    mail_message['datos']["lang"] = re.search(r"/texto\s+([^/]*?)(?=\s*/|$)", texto.lower()).group().replace("/texto", "").strip()

                # Procesar OCR
                texto_extraido = self.ocr.get_text(imagen_data, mail_message['datos']["lang"])
                

                if texto_extraido[0] == "error":
                    self.enviar_respuesta_email(remitente, "ERROR:\n\n" + texto_extraido[1])
                    return texto_extraido
                
                else:
                    texto_extraido = texto_extraido[1]
                # Preparar respuesta
                # respuesta = f"Texto extraído de la imagen:\n\n{texto_extraido}"
                
                # Enviar respuesta
                self.enviar_respuesta_email(remitente, texto_extraido)
                
                logging.info(f"OCR completado para email de {remitente}")
            else:
                self.enviar_respuesta_email(
                    remitente, 
                    "No se encontró ninguna imagen adjunta en el email. Por favor, adjunta una imagen con texto."
                )
                
        except Exception as e:
            if "Network is unreachable" in str(e.args):
                if intentos_red > 0:
                    return self._procesar_email_individual(mail_message, intentos_red - 1)
                
            
            logging.error(f"Error procesando email individual: {e}")

            try:
                self.enviar_respuesta_email(
                    remitente,
                    f"Error al procesar tu solicitud: {str(e)}"
                )
            except:
                pass
    
    def verificar_comandos(self, texto, cantidad_permitidos = 1):

        if tuple(filter(lambda comando, texto=texto: comando in texto.lower(), ["/texto", "/ia", "/help"])):
            return texto
            

        else:
            False

    def _es_comando_ocr(self, mail_message: Message, cantidad_permitidos = 1):
        """
        Verificar si el email contiene el comando de OCR
        """

        

        try:

            # Verificar asunto
            asunto = mail_message['subject'] or ""
            if "/texto" in asunto.lower():
                return self.verificar_comandos(cuerpo, cantidad_permitidos)
            
            # Verificar cuerpo del mensaje
            if mail_message.is_multipart():
                for part in mail_message.walk():
                    if part.get_content_type() == "text/plain":
                        cuerpo = part.get_payload(decode=True).decode('utf-8', errors='ignore').lower()
                        return self.verificar_comandos(cuerpo, cantidad_permitidos)

                        
            else:
                cuerpo = mail_message.get_payload(decode=True).decode('utf-8', errors='ignore').lower()
                return self.verificar_comandos(cuerpo, cantidad_permitidos)
            
            return False
            
        except Exception as e:
            logging.error(f"Error verificando comando OCR: {e}")
            return False
    
    def _extraer_imagenes_email(self, mail_message: Message):
        """
        Extraer imágenes del email
        """
        try:
            if mail_message.is_multipart():
                for part in mail_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    # Buscar imágenes adjuntas
                    if "image" in content_type and "attachment" in content_disposition:
                        imagen_data = part.get_payload(decode=True)
                        if imagen_data:
                            return imagen_data
                    
                    # Buscar imágenes inline
                    elif "image" in content_type and "inline" in content_disposition:
                        imagen_data = part.get_payload(decode=True)
                        if imagen_data:
                            return imagen_data
            
            return None
            
        except Exception as e:
            logging.error(f"Error extrayendo imágenes del email: {e}")
            return None
