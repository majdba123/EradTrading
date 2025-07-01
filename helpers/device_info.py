import platform
import requests
from fastapi import Request

def get_device_info(request: Request):
    user_agent = request.headers.get("user-agent", "unknown")
    ip_address = request.client.host if request.client else "unknown"
    
    device_info = {
        "ip_address": ip_address,
        "device_name": platform.system(),
        "device_type": "mobile" if "Mobi" in user_agent else "desktop",
        "os": platform.system() + " " + platform.release(),
        "browser": user_agent.split("/")[0] if "/" in user_agent else "unknown",
        "country": "unknown",
        "city": "unknown"
    }
    
    try:
        if ip_address not in ["127.0.0.1", "unknown"]:
            res = requests.get(f"http://ip-api.com/json/{ip_address}?fields=country,city", timeout=2)
            if res.status_code == 200:
                geo = res.json()
                device_info.update({
                    "country": geo.get("country", "unknown"),
                    "city": geo.get("city", "unknown")
                })
    except:
        pass
    
    return device_info