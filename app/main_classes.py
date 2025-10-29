import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.message import Message
import numpy as np
from PIL import Image
import io
from config import *
import logging
from easyocr import Reader


class OCRBot:

    def __init__(self, reader: Reader):
        self.processed_emails = set()
        self.reader = reader
        
    def procesar_imagen(self, image_data):
        """
        Procesar imagen y extraer texto usando EasyOCR
        """
        try:
            # Convertir datos de imagen a formato numpy
            if isinstance(image_data, bytes):
                image = Image.open(io.BytesIO(image_data))
            else:
                image = image_data
                
            image_np = np.array(image)
            
            # Realizar OCR
            resultados = self.reader.readtext(image_np)
            
            # Filtrar resultados con buena confianza y unir texto
            textos = []
            for (bbox, texto, confianza) in resultados:
                if confianza > 0.4:  # Filtro de confianza
                    textos.append(texto)
            
            texto_completo = "\n".join(textos)
            return texto_completo if texto_completo else "No se pudo detectar texto en la imagen."
            
        except Exception as e:
            logging.error(f"Error procesando imagen: {e}")
            return f"Error al procesar la imagen: {str(e)}"
    
    def enviar_respuesta_email(self, destinatario, texto_respuesta, asunto="Resultado OCR"):
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
    
    def _procesar_email_individual(self, mail_message: Message):
        """
        Procesar un email individual
        """
        try:
            # Obtener remitente y asunto
            remitente = mail_message['from']
            asunto = mail_message['subject'] or ""
            
            logging.info(f"Procesando email de: {remitente} - Asunto: {asunto}")
            
            # Verificar si es un comando de OCR
            if not self._es_comando_ocr(mail_message):
                return
            
            # Buscar imágenes adjuntas
            imagen_data = self._extraer_imagenes_email(mail_message)
            
            if imagen_data:
                # Procesar OCR
                texto_extraido = self.procesar_imagen(imagen_data)
                
                # Preparar respuesta
                respuesta = f"Texto extraído de la imagen:\n\n{texto_extraido}"
                
                # Enviar respuesta
                self.enviar_respuesta_email(remitente, respuesta)
                
                logging.info(f"OCR completado para email de {remitente}")
            else:
                self.enviar_respuesta_email(
                    remitente, 
                    "No se encontró ninguna imagen adjunta en el email. Por favor, adjunta una imagen con texto."
                )
                
        except Exception as e:
            logging.error(f"Error procesando email individual: {e}")
            try:
                self.enviar_respuesta_email(
                    remitente,
                    f"Error al procesar tu solicitud: {str(e)}"
                )
            except:
                pass
    
    def _es_comando_ocr(self, mail_message: Message):
        """
        Verificar si el email contiene el comando de OCR
        """
        try:
            # Verificar asunto
            asunto = mail_message['subject'] or ""
            if "/texto" in asunto.lower():
                return True
            
            # Verificar cuerpo del mensaje
            if mail_message.is_multipart():
                for part in mail_message.walk():
                    if part.get_content_type() == "text/plain":
                        cuerpo = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        if "/texto" in cuerpo.lower():
                            return True
            else:
                cuerpo = mail_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                if "/texto" in cuerpo.lower():
                    return True
            
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