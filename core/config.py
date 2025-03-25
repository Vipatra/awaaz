import os
from dotenv import load_dotenv


load_dotenv()

TARA_API_KEY = os.getenv("TARA_API_KEY")

API_KEYS = [TARA_API_KEY]



