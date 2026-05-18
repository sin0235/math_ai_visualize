from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import base64, json
img = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=')
test_img = Path(r'D:\Programs\hinh\tmp-chat-upload.png')
test_img.write_bytes(img)
result = {'url': None, 'logged_in': False, 'icon': None, 'sent': False, 'error': None, 'screenshot': r'D:\Programs\hinh\tmp-chat-test.png'}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1366, 'height': 768})
    page.goto('http://localhost:5173', wait_until='networkidle')
    result['url'] = page.url
    buttons = page.locator('button[aria-label="Chat với admin"]')
    if buttons.count() == 0:
        result['error'] = 'Không thấy nút Chat với admin; có thể chưa đăng nhập hoặc UI khác.'
        page.screenshot(path=result['screenshot'], full_page=True)
        browser.close()
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit
    result['logged_in'] = True
    buttons.first.click()
    page.wait_for_timeout(500)
    attach = page.locator('button[aria-label="Đính kèm ảnh"]').first
    attach.wait_for(timeout=5000)
    result['icon'] = attach.evaluate("el => { const cs=getComputedStyle(el); const r=el.getBoundingClientRect(); const svg=el.querySelector('svg'); const sr=svg ? svg.getBoundingClientRect() : null; return {color: cs.color, background: cs.backgroundColor, border: cs.borderWidth + ' ' + cs.borderStyle + ' ' + cs.borderColor, box:{x:r.x,y:r.y,w:r.width,h:r.height}, svg: sr ? {x:sr.x,y:sr.y,w:sr.width,h:sr.height, cx:sr.x+sr.width/2, cy:sr.y+sr.height/2, dx:(sr.x+sr.width/2)-(r.x+r.width/2), dy:(sr.y+sr.height/2)-(r.y+r.height/2)} : null}; }")
    page.locator('input[type="file"]').first.set_input_files(str(test_img))
    page.wait_for_timeout(300)
    page.locator('textarea[placeholder="Nhập tin nhắn..."]').fill('test ảnh cloudinary')
    page.locator('button[aria-label="Gửi tin nhắn"]').first.click()
    try:
        page.wait_for_function("() => Array.from(document.querySelectorAll('.chat-message img')).some(img => img.src.includes('cloudinary') || img.src.startsWith('http'))", timeout=15000)
        result['sent'] = True
    except PlaywrightTimeoutError:
        toast = page.locator('.notification-card, .error-box').all_inner_texts()
        result['error'] = 'Không xác nhận được ảnh đã gửi trong 15s. Toast/error: ' + ' | '.join(toast[:3])
    page.screenshot(path=result['screenshot'], full_page=True)
    browser.close()
print(json.dumps(result, ensure_ascii=False, indent=2))
