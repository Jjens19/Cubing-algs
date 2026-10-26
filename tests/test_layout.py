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
        driver.find_element('id', 'library-back').click()
        wait.until(lambda d: d.title == 'CFOP · Cube Library')
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#advanced-cards h2')], ['WV', 'SV', 'COLL', 'Anti PLL'])
        for index, name, count in ((0, 'WV', 27), (1, 'SV', 27), (2, 'COLL', 40)):
            driver.find_elements('css selector', '#advanced-cards button')[index].click()
            wait.until(lambda d: d.title == name+' · Cube Library')
            self.assertEqual(len(driver.find_elements('css selector', '.card')), count)
            self.assertIn('#/methods/cfop', driver.find_element('id', 'library-back').get_attribute('href'))
            driver.find_element('id', 'library-back').click()
            wait.until(lambda d: d.title == 'CFOP · Cube Library')
        driver.find_element('css selector', '.page-links a[href="#/methods/roux"]').click()
        wait.until(lambda d: d.title == 'Roux · Cube Library')
        self.assertIn('two opposite', driver.find_element('id', 'method-description').text)
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#subset-cards h2')], ['CMLL', 'LSE'])
        self.assertIn('M slice', driver.find_elements('css selector', '#subset-cards p')[0].text)
        driver.find_elements('css selector', '#subset-cards button')[0].click()
        wait.until(lambda d: d.title == 'CMLL · Cube Library')
        self.assertEqual(len(driver.find_elements('css selector', '.card')), 42)
        self.assertIn('both Roux blocks', driver.find_element('id', 'subtitle').text)
        wait.until(lambda d: d.execute_script("return [...document.querySelectorAll('.preview img')].every(i=>i.complete&&i.naturalWidth>0)"))
        driver.find_element('id', 'library-back').click()
        wait.until(lambda d: d.title == 'Roux · Cube Library')
        driver.find_elements('css selector', '#subset-cards button')[1].click()
        wait.until(lambda d: d.title == 'LSE · Cube Library')
        self.assertIn('six remaining edges', driver.find_element('id', 'subtitle').text)
        self.assertEqual(len(driver.find_elements('css selector', '.card')), 9)
        self.assertIn('EO4A', driver.find_element('id', 'subtitle').text)
        wait.until(lambda d: d.execute_script("return [...document.querySelectorAll('.preview img')].every(i=>i.complete&&i.naturalWidth>0)"))
        driver.find_element('id', 'library-back').click()
        wait.until(lambda d: d.title == 'Roux · Cube Library')
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#advanced-cards h2')], ['EOLR'])
        driver.find_element('css selector', '#advanced-cards button').click()
        wait.until(lambda d: d.title == 'EOLR · Cube Library')
        self.assertEqual(len(driver.find_elements('css selector', '.card')), 46)
        self.assertIn('#/methods/roux', driver.find_element('id', 'library-back').get_attribute('href'))
        driver.find_element('css selector', '.page-links a').click()
        wait.until(lambda d: d.find_element('id', 'home-view').is_displayed())
        self.assertEqual(len(driver.find_elements('css selector', '#home-view #advanced-cards')), 0)
        driver.find_element('css selector', '.page-links a[href="#/methods/cfce"]').click()
        wait.until(lambda d: d.title == 'CFCE · Cube Library')
        self.assertEqual([e.text for e in driver.find_elements('css selector', '#advanced-cards h2')], ['Anti PLL'])
        driver.find_element('css selector', '#advanced-cards button').click()
        wait.until(lambda d: d.title == 'Anti PLL · Cube Library')
        self.assertEqual(len(driver.find_elements('css selector', '.card')), 22)
        shared_ids = [c['id'] for c in self.request('/api/library')[2]['cases'] if c['alg_set'] == 'Anti PLL']
        driver.find_element('css selector', '.card .progress').click()
        wait.until(lambda d: d.find_element('css selector', '.card .progress').text == '◐ Learning')
        self.assertIn('#/methods/cfce', driver.find_element('id', 'library-back').get_attribute('href'))
        driver.find_element('css selector', '.page-links a[href="#/methods/cfop"]').click()
        wait.until(lambda d: d.title == 'CFOP · Cube Library')
        driver.find_elements('css selector', '#advanced-cards button')[3].click()
        wait.until(lambda d: d.title == 'Anti PLL · Cube Library')
        self.assertEqual([c['id'] for c in self.request('/api/library')[2]['cases'] if c['alg_set'] == 'Anti PLL'], shared_ids)
        self.assertEqual(driver.find_element('css selector', '.card .progress').text, '◐ Learning')
        self.assertIn('#/methods/cfop', driver.find_element('id', 'library-back').get_attribute('href'))

    def test_cubing_wiki_navigation_search_and_mobile(self):
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
        driver.find_element('id', 'info-button').click()
        wait.until(lambda d: d.find_element('id', 'wiki-view').is_displayed())
        self.assertFalse(driver.find_element('id', 'home-view').is_displayed())
        driver.find_element('css selector', '#wiki-article a[href="#/info/method/roux"]').click()
        wait.until(lambda d: d.find_element('css selector', '#wiki-article h2').text == 'Roux')
        self.assertIn('1×2×3', driver.find_element('id', 'wiki-article').text)
        driver.find_element('css selector', '#wiki-article a[href="#/info/subset/EOLR"]').click()
        wait.until(lambda d: d.find_element('css selector', '#wiki-article h2').text == 'EOLR')
        self.assertIn('M2', driver.find_element('id', 'wiki-article').text)
        driver.find_element('css selector', '#wiki-article a[href="#/sets/EOLR"]').click()
        wait.until(lambda d: d.title == 'EOLR · Cube Library')
        driver.find_element('id', 'subset-info').click()
        wait.until(lambda d: d.find_element('css selector', '#wiki-article h2').text == 'EOLR')
        search = driver.find_element('id', 'wiki-search')
        search.send_keys('Anti PLL')
        links = driver.find_elements('css selector', '#wiki-topics .wiki-subtopic')
        self.assertEqual(len(links), 2)
        links[0].click()
        wait.until(lambda d: d.find_element('css selector', '#wiki-article h2').text == 'Anti PLL')
        related = [e.text for e in driver.find_elements('css selector', '#wiki-article a')]
        self.assertIn('CFCE', related)
        self.assertIn('CFOP', related)
        search.clear()
        search.send_keys('no-such-topic')
        self.assertIn('No matching topics.', driver.find_element('id', 'wiki-topics').text)
        driver.set_window_size(480, 900)
        self.assertLessEqual(driver.execute_script('return document.documentElement.scrollWidth'), driver.execute_script('return window.innerWidth'))
        driver.get(self.base+'/#/info/subset/OLL')
        wait.until(lambda d: d.find_element('css selector', '#wiki-article h2').text == 'OLL')
        self.assertIn('first two layers', driver.find_element('id', 'wiki-article').text)
        driver.get(self.base+'/#/info/subset/Unknown')
        wait.until(lambda d: 'not found' in d.find_element('id', 'wiki-article').text)

    def test_notation_guide_moves_and_animation(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait, Select
        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options, service=Service(shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        driver.get(self.base+'/#/info/notation')
        wait.until(lambda d: d.find_elements('css selector', '#notation-cube polygon'))
        move = Select(driver.find_element('id', 'notation-move'))
        self.assertEqual([o.get_attribute('value') for o in move.options], list('UDRLFBMESxyz'))
        for name, direction in [('M','L'),('E','D'),('S','F'),('x','R'),('y','U'),('z','F')]:
            move.select_by_value(name)
            self.assertIn('same direction as '+direction, driver.find_element('id', 'notation-description').text)
            self.assertTrue(driver.find_elements('css selector', '#notation-cube polygon[data-moving="true"]'))
            if name in 'xyz':
                self.assertFalse(driver.find_elements('css selector', '#notation-cube polygon[data-moving="false"]'))
            else:
                self.assertTrue(driver.find_elements('css selector', '#notation-cube polygon[data-moving="false"]'))
        before = driver.find_element('css selector', '#notation-cube polygon').get_attribute('points')
        driver.find_element('id', 'notation-play').click()
        wait.until(lambda d: d.find_element('id', 'notation-progress').get_attribute('value') == '100')
        self.assertNotEqual(before, driver.find_element('css selector', '#notation-cube polygon').get_attribute('points'))
        self.assertIn('90° / 90°', driver.find_element('id', 'notation-status').text)
        Select(driver.find_element('id', 'notation-suffix')).select_by_value("'")
        self.assertIn('Reverse', driver.find_element('id', 'notation-description').text)
        Select(driver.find_element('id', 'notation-suffix')).select_by_value('2')
        driver.find_elements('css selector', '.notation-actions button')[2].click()
        self.assertIn('180° / 180°', driver.find_element('id', 'notation-status').text)
        move.select_by_value('D')
        self.assertIn('D', driver.find_element('id', 'notation-cube').text)
        driver.set_window_size(480, 900)
        self.assertLessEqual(driver.execute_script('return document.documentElement.scrollWidth'), driver.execute_script('return window.innerWidth'))
        driver.find_element('id', 'notation-play').click()
        driver.find_element('id', 'info-button').click()
        wait.until(lambda d: d.find_element('css selector', '#wiki-article h2').text == 'Welcome to the cubing wiki')
        self.assertEqual(driver.find_element('id', 'notation-progress').get_attribute('value'), '0')

    def test_dark_mode_persistence_and_cube_colors(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        options = Options()
        options.add_argument('-headless')
        options.set_preference('ui.systemUsesDarkTheme', 1)
        driver = webdriver.Firefox(options=options, service=Service(shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        driver.get(self.base+'/#/sets/CLL')
        wait.until(lambda d: d.find_elements('css selector', '.case-open'))
        self.assertEqual(driver.find_element('tag name', 'html').get_attribute('data-theme'), 'dark')
        self.assertEqual(driver.find_element('id', 'theme-toggle').get_attribute('aria-pressed'), 'true')
        self.assertEqual(driver.execute_script('return getComputedStyle(document.documentElement).backgroundColor'), 'rgb(21, 28, 25)')
        driver.find_element('css selector', 'button[aria-label="Open U1"]').click()
        wait.until(lambda d: d.find_element('id', 'detail').get_property('open'))
        self.assertEqual(driver.find_element('css selector', '#cube rect[data-key="U0"]').get_attribute('fill'), '#ffdd00')
        self.assertEqual(driver.execute_script('return getComputedStyle(document.getElementById("name")).backgroundColor'), 'rgb(34, 45, 38)')
        driver.find_element('id', 'close').click()
        driver.find_element('id', 'theme-toggle').click()
        self.assertEqual(driver.find_element('tag name', 'html').get_attribute('data-theme'), 'light')
        driver.refresh()
        wait.until(lambda d: d.find_elements('css selector', '.case-open'))
        self.assertEqual(driver.find_element('tag name', 'html').get_attribute('data-theme'), 'light')
        driver.find_element('id', 'theme-toggle').click()
        driver.get(self.base+'/#/info')
        wait.until(lambda d: d.find_element('id', 'wiki-view').is_displayed())
        self.assertEqual(driver.find_element('tag name', 'html').get_attribute('data-theme'), 'dark')
        self.assertEqual(driver.execute_script('return getComputedStyle(document.getElementById("wiki-article")).backgroundColor'), 'rgb(34, 45, 38)')
        driver.set_window_size(480, 900)
        self.assertLessEqual(driver.execute_script('return document.documentElement.scrollWidth'), driver.execute_script('return window.innerWidth'))

    def test_full_cube_recognition_editor_and_practice_hint(self):
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options, service=Service(shutil.which('geckodriver')))
        self.addCleanup(driver.quit)
        wait = WebDriverWait(driver, 15)
        for subset in ('CMLL', 'EOLR', 'LSE'):
            driver.get(self.base+'/#/sets/'+subset)
            wait.until(lambda d: d.find_elements('css selector', '.case-open'))
            driver.find_element('css selector', '.case-open').click()
            wait.until(lambda d: d.find_element('id', 'detail').get_property('open'))
            self.assertEqual(len(driver.find_elements('css selector', '#cube polygon[data-key]')), 54)
            driver.find_element('css selector', 'button[aria-label="Blue"]').click()
            driver.find_element('css selector', '#cube polygon[data-key="F7"]').click()
            driver.find_element('id', 'highlight').click()
            driver.find_element('css selector', '#cube polygon[data-key="F7"]').click()
            self.assertEqual(driver.find_element('css selector', '#cube polygon[data-key="F7"]').get_attribute('fill'), '#0000ff')
            self.assertEqual(driver.find_element('css selector', '#cube polygon[data-key="F7"]').get_attribute('aria-pressed'), 'true')
            driver.find_element('id', 'rotate-layer').click()
            self.assertEqual(driver.find_element('css selector', '#cube polygon[data-key="F7"]').get_attribute('fill'), '#0000ff')
            driver.find_element('id', 'use-drawing').click()
            driver.find_element('css selector', '#case-form button[type="submit"]').click()
            wait.until(lambda d: not d.find_element('id', 'detail').get_property('open'))
            wait.until(lambda d: d.find_elements('css selector', '.preview .full-cube-diagram'))
            self.assertEqual(len(driver.find_elements('css selector', '.preview .full-cube-diagram')[0].find_elements('css selector', 'polygon')), 54)
            driver.find_element('css selector', '.case-open').click()
            wait.until(lambda d: d.find_element('id', 'detail').get_property('open'))
            self.assertEqual(driver.find_element('css selector', '#cube polygon[data-key="F7"]').get_attribute('fill'), '#0000ff')
            driver.find_element('id', 'close').click()
            from src import server
            with server.connect() as db:
                db.execute('UPDATE cases SET learning=1 WHERE alg_set=?', (subset,))
            driver.refresh()
            wait.until(lambda d: d.find_elements('css selector', '.case-open'))
            driver.find_element('id', 'start-practice').click()
            wait.until(lambda d: not d.find_element('id', 'practice-hint-button').get_property('disabled'))
            driver.find_element('id', 'practice-hint-button').click()
            wait.until(lambda d: len(d.find_elements('css selector', '#practice-hint-graphic polygon')) == 54)
            driver.find_element('id', 'close-practice').click()
