#!/usr/bin/env python3
import asyncio, json, aiohttp, websockets, shutil, subprocess, os, signal, random, time

# set BROWSER_BIN to qutebrowser/chrome path if needed, else script will try common names
BROWSER_BIN = os.environ.get("BROWSER_BIN")
if not BROWSER_BIN:
    BROWSER_BIN = shutil.which("qutebrowser") or shutil.which("google-chrome") or shutil.which("chrome") or shutil.which("chromium") or shutil.which("chromium-browser")

CDP_HOST = "http://127.0.0.1:9222"
TARGET_URL = "https://www.merriam-webster.com/dictionary/shard"
DOM_DEPTH = 4
GRID_SIZE = 5
RETRY_LIMIT = 3

async def launch_browser():
    if not BROWSER_BIN:
        raise SystemExit("No browser binary found; set BROWSER_BIN or install Chrome/qutebrowser.")
    args = [
        BROWSER_BIN,
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--disable-blink-features=AutomationControlled",
        "--window-size=1366,768",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(1.0)
    return proc

async def new_tab(session, url):
    async with session.get(f"{CDP_HOST}/json/new?{url}") as resp:
        resp.raise_for_status()
        return await resp.json()

class CDP:
    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self._futures = {}
        self.last_event = None
        self.recv_task = asyncio.create_task(self._recv_loop())

    async def _recv_loop(self):
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg:
                fut = self._futures.pop(msg["id"], None)
                if fut and not fut.done():
                    fut.set_result(msg)
            else:
                self.last_event = msg

    async def send(self, method, params=None, timeout=10):
        self._id += 1
        payload = {"id": self._id, "method": method}
        if params:
            payload["params"] = params
        fut = asyncio.get_event_loop().create_future()
        self._futures[self._id] = fut
        await self.ws.send(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=timeout)

    async def close(self):
        self.recv_task.cancel()
        await self.ws.close()

def box_center(model):
    cx = (model["content"][0] + model["content"][4]) / 2.0
    cy = (model["content"][1] + model["content"][5]) / 2.0
    return cx, cy

def grid_points(model, n):
    xs = [model["content"][i] for i in range(0,8,2)]
    ys = [model["content"][i] for i in range(1,8,2)]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pad_x = (maxx - minx) * 0.12
    pad_y = (maxy - miny) * 0.12
    left, right = minx + pad_x, maxx - pad_x
    top, bottom = miny + pad_y, maxy - pad_y
    pts = []
    for i in range(n):
        for j in range(n):
            fx = left + (right - left) * (j / (n - 1)) if n > 1 else (left + right) / 2
            fy = top + (bottom - top) * (i / (n - 1)) if n > 1 else (top + bottom) / 2
            pts.append((fx, fy))
    random.shuffle(pts)
    return pts

async def smooth_move_and_click(cdp, x, y, steps=10):
    sx = x + random.uniform(-120, 120)
    sy = y + random.uniform(-60, 60)
    for i in range(steps):
        t = (i+1)/steps
        ix = sx + (x - sx) * t + random.uniform(-1,1)
        iy = sy + (y - sy) * t + random.uniform(-1,1)
        await cdp.send("Input.dispatchMouseEvent", {"type":"mouseMoved","x":ix,"y":iy,"buttons":0})
        await asyncio.sleep(random.uniform(0.01,0.04))
    await asyncio.sleep(random.uniform(0.03,0.12))
    await cdp.send("Input.dispatchMouseEvent", {"type":"mousePressed","x":x,"y":y,"button":"left","clickCount":1})
    await asyncio.sleep(random.uniform(0.03,0.08))
    await cdp.send("Input.dispatchMouseEvent", {"type":"mouseReleased","x":x,"y":y,"button":"left","clickCount":1})

async def wait_for_verification(cdp, timeout=8.0):
    end = asyncio.get_event_loop().time() + timeout
    last_len = None
    while asyncio.get_event_loop().time() < end:
        evt = getattr(cdp, "last_event", None)
        if evt and evt.get("method") in ("Page.frameNavigated","Page.loadEventFired","Page.frameStoppedLoading"):
            return True
        try:
            eval_resp = await cdp.send("Runtime.evaluate", {"expression":"document.documentElement.outerHTML.length","returnByValue":True}, timeout=2)
            length = eval_resp.get("result",{}).get("result",{}).get("value")
            if last_len is None:
                last_len = length
            else:
                if length != last_len:
                    return True
            doc = await cdp.send("DOM.getDocument", {"depth":1}, timeout=2)
            root = doc.get("result",{}).get("root",{})
            q = await cdp.send("DOM.querySelectorAll", {"nodeId":root.get("nodeId"), "selector":"iframe"}, timeout=2)
            if len(q.get("result",{}).get("nodeIds",[])) == 0:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.4)
    return False

async def try_click_iframe(cdp, iframe_nodeId):
    await cdp.send("DOM.requestChildNodes", {"nodeId": iframe_nodeId, "depth": 2})
    box = await cdp.send("DOM.getBoxModel", {"nodeId": iframe_nodeId})
    if "result" not in box:
        return False
    model = box["result"]["model"]
    points = [box_center(model)] + grid_points(model, GRID_SIZE)
    tried=set()
    for x,y in points:
        key=(round(x),round(y))
        if key in tried: continue
        tried.add(key)
        await smooth_move_and_click(cdp, x, y, steps=random.randint(6,12))
        ok = await wait_for_verification(cdp, timeout=3.0)
        if ok:
            return True
    return False

async def main():
    proc = None
    try:
        proc = await launch_browser()
        async with aiohttp.ClientSession() as session:
            tab = await new_tab(session, TARGET_URL)
        ws_url = tab["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url) as ws:
            cdp = CDP(ws)
            await cdp.send("Page.enable")
            await cdp.send("DOM.enable")
            await cdp.send("Runtime.enable")
            await cdp.send("Input.enable")
            await cdp.send("Page.navigate", {"url": TARGET_URL})
            start=time.time()
            while True:
                evt = getattr(cdp, "last_event", None)
                if evt and evt.get("method") in ("Page.loadEventFired","Page.domContentEventFired"):
                    break
                if time.time() - start > 12:
                    break
                await asyncio.sleep(0.1)
            doc = await cdp.send("DOM.getDocument", {"depth": DOM_DEPTH})
            root = doc.get("result",{}).get("root",{})
            root_id = root.get("nodeId")
            q = await cdp.send("DOM.querySelectorAll", {"nodeId": root_id, "selector": "iframe"})
            iframe_nodeIds = q.get("result",{}).get("nodeIds", [])
            if not iframe_nodeIds:
                print("No iframes found.")
                return
            success=False
            for attempt in range(RETRY_LIMIT):
                for iframe_nodeId in iframe_nodeIds:
                    try:
                        ok = await try_click_iframe(cdp, iframe_nodeId)
                        if ok:
                            final = await wait_for_verification(cdp, timeout=10.0)
                            if final:
                                print("Success: Cloudflare likely passed.")
                                success=True
                                break
                    except Exception:
                        continue
                if success:
                    break
                await cdp.send("Page.reload", {"ignoreCache": True})
                await asyncio.sleep(1.2 + attempt*0.5)
                doc = await cdp.send("DOM.getDocument", {"depth": DOM_DEPTH})
                root = doc.get("result",{}).get("root",{})
                q = await cdp.send("DOM.querySelectorAll", {"nodeId": root.get("nodeId"), "selector":"iframe"})
                iframe_nodeIds = q.get("result",{}).get("nodeIds", [])
            if not success:
                print("Failed to pass Cloudflare checkbox after retries.")
            await cdp.close()
    finally:
        if proc:
            try:
                proc.send_signal(signal.SIGTERM)
            except Exception:
                pass

if __name__=="__main__":
    asyncio.run(main())
