import asyncio
import json
import os
import subprocess
import time
import urllib.request
import base64
import websockets

SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CDP_PORT = 9222

def get_session_cookie(user_id, password):
    url = "http://127.0.0.1:8000/api/auth/login"
    data = json.dumps({"user_id": user_id, "password": password}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        cookies = resp.headers.get_all('Set-Cookie') or []
        for c in cookies:
            if "abc_session=" in c:
                val = c.split("abc_session=")[1].split(";")[0]
                return val
    return None

class CDPClient:
    def __init__(self, ws):
        self.ws = ws
        self.msg_id = 0

    async def send(self, method, params=None):
        self.msg_id += 1
        current_id = self.msg_id
        req = {"id": current_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(req))
        while True:
            resp_str = await self.ws.recv()
            resp = json.loads(resp_str)
            if resp.get("id") == current_id:
                if "error" in resp:
                    raise Exception(f"CDP error: {resp['error']}")
                return resp.get("result", {})

async def capture_page(ws_url, path, filename, width, height, is_mobile, cookie=None):
    async with websockets.connect(ws_url, max_size=20_000_000) as ws:
        cdp = CDPClient(ws)
        await cdp.send("Page.enable")
        await cdp.send("Network.enable")
        
        # Clear cookies
        await cdp.send("Network.clearBrowserCookies")
        
        if cookie:
            await cdp.send("Network.setCookie", {
                "name": "abc_session",
                "value": cookie,
                "domain": "127.0.0.1",
                "path": "/",
                "httpOnly": True
            })
            
        await cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": is_mobile
        })
        
        full_url = f"http://127.0.0.1:8000{path}"
        await cdp.send("Page.navigate", {"url": full_url})
        
        # Wait a short while for page to load & dynamic JS to render
        await asyncio.sleep(2.0)
        
        res = await cdp.send("Page.captureScreenshot", {"format": "png"})
        img_data = base64.b64decode(res["data"])
        
        out_path = os.path.join(SCREENSHOTS_DIR, filename)
        with open(out_path, "wb") as f:
            f.write(img_data)
        print(f"Captured: {filename} ({width}x{height}) -> {len(img_data)} bytes")

async def main():
    profile_dir = os.path.join(SCREENSHOTS_DIR, "edge_profile")
    os.makedirs(profile_dir, exist_ok=True)
    
    cmd = [
        EDGE_PATH,
        "--headless=new",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "about:blank"
    ]
    proc = subprocess.Popen(cmd)
    try:
        # Wait for debugging port
        page_ws_url = None
        for _ in range(15):
            try:
                # Open a new page target
                req = urllib.request.Request(f"http://127.0.0.1:{CDP_PORT}/json/new?about:blank", method="PUT")
                with urllib.request.urlopen(req) as r:
                    page_data = json.loads(r.read().decode())
                    page_ws_url = page_data.get("webSocketDebuggerUrl")
                    if page_ws_url:
                        break
            except Exception:
                # If PUT fails, check GET /json/list
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list") as r:
                        pages = json.loads(r.read().decode())
                        for p in pages:
                            if p.get("type") == "page":
                                page_ws_url = p.get("webSocketDebuggerUrl")
                                break
                    if page_ws_url:
                        break
                except Exception:
                    pass
                time.sleep(0.5)

        if not page_ws_url:
            raise Exception("Could not find a valid page CDP WebSocket URL")

        print("Page CDP Connected at:", page_ws_url)
        
        # Get session cookies
        admin_cookie = get_session_cookie("admin", "Admin@123")
        faculty_cookie = get_session_cookie("501", "Faculty@123")
        student_cookie = get_session_cookie("1001", "Student@123")
        
        print("Cookies retrieved successfully.")
        
        targets = [
            # Desktop (1280x800)
            ("/login", "login_desktop.png", 1280, 800, False, None),
            ("/student", "student_desktop.png", 1280, 800, False, student_cookie),
            ("/faculty", "faculty_desktop.png", 1280, 800, False, faculty_cookie),
            ("/admin", "admin_desktop.png", 1280, 800, False, admin_cookie),
            
            # Mobile (375x700)
            ("/login", "login_mobile.png", 375, 700, True, None),
            ("/student", "student_mobile.png", 375, 700, True, student_cookie),
            ("/faculty", "faculty_mobile.png", 375, 700, True, faculty_cookie),
            ("/admin", "admin_mobile.png", 375, 700, True, admin_cookie),
        ]
        
        for path, filename, w, h, is_m, cookie in targets:
            await capture_page(page_ws_url, path, filename, w, h, is_m, cookie)
            
        print("All screenshots captured successfully!")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(main())
