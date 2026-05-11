from playwright.sync_api import sync_playwright, expect
import json

captured = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    def handle_route(route):
        request = route.request
        url = request.url
        if '/api/auth/me' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'user': {'id': 'u1', 'email': 'test@example.com', 'created_at': '2026-01-01T00:00:00Z', 'role': 'user', 'status': 'active', 'plan': 'free'}}))
        if '/api/settings/defaults' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({
                'default_provider': 'openrouter',
                'openrouter': {'api_key': '', 'base_url': '', 'model': 'test-render-model'},
                'nvidia': {'api_key': '', 'base_url': '', 'model': ''},
                'ollama': {'api_key': '', 'base_url': '', 'model': ''},
                'openai_compat': {'api_key': '', 'base_url': '', 'model': ''},
                'router9': {'api_key': '', 'base_url': '', 'model': '', 'only_mode': False, 'allowed_model_ids': []},
                'ocr': {'provider': 'openrouter', 'model': 'test-ocr-model', 'max_image_mb': 5},
                'openrouter_http_referer': '',
                'openrouter_x_title': '',
                'openrouter_reasoning_enabled': False,
            }))
        if '/api/user/settings' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'settings': None, 'updated_at': None}))
        if '/api/ocr' in url:
            captured.append(json.loads(request.post_data or '{}'))
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'text': 'Cho tam giác ABC. Vẽ tam giác ABC.', 'provider': 'openrouter', 'model': 'test-ocr-model', 'warnings': []}))
        if '/api/render' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'scene': {'version': '1.0', 'renderer': 'geogebra_2d', 'objects': []}, 'payload': {}, 'warnings': []}))
        if '/api/health' in url:
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'status': 'ok', 'app': 'test'}))
        return route.fulfill(status=200, content_type='application/json', body='{}')

    page.route('**/api/**', handle_route)
    page.goto('http://127.0.0.1:5173')
    page.wait_for_load_state('networkidle')

    page.locator('.textarea-wrap textarea').set_input_files if False else None
    textarea = page.locator('.textarea-wrap textarea')
    expect(textarea).to_be_visible(timeout=10000)

    # Textarea file chooser via double click should use problem mode.
    with page.expect_file_chooser() as fc_info:
        textarea.dblclick()
    fc_info.value.set_files({'name': 'problem.png', 'mimeType': 'image/png', 'buffer': b'fakepng'})
    page.wait_for_timeout(500)

    page.locator('button.ocr-image-drop-target').click()
    with page.expect_file_chooser() as fc_info2:
        page.locator('button.ocr-image-drop-target').click()
    fc_info2.value.set_files({'name': 'diagram.png', 'mimeType': 'image/png', 'buffer': b'fakepng'})
    page.wait_for_timeout(500)

    print(json.dumps([item.get('mode') for item in captured]))
    browser.close()
