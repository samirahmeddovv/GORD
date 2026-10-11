import time
import requests
import psutil
import keyboard
import threading
import os
import subprocess
import sounddevice as sd
import wave
import numpy as np
import pynvml

# NVML (GPU) sistemini işə salırıq
try:
    pynvml.nvmlInit()
except Exception as e:
    print("GPU Başlatma xətası:", e)

TOKEN = "Token"
CHAT_ID = "Chat_ID"
AUDIO_PATH = "alert_voice.wav"
FLASK_URL = "http://127.0.0.1:5000/api/upload"

def wait_for_internet():
    while True:
        try:
            requests.get("https://www.google.com", timeout=3)
            break 
        except:
            time.sleep(5)

wait_for_internet()

def send_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("Mesaj xətası:", e)

def lock_pc():
    try:
        subprocess.run(["powershell", "-Command", "(New-Object -ComObject Shell.Application).MinimizeAll(); rundll32.exe user32.dll,LockWorkStation"], shell=True)
    except Exception as e:
        print("Kilidləmə xətası:", e)

def record_and_send_audio():
    try:
        duration = 6
        fs = 44100
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype=np.int16)
        sd.wait()
        
        with wave.open(AUDIO_PATH, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fs)
            wf.writeframes(audio.tobytes())
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendVoice"
        with open(AUDIO_PATH, 'rb') as f:
            files = {'voice': f}
            data = {'chat_id': CHAT_ID, 'caption': '🎙️ Təhlükə anında ətrafdakı səslər:'}
            requests.post(url, data=data, files=files, timeout=10)
        
        if os.path.exists(AUDIO_PATH):
            os.remove(AUDIO_PATH)
    except Exception as e:
        print("Səs qeyd xətası:", e)

def send_telegram_alert(message):
    send_msg(f"🚨 *TƏHLÜKƏ XƏBƏRDARLIĞI!*\n{message}")
    threading.Thread(target=record_and_send_audio, daemon=True).start()

def is_locked():
    return any(p.info['name'] == 'LogonUI.exe' for p in psutil.process_iter(['name']))

def get_ip_info():
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5).json()
        ip = r.get("ip", "Naməlum")
        city = r.get("city", "Naməlum")
        country = r.get("country", "Naməlum")
        org = r.get("org", "Naməlum")
        return f"🌍 *Şəbəkə Məlumatı:*\n- IP: `{ip}`\n- Şəhər/Ölkə: {city}, {country}\n- Provayder: {org}"
    except:
        return "IP məlumatı əldə edilmədi."

# Telemetriya məlumatlarını Flask serverinə göndərən fon funksiyası
def send_telemetry_to_server():
    while True:
        try:
            cpu_pct = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            
            # GPU məlumatları
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            gpu_pct = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
            gpu_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            battery = psutil.sensors_battery()
            battery_pct = battery.percent if battery else 100
            locked = is_locked()

            payload = {
                "device_id": "samir_pc_01",
                "device_name": "Samir Laptop",
                "cpu_pct": cpu_pct,
                "ram_pct": ram,
                "gpu_pct": gpu_pct,
                "gpu_temp": gpu_temp,
                "battery_pct": battery_pct,
                "is_locked": locked
            }

            requests.post(FLASK_URL, json=payload, timeout=5)
        except Exception as e:
            print("Telemetriya göndərmə xətası:", e)
        
        time.sleep(30)  # Hər 30 saniyədən bir bazaya məlumat göndərəcək

def telegram_command_listener():
    print("🤖 Telegram dinləmə sistemi işə düşdü...")
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=30"
            resp = requests.get(url, timeout=35).json()
            if resp.get("ok"):
                for result in resp.get("result", []):
                    offset = result["update_id"] + 1
                    msg = result.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id"))
                    text = msg.get("text", "").strip()
                    
                    if chat_id == CHAT_ID:
                        if text == "/status":
                            try:
                                cpu_pct = psutil.cpu_percent(interval=0.5)
                                ram = psutil.virtual_memory()
                                ram_pct = ram.percent
                                ram_used = round(ram.used / (1024 ** 3), 1)
                                ram_total = round(ram.total / (1024 ** 3), 1)
                                
                                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                                gpu_name = pynvml.nvmlDeviceGetName(handle)
                                if isinstance(gpu_name, bytes):
                                    gpu_name = gpu_name.decode('utf-8')
                                
                                gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                                gpu_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                                gpu_info = f"- GPU ({gpu_name}): %{gpu_util} | {gpu_temp}°C"

                                battery = psutil.sensors_battery()
                                pct = battery.percent if battery else "Naməlum"
                                plugged = "Şarjdadır ⚡" if battery and battery.power_plugged else "Batareyadadır 🔋"
                                locked = "Bəli 🔒" if is_locked() else "Xeyr 🔓"
                                
                                status_text = (
                                    f"📊 *Sistem Statusu (Telemetriya):*\n"
                                    f"- CPU Yükü: %{cpu_pct}\n"
                                    f"- RAM: %{ram_pct} ({ram_used}GB / {ram_total}GB)\n"
                                    f"{gpu_info}\n"
                                    f"- Batareya: %{pct} ({plugged})\n"
                                    f"- Ekran Kilidli: {locked}"
                                )
                                send_msg(status_text)
                            except Exception as e:
                                send_msg(f"❌ Status oxunarkən xəta: {e}")
                            
                        elif text == "/ip":
                            send_msg(get_ip_info())
                        elif text == "/lock":
                            send_msg("🔒 Kompüter uzaqdan kilidləndi.")
                            lock_pc()
                            
                        elif text == "/shutdown":
                            send_msg("⚠️ Kompüter uzaqdan söndürülür...")
                            subprocess.run(["shutdown", "/s", "/t", "1"])
                            
        except Exception as e:
            print("❌ Telegram dinləmə xətası:", e)
            time.sleep(5)

def monitor_power():
    battery = psutil.sensors_battery()
    if battery is None:
        return
    initial_status = battery.power_plugged
    
    while True:
        if is_locked():
            current_status = psutil.sensors_battery().power_plugged
            if current_status != initial_status:
                send_telegram_alert("Kompüter kilidli ikən enerji kabeli çıxarıldı!")
                break
        else:
            initial_status = psutil.sensors_battery().power_plugged
        time.sleep(2)

def monitor_keyboard():
    def on_key(e):
        if is_locked() and e.event_type == keyboard.KEY_DOWN:
            send_telegram_alert("Kilidli ekranda klaviaturadan istifadə edilməyə cəhd edildi!")
            time.sleep(12)

    keyboard.hook(on_key)
    keyboard.wait()

if __name__ == "__main__":
    print("=== TAM TƏHLÜKƏSİZLİK VƏ TELEMETRİYA SİSTEMİ İŞƏ DÜŞDÜ ===")
    
    # Bütün axınları (threads) işə salırıq
    threading.Thread(target=telegram_command_listener, daemon=True).start()
    threading.Thread(target=monitor_power, daemon=True).start()
    threading.Thread(target=monitor_keyboard, daemon=True).start()
    threading.Thread(target=send_telemetry_to_server, daemon=True).start()  # Bazaya məlumat ötürən axın
    
    while True:
        time.sleep(1)
