"""Injection regressions against an isolated database and local HTTP server.

Set RUN_BROWSER_SECURITY_TESTS=1 to include Firefox/Selenium XSS tests.
"""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src import server


class QuietHandler(server.Handler):
    def log_message(self, *args):
        pass


class LocalApp(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.previous_db = server.DB
        self.addCleanup(setattr, server, 'DB', self.previous_db)
        server.DB = Path(self.directory.name) / 'security.sqlite3'
        server.initialize()
        self.http = HTTPServer(('127.0.0.1', 0), QuietHandler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.http.server_port}'
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    def request(self, path, data=None, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        request = Request(self.base + path, None if data is None else json.dumps(data).encode(), headers)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, response.headers, json.loads(body) if response.headers.get_content_type() == 'application/json' else body

    def create_case(self, **fields):
        case = {'name': 'Security test', 'alg_set': 'ELL', 'category': 'Security',
                'algorithm': "R U R'", 'description': '', 'recognition': '', 'image': '', 'drawing': '{}'}
        case.update(fields)
        status, _, result = self.request('/api/case', case)
        self.assertEqual(status, 200, result)
        case['id'] = result['id']
        return case


class SQLInjectionTests(LocalApp):
    def test_sql_payloads_are_stored_as_literal_text(self):
        payloads = ["'); DROP TABLE cases; --", "' OR 1=1 --", "'; UPDATE cases SET learned=1; --"]
        baseline = self.request('/api/library')[2]['cases']
        for payload in payloads:
            with self.subTest(payload=payload):
                status, _, _ = self.request('/api/sets', {'name': payload})
                self.assertEqual(status, 200)
                case = self.create_case(name=payload, alg_set=payload, category=payload,
                                        algorithm=payload, description=payload, recognition=payload,
                                        image=payload)
                case['description'] = payload + ' updated'
                self.assertEqual(self.request('/api/case', case)[0], 200)
                library = self.request('/api/library')[2]
                stored = next(c for c in library['cases'] if c['id'] == case['id'])
                for field in ['name', 'alg_set', 'category', 'algorithm', 'recognition', 'image']:
                    self.assertEqual(stored[field], payload)
                self.assertEqual(stored['description'], payload + ' updated')
                self.assertIn(payload, library['sets'])
        # Check every original row, not just that the table still exists.
        current = {c['id']: c for c in self.request('/api/library')[2]['cases']}
        for case in baseline:
            self.assertEqual(current[case['id']], case)
        with server.connect() as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_injected_ids_cannot_update_other_rows(self):
        self.create_case(learning=1)
        before = self.request('/api/library')[2]
        for payload in ['1 OR 1=1', "1; DROP TABLE cases; --", "' UNION SELECT 1 --"]:
            with self.subTest(payload=payload):
                status, _, _ = self.request('/api/progress', {'id': payload, 'state': 'learned'})
                self.assertEqual(status, 404)
                status, _, _ = self.request('/api/practice-result', {'id': payload, 'elapsed_ms': 1000})
                self.assertEqual(status, 404)
                # A nonexistent ID can be a no-op, but must never match every row.
                self.request('/api/case', {'id': payload, 'name': 'Injected', 'alg_set': 'ELL'})
                self.assertEqual(self.request('/api/library')[2], before)

    def test_injected_set_lookup_does_not_bypass_validation(self):
        before = self.request('/api/library')[2]
        status, _, _ = self.request('/api/case', {'name': 'Invalid set', 'alg_set': "ELL' OR 1=1 --"})
        self.assertEqual(status, 400)
        self.assertEqual(self.request('/api/library')[2], before)


XSS_PAYLOAD = '<img src=x onerror="window.__xssExecuted=true" data-xss-probe="1">'


class XSSResponseTests(LocalApp):
    def test_stored_payloads_are_json_not_html(self):
        self.create_case(name=XSS_PAYLOAD, algorithm=XSS_PAYLOAD,
                         category=XSS_PAYLOAD, description=XSS_PAYLOAD, recognition=XSS_PAYLOAD)
        for path in ['/api/library', '/api/export']:
            with self.subTest(path=path):
                status, headers, data = self.request(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers.get_content_type(), 'application/json')
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(data['cases'][-1]['name'], XSS_PAYLOAD)
        status, headers, html = self.request('/')
        self.assertEqual(status, 200)
        self.assertNotIn(XSS_PAYLOAD.encode(), html)

    def test_reflected_path_payload_is_not_html(self):
        status, headers, data = self.request('/%3Csvg%20onload%3Dalert(1)%3E')
        self.assertEqual(status, 404)
        self.assertEqual(headers.get_content_type(), 'application/json')
        self.assertEqual(data, {'error': 'Not found'})


@unittest.skipUnless(os.environ.get('RUN_BROWSER_SECURITY_TESTS') == '1',
                     'Set RUN_BROWSER_SECURITY_TESTS=1 and install requirements-dev.txt for Firefox XSS tests')
class XSSBrowserTests(LocalApp):
    def test_stored_payloads_render_as_text_without_executing(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        import shutil

        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options, service=Service(executable_path=shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        payloads = [XSS_PAYLOAD, '<script>window.__xssExecuted=true</script>',
                    '<svg onload="window.__xssExecuted=true" data-xss-probe="1"></svg>']
        for payload in payloads:
            self.request('/api/sets', {'name': payload})
            self.create_case(name=payload, alg_set=payload, category=payload,
                                    algorithm=payload, description=payload, recognition=payload,
                                    image='/missing.png" onerror="window.__xssExecuted=true',
                                    drawing=json.dumps({'useDrawing': True, 'stickers': {
                                        'U0': {'color': '"><svg onload="window.__xssExecuted=true">', 'highlight': True}}}))
            driver.get(self.base+'/#/sets/ELL')
            # Hash navigation alone need not reload data created by this test.
            driver.refresh()
            wait.until(lambda d: d.find_elements('css selector', '.card'))
            driver.execute_script("const el=document.getElementById('sets');el.value=arguments[0];el.dispatchEvent(new Event('change'));", payload)
            wait.until(lambda d: len(d.find_elements('css selector', '.card')) == 1)
            self.assertEqual(driver.find_element('css selector', '.card strong').text, payload)
            driver.find_element('css selector', '.case-open').click()
            wait.until(lambda d: d.find_element('id', 'detail').get_property('open'))
            self.assertEqual(driver.find_element('id', 'algorithm-heading').text, payload)
            self.assertEqual(driver.find_element('id', 'description').get_property('value'), payload)
            self.assertEqual(driver.find_element('id', 'recognition').get_property('value'), payload)
            # Also exercise live algorithm-title updates rather than only loading.
            driver.execute_script("const el=document.getElementById('algorithm');el.value=arguments[0];el.dispatchEvent(new Event('input',{bubbles:true}));", payload)
            self.assertEqual(driver.find_element('id', 'algorithm-heading').text, payload)
            self.assertFalse(driver.execute_script('return Boolean(window.__xssExecuted)'))
            self.assertEqual(driver.find_elements('css selector', '[data-xss-probe], [onerror], [onload]'), [])
            self.assertEqual(driver.execute_script("return [...document.scripts].filter(s=>!s.src).length"), 0)
            driver.find_element('id', 'close').click()
            driver.switch_to.alert.accept()
