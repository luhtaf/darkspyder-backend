from dotenv import load_dotenv
from cryptography.fernet import Fernet
import os, requests

load_dotenv()

app_secret = os.getenv('APP_SECRET')
fernet = Fernet(app_secret)
data =  {"token":"763373424:9kptk7oa", "request":"boyneh@ymail.com"}
token = 'gAAAAABnPJw5B5RlAH3ym7MmO7pJpTmkOOoUtwPuwD3Wd8PN1N7x-oNeFuHfUrD2MP8VfCAKGh7bjrRJw26k5uAKPZIMMzVkPo1GPo4Tjy8pWWzqw3xjC7Y='
new_token = fernet.decrypt(token.encode()).decode()
response = requests.post(new_token, json=data)
datajson= response.json()