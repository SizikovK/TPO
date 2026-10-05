"""Проверка веб-запуска Locust браузером; требует Selenium из lab4/.venv."""
import json
import os
from pathlib import Path
import time

import urllib.request
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'lab6/results'
os.environ.setdefault('SE_CACHE_PATH', str(ROOT / 'lab4/.selenium'))
options = webdriver.FirefoxOptions()
options.add_argument('-headless')
driver = webdriver.Firefox(options=options)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch(path, timeout=10):
    with opener.open('http://127.0.0.1:8089' + path, timeout=timeout) as response:
        return response.read().decode()


def stats():
    return json.loads(fetch('/stats/requests'))
try:
    driver.set_window_size(1440, 1000)
    driver.get('http://127.0.0.1:8089')
    wait = WebDriverWait(driver, 30)
    wait.until(lambda d: d.find_elements(By.NAME, 'userCount'))
    for name, value in [('userCount', '10'), ('spawnRate', '2')]:
        field = driver.find_element(By.NAME, name)
        field.clear()
        field.send_keys(value)
    driver.save_screenshot(str(OUT / 'web-start.png'))
    print('Открыт http://127.0.0.1:8089; классы OpenBMCUser и PublicAPIUser; пользователи=10, скорость=2/с', flush=True)
    driver.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()
    wait.until(lambda d: stats()['state'] == 'running')
    print('Нажата START; нагрузка запущена через браузер', flush=True)
    time.sleep(40)
    snapshot = stats()
    (OUT / 'web-stats.json').write_text(json.dumps(snapshot, indent=2))
    driver.save_screenshot(str(OUT / 'web-running.png'))
    (OUT / 'web-running.txt').write_text(driver.find_element(By.TAG_NAME, 'body').text)
    print(f"state={snapshot['state']}; users={snapshot['user_count']}; total_rps={snapshot['total_rps']}", flush=True)
    stop = driver.find_elements(By.XPATH, "//button[contains(translate(., 'STOP', 'stop'), 'stop')]")
    if not stop:
        raise RuntimeError('Не найдена кнопка STOP')
    stop[0].click()
    wait.until(lambda d: stats()['state'] == 'stopped')
    print('Нажата STOP; state=stopped', flush=True)
    driver.save_screenshot(str(OUT / 'web-stopped.png'))
    for url, filename in [('/stats/requests/csv', 'web-download.csv'), ('/stats/failures/csv', 'web-failures-download.csv')]:
        (OUT / filename).write_text(fetch(url))
    print('Статистика и скриншоты сохранены в lab6/results', flush=True)
finally:
    fetch('/stop')
    driver.quit()
