"""Скриншоты Jenkins в настоящем браузере; Selenium из lab4/.venv."""
import argparse
import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--number', type=int, required=True)
args = parser.parse_args()
settings = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if '=' in line)
os.environ.setdefault('SE_CACHE_PATH', str(ROOT.parent / 'lab4/.selenium'))
options = webdriver.FirefoxOptions()
options.add_argument('-headless')
driver = webdriver.Firefox(options=options)
try:
    driver.set_window_size(1600, 1100)
    wait = WebDriverWait(driver, 30)
    driver.get('http://127.0.0.1:18080/login')
    wait.until(lambda d: d.find_elements(By.NAME, 'j_username'))
    driver.find_element(By.NAME, 'j_username').send_keys(settings['JENKINS_ADMIN_USER'])
    driver.find_element(By.NAME, 'j_password').send_keys(settings['JENKINS_ADMIN_PASSWORD'])
    driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()
    wait.until(lambda d: '/login' not in d.current_url)
    for name, suffix in [('job', '/job/openbmc-ci/'),
                         ('build', f'/job/openbmc-ci/{args.number}/'),
                         ('tests', f'/job/openbmc-ci/{args.number}/testReport/')]:
        driver.get('http://127.0.0.1:18080' + suffix)
        wait.until(lambda d: d.find_elements(By.ID, 'main-panel'))
        if name == 'job':
            wait.until(lambda d: 'QEMU OpenBMC' in d.find_element(By.TAG_NAME, 'body').text)
        driver.save_screenshot(str(ROOT / 'results' / f'jenkins-{name}.png'))
        (ROOT / 'results' / f'jenkins-{name}.txt').write_text(driver.find_element(By.TAG_NAME, 'body').text)
        print(f'Сохранён скриншот Jenkins: {name}; HTTP-страница {suffix}')
finally:
    driver.quit()
