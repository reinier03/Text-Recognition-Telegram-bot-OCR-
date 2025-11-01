import os
from config import *
import subprocess as s

delay = (os.environ["delay"] if os.environ.get("delay") else 10)

def comando(cmd):
    return s.run(cmd, stderr=s.PIPE, stdout=s.PIPE, shell=True, universal_newlines=True).stdout

if os.name == "nt":
    python_str = "python"

else:
    python_str = "python3"

if not EMAIL in comando('{} email_main.py list'.format(python_str)):
    os.system('{} email_main.py init {} "{}"'.format(python_str, EMAIL, EMAIL_PASSWORD))  

os.system('{} email_main.py config scan_all_folders_debounce_secs {}'.format(python_str, delay)) 

os.system('{} email_main.py serve'.format(python_str))