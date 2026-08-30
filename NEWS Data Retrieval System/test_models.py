import os
from dotenv import load_dotenv
from google import genai

load_dotenv('backend/.env')

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

print("Listing embedding models:")
for model in client.models.list():
    if "embed" in model.name.lower():
        print(model.name)
