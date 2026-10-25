"""Browser regression for the app's stylesheet and responsive layout."""
import os
import shutil
import unittest

from test_security import LocalApp


@unittest.skipUnless(os.environ.get('RUN_BROWSER_SECURITY_TESTS') == '1',
                     'Enable Firefox tests with RUN_BROWSER_SECURITY_TESTS=1')
class LayoutTests(LocalApp):
    def test_cll_recognition_colors_and_edits(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait

        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options, service=Service(shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        driver.get(self.base + '/#/sets/CLL')
        wait.until(lambda d: d.find_elements('css selector', '.case-open'))
        driver.find_element('css selector', 'button[aria-label="Open U1"]').click()
        wait.until(lambda d: d.find_element('id', 'detail').get_property('open'))
        def sticker(key):
            return driver.find_element('css selector', f'#cube rect[data-key="{key}"]')
        for key, color in [('U0', '#ffdd00'), ('U1', '#51565d'), ('U2', '#ffdd00'), ('U4', '#ffdd00')]:
            self.assertEqual(sticker(key).get_attribute('fill'), color, key)
        driver.find_element('css selector', 'button[aria-label="Blue"]').click()
        sticker('U0').click()
        driver.find_element('id', 'highlight').click()
        sticker('U2').click()
        driver.find_element('css selector', '#case-form button[type="submit"]').click()
        wait.until(lambda d: not d.find_element('id', 'detail').get_property('open'))
        driver.find_element('css selector', 'button[aria-label="Open U1"]').click()
        wait.until(lambda d: d.find_element('id', 'detail').get_property('open'))
        self.assertEqual(sticker('U0').get_attribute('fill'), '#0000ff')
        self.assertEqual(sticker('U2').get_attribute('aria-pressed'), 'true')
        self.assertEqual(sticker('U4').get_attribute('fill'), '#ffdd00')

    def test_layout_and_category_dropdowns(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait

        self.create_case(name='Nested case', category='A / Bars / Opposite')
        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options, service=Service(shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        driver.set_window_size(1440, 1000)
        driver.get(self.base+'/#/sets/ELL')
        wait = WebDriverWait(driver, 15)
        wait.until(lambda d: d.find_elements('css selector', '.card'))
        self.assertEqual(driver.execute_script("return getComputedStyle(document.querySelector('#grid')).display"), 'grid')
        self.assertEqual(driver.execute_script("return getComputedStyle(document.querySelector('aside')).position"), 'fixed')
        self.assertGreaterEqual(driver.find_element('css selector', 'main').rect['x'],
                                driver.find_element('css selector', 'aside').rect['width'])
        driver.find_element('css selector', '[aria-label="Expand A"]').click()
        self.assertTrue(driver.find_element('css selector', '[title="A / Bars"]').is_displayed())
        driver.find_element('css selector', '[aria-label="Collapse A"]').click()
        self.assertFalse(driver.find_element('css selector', '[title="A / Bars"]').is_displayed())
        for width in [1440, 390]:
            with self.subTest(width=width):
                driver.set_window_size(width, 1000)
                self.assertTrue(driver.execute_script('return document.documentElement.scrollWidth<=innerWidth'))
        self.assertEqual(driver.execute_script("return getComputedStyle(document.querySelector('aside')).position"), 'static')

    def test_home_to_method_and_subset_navigation(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait

        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options, service=Service(shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        driver.get(self.base)
        wait.until(lambda d: d.find_elements('css selector', '#method-cards button'))
        self.assertTrue(driver.find_element('id', 'home-view').is_displayed())
        self.assertEqual(len(driver.find_elements('css selector', '#method-cards button:first-child .navigation-picture svg')), 2)
        self.assertFalse(driver.find_element('id', 'library-view').is_displayed())
        driver.find_element('css selector', '#method-cards button').click()
        wait.until(lambda d: d.find_element('id', 'method-view').is_displayed())
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#subset-cards h2')], ['CLL', 'ELL'])
        self.assertEqual(len(driver.find_elements('css selector', '#subset-cards .navigation-picture svg')), 2)
        driver.find_elements('css selector', '#subset-cards button')[0].click()
        wait.until(lambda d: d.title == 'CLL · Cube Library')
        self.assertEqual(len(driver.find_elements('css selector', '.card')), 42)
        driver.back()
        wait.until(lambda d: d.find_element('id', 'method-view').is_displayed())
        driver.find_elements('css selector', '#subset-cards button')[1].click()
        wait.until(lambda d: d.title == 'ELL · Cube Library')
        self.assertEqual(len(driver.find_elements('css selector', '.card')), 30)
        driver.find_element('css selector', '.page-links a').click()
        wait.until(lambda d: d.find_element('id', 'home-view').is_displayed())
        driver.find_elements('css selector', '#method-cards button')[1].click()
        wait.until(lambda d: d.title == 'CFOP · Cube Library')
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#subset-cards h2')], ['OLL', 'PLL'])
        driver.find_elements('css selector', '#subset-cards button')[0].click()
        wait.until(lambda d: d.title == 'OLL · Cube Library')
        self.assertEqual(driver.find_element('id', 'library-back').get_attribute('href').split('#')[-1], '/methods/cfop')
        self.assertEqual(len(driver.find_elements('css selector', '.card')), 57)
        driver.find_element('id', 'library-back').click()
        wait.until(lambda d: d.title == 'CFOP · Cube Library')
        driver.find_elements('css selector', '#subset-cards button')[1].click()
        wait.until(lambda d: d.title == 'PLL · Cube Library')
        driver.find_element('css selector', '.page-links a[href="#/advanced"]').click()
        wait.until(lambda d: d.title == 'Advanced subsets · Cube Library')
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#subset-cards h2')], ['WV', 'SV'])
        driver.find_elements('css selector', '#subset-cards button')[0].click()
        wait.until(lambda d: d.title == 'WV · Cube Library')
        self.assertIn('#/advanced', driver.find_element('id', 'library-back').get_attribute('href'))
        driver.find_element('id', 'library-back').click()
        wait.until(lambda d: d.title == 'Advanced subsets · Cube Library')
        driver.find_elements('css selector', '#subset-cards button')[1].click()
        wait.until(lambda d: d.title == 'SV · Cube Library')
        driver.find_element('css selector', '.page-links a').click()
        wait.until(lambda d: d.find_element('id', 'home-view').is_displayed())
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#advanced-cards h2')], ['WV', 'SV'])
