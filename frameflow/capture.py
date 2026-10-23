"""Deterministic page captures for news-snapshot scenes (Playwright + the system Google Chrome).

    python -m frameflow.capture <url> <out.png>

Fixed 1080x1350 viewport at 1x, reduced motion, animations and transitions frozen, common cookie/consent overlays
hidden, top of the article only. The same page state always gives the same picture.
"""
import sys
from pathlib import Path

FREEZE = """
*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }
[id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i], [class*="gdpr" i],
[class*="newsletter" i][class*="popup" i], [aria-modal="true"], iframe[src*="ads"] { display: none !important; }
html, body { overflow: hidden !important; }
"""


def capture(url, out, width=1080, height=1350, timeout_ms=30000):
    from playwright.sync_api import sync_playwright
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1,
                                reduced_motion="reduce", locale="en-IN", timezone_id="Asia/Kolkata")
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # busy news pages never go idle; the DOM is enough
        page.add_style_tag(content=FREEZE)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out), animations="disabled")
        browser.close()
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m frameflow.capture <url> <out.png>")
    print(capture(sys.argv[1], sys.argv[2]))
