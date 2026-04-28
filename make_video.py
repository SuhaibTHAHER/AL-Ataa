# -*- coding: utf-8 -*-
"""
يشغّل سيرفر محلي → يسجّل الانميشن كفيديو حقيقي → يحوّله لـ MP4
"""
import asyncio, threading, os, shutil, time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from playwright.async_api import async_playwright

# ── إعدادات ────────────────────────────────────────
DIR       = Path(__file__).parent
OUT       = DIR / "al-ataa-ad.mp4"
WIDTH, H  = 1080, 1080
PORT      = 8765

# مدة كل شريحة + الـ fade (ثواني)
SLIDE_DURS = [4.5, 6, 9, 9, 8, 6, 7]
FADE       = 0.9
TOTAL      = sum(SLIDE_DURS) + len(SLIDE_DURS) * FADE + 2  # +2 هامش

# ── سيرفر محلي ──────────────────────────────────────
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIR), **kw)

def start_server():
    srv = HTTPServer(("127.0.0.1", PORT), QuietHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv

# ── التسجيل ─────────────────────────────────────────
async def record():
    tmp_dir = DIR / "_video_tmp"
    tmp_dir.mkdir(exist_ok=True)

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            "",
            headless=True,
            viewport={"width": WIDTH, "height": H},
            device_scale_factor=1,
            record_video_dir=str(tmp_dir),
            record_video_size={"width": WIDTH, "height": H},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print("  جاري تحميل الصفحة...")
        await page.goto(f"http://127.0.0.1:{PORT}/ad-animation.html")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)  # انتظر الخطوط + الصور

        print(f"  التسجيل ({TOTAL:.0f}s)...")
        # شغّل الشرائح تلقائياً — كل شريحة بمدتها
        for i, dur in enumerate(SLIDE_DURS):
            if i > 0:
                await page.click("body")
                await asyncio.sleep(FADE)
            await asyncio.sleep(dur)
            print(f"  شريحة {i+1}/{len(SLIDE_DURS)} ✓")

        await asyncio.sleep(1)

        # أغلق وخذ مسار الفيديو
        video_path = await page.video.path()
        await ctx.close()

    return Path(video_path), tmp_dir

# ── تحويل WebM → MP4 ────────────────────────────────
def convert(webm: Path):
    from moviepy import VideoFileClip
    print("  تحويل WebM → MP4...")
    clip = VideoFileClip(str(webm))
    clip.write_videofile(
        str(OUT),
        codec="libx264",
        audio=False,
        logger=None,
        ffmpeg_params=["-crf", "16", "-pix_fmt", "yuv420p", "-preset", "slow"]
    )
    clip.close()

# ── رئيسي ───────────────────────────────────────────
async def main():
    print("تشغيل السيرفر...")
    srv = start_server()
    await asyncio.sleep(0.5)

    try:
        t0 = time.time()
        webm, tmp_dir = await record()
        convert(webm)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        size = OUT.stat().st_size / 1e6
        print(f"\nالفيديو جاهز: al-ataa-ad.mp4 ({size:.1f} MB) في {time.time()-t0:.0f}s")
    finally:
        srv.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
