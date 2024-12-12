from dotenv import load_dotenv
import os
load_dotenv()

username_app = os.getenv('USERNAME_APP')
password_app = os.getenv('PASSWORD_APP')
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set.")