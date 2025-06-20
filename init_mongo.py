import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'darkspyder')

class MongoDB:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.accounts = self.db.account
    
    def get_accounts_collection(self):
        return self.accounts
    
    def close_connection(self):
        self.client.close()

# Global MongoDB instance
mongo_db = MongoDB()
