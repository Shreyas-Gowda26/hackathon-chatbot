from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if api_key:
    print("✅ .env file is working!")
    print(f"   API Key found: {api_key[:10]}...") # Shows first 10 chars only
else:
    print("❌ .env file NOT working or API key not set")