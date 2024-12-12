from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os
load_dotenv()
app_secret = os.getenv('APP_SECRET')

# Ensure that APP_SECRET exists
if not app_secret:
    raise ValueError("APP_SECRET environment variable is not set.")
fernet = Fernet(app_secret)