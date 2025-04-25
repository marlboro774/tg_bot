import os
from dotenv import load_dotenv

load_dotenv('token')
TG_TOKEN = os.getenv('TG_TOKEN')
