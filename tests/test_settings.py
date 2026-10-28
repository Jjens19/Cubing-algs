import os
import shutil
import unittest

from src import server
from test_security import LocalApp


class ResetProgressTests(LocalApp):
    def seed_progress(self):
        with server.connect() as db:
            db.execute("UPDATE cases SET learned=1 WHERE alg_set='PLL'")
            db.execute("UPDATE cases SET learning=1 WHERE alg_set='OLL'")
            return {row['id']: dict(row) for row in db.execute('SELECT * FROM cases')}

    def test_subset_reset_preserves_all_other_fields_and_other_sets(self):
        before = self.seed_progress()
        status, _, result = self.request('/api/reset-progress', {'scope': 'subset', 'alg_set': 'OLL', 'confirmed': True})
        self.assertEqual(status, 200)
        self.assertEqual(result['reset'], 57)
        server.initialize()
        with server.connect() as db:
            after = {row['id']: dict(row) for row in db.execute('SELECT * FROM cases')}
        for key, case in before.items():
            expected = {**case, 'learned': 0, 'learning': 0} if case['alg_set'] == 'OLL' else case
            self.assertEqual(after[key], expected)

    def test_reset_everything_and_empty_reset(self):
        before = self.seed_progress()
        payload = {'scope': 'all', 'confirmed': True}
        self.assertEqual(self.request('/api/reset-progress', payload)[2]['reset'], 78)
        with server.connect() as db:
            for row in db.execute('SELECT * FROM cases'):
                self.assertEqual(dict(row), {**before[row['id']], 'learned': 0, 'learning': 0})
        self.assertEqual(self.request('/api/reset-progress', payload)[2]['reset'], 0)

    def test_invalid_or_unconfirmed_resets_cannot_modify_progress(self):
        before = self.seed_progress()
        for payload in ({'scope': 'all'}, {'scope': 'all', 'confirmed': 'true'},
                        {'scope': 'unknown', 'confirmed': True},
                        {'scope': 'subset', 'alg_set': "OLL' OR 1=1 --", 'confirmed': True},
                        {'scope': 'subset', 'confirmed': True}):
            self.assertEqual(self.request('/api/reset-progress', payload)[0], 400)
        self.assertEqual(self.request('/api/reset-progress', {'scope': 'all', 'confirmed': True}, origin='https://example.com')[0], 403)
        with server.connect() as db:
            self.assertEqual({r['id']:dict(r) for r in db.execute('SELECT * FROM cases')}, before)


@unittest.skipUnless(os.environ.get('RUN_BROWSER_SECURITY_TESTS') == '1', 'Enable Firefox tests with RUN_BROWSER_SECURITY_TESTS=1')
class SettingsBrowserTests(LocalApp):
    def test_confirm_cancel_subset_and_all_resets(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait, Select
        with server.connect() as db:
            db.execute("UPDATE cases SET learning=1 WHERE alg_set='OLL'")
            db.execute("UPDATE cases SET learned=1 WHERE alg_set='PLL'")
        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options, service=Service(shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        driver.get(self.base+'/#/sets/OLL')
        wait.until(lambda d: d.find_elements('css selector', '.case-open'))
        driver.find_element('id', 'open-settings').click()
        self.assertIn('57 of 57', driver.find_element('id', 'reset-summary').text)
        driver.find_element('id', 'review-reset').click()
        driver.find_element('id', 'cancel-reset').click()
        self.assertFalse(driver.find_element('id', 'reset-confirmation').is_displayed())
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT SUM(learning) FROM cases WHERE alg_set='OLL'").fetchone()[0], 57)
        driver.find_element('id', 'review-reset').click()
        driver.find_element('id', 'confirm-reset').click()
        wait.until(lambda d: 'Progress reset for 57 cases.' in d.find_element('id', 'settings-status').text)
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT SUM(learned) FROM cases WHERE alg_set='PLL'").fetchone()[0], 21)
        Select(driver.find_element('id', 'reset-scope')).select_by_value('all')
        self.assertIn('21 of 363', driver.find_element('id', 'reset-summary').text)
        driver.find_element('id', 'review-reset').click()
        driver.find_element('id', 'confirm-reset').click()
        wait.until(lambda d: 'Progress reset for 21 cases.' in d.find_element('id', 'settings-status').text)
        self.assertTrue(driver.find_element('id', 'review-reset').get_property('disabled'))
        driver.find_element('id', 'close-settings').click()
        driver.refresh()
        wait.until(lambda d: d.find_elements('css selector', '.case-open'))
        self.assertEqual(len(driver.find_elements('css selector', '.card.learning, .card.learned')), 0)
