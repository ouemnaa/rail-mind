
import os
import sys
from dotenv import load_dotenv
from groq import Groq

# Load .env
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

print(f"Testing Groq API with model: {model}")
print(f"API Key present: {bool(api_key)}")
if api_key:
    print(f"API Key preview: {api_key[:10]}...")

try:
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Hello, simply reply with 'OK'."}
        ],
        max_tokens=10
    )
    print(f"Response: {completion.choices[0].message.content}")
    print("SUCCESS: LLM connection working.")
    
    # Save success to file
    with open("llm_test_result.txt", "w") as f:
        f.write("SUCCESS")
        
except Exception as e:
    print(f"ERROR: {str(e)}")
    # Save error to file
    with open("llm_test_result.txt", "w") as f:
        f.write(f"ERROR: {str(e)}")
