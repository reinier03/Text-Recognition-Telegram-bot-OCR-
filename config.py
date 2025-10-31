import os

TELEGRAM_BOT_TOKEN = os.environ["token"]
EMAIL = os.environ["email"]
EMAIL_PASSWORD = os.environ["email_pass"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
admin = int(os.environ["admin"]) if os.environ.get("admin") else 1413725506
# deepseek_usertoken = os.environ["deepseek_usertoken"] 
# deepseek_api = os.environ["deepseek_api"] if os.environ.get("deepseek_api") else None

#https://www.arliai.com/ 
arliai_token = os.environ["arliai_token"] if os.environ.get("arliai_token") else None

# https://ocr.space/
ocr_token = os.environ["ocr_token"] if os.environ.get("ocr_token") else None

if os.environ.get("RENDER_EXTERNAL_URL") and not os.environ.get("webhook_url"):
    os.environ["webhook_url"] = os.environ["RENDER_EXTERNAL_URL"]
