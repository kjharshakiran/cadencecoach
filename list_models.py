import os
from dotenv import load_dotenv
from google.genai import Client

load_dotenv()

client = Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Listing models...")
for model in client.models.list(config={"page_size": 100}):
    print(f"Model: {model.name}")
    # print(f"  Supported methods: {model.supported_generation_methods}")
