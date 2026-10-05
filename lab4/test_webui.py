"""Selenium: авторизация и два кейса варианта 24 на настоящем Web UI OpenBMC."""
import base64
import json
import os
from pathlib import Path
import re
import ssl
import time
import urllib.request

import pytest
from selenium import webdriver
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select

BASE = os.environ.get('BMC_URL', 'https://127.0.0.1:3443').rstrip('/')
USER = os.environ.get('BMC_USER', 'root')
PASSWORD = os.environ.get('BMC_PASSWORD', '0penBmc')
OUT = Path(__file__).resolve().parent / 'results'
OUT.mkdir(exist_ok=True)
os.environ.setdefault('SE_CACHE_PATH', str(Path(__file__).resolve().parent / '.selenium'))


def account_policy():
    token = base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode()
    request = urllib.request.Request(BASE + '/redfish/v1/AccountService',
                                     headers={'Authorization': 'Basic ' + token})
    # Самоподписанный сертификат изолированного учебного BMC.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    with opener.open(request, timeout=30) as r:
        policy = json.load(r)
    (OUT / 'account-policy.json').write_text(json.dumps(policy, indent=2))
    return policy


@pytest.fixture
def browser(request):
    options = webdriver.FirefoxOptions()
    if os.environ.get('HEADLESS', '1') == '1':
        options.add_argument('-headless')
    options.accept_insecure_certs = True
    options.set_preference('intl.accept_languages', 'en-US, en')
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1440, 1000)
    driver.set_page_load_timeout(120)
    try:
        yield driver
    finally:
        name = re.sub(r'[^\w-]', '_', request.node.name)
        driver.save_screenshot(str(OUT / (name + '.png')))
        (OUT / (name + '.txt')).write_text(driver.find_element(By.TAG_NAME, 'body').text)
        try:
            logout(driver)
        finally:
            driver.quit()


def wait(driver):
    return WebDriverWait(driver, 90)


def login(driver, username=USER, password=PASSWORD, success=True, require_message=True):
    driver.get(BASE + '/#/login')
    field = wait(driver).until(EC.visibility_of_element_located((By.ID, 'username')))
    field.clear(); field.send_keys(username)
    field = driver.find_element(By.ID, 'password')
    field.clear(); field.send_keys(password)
    # Запоминается только HTTP-статус запроса, отправленного самим UI по нажатию кнопки.
    # Это позволяет отличить отклонённый вход от неотправленной/зависшей формы.
    driver.execute_script('''
        sessionStorage.removeItem('labLoginStatus');
        if (!window.labLoginObserver) {
          window.labLoginObserver = true;
          const original = XMLHttpRequest.prototype.open;
          XMLHttpRequest.prototype.open = function(method, url, ...rest) {
            if (method.toUpperCase() === 'POST' && String(url).endsWith('/SessionService/Sessions')) {
              this.addEventListener('loadend', () => {
                sessionStorage.setItem('labLoginStatus', String(this.status));
              });
            }
            return original.call(this, method, url, ...rest);
          };
        }
    ''')
    driver.find_element(By.CSS_SELECTOR, '[data-test-id="login-button-submit"]').click()
    if success:
        wait(driver).until(EC.visibility_of_element_located((By.ID, 'app-header-user__BV_toggle_')))
        assert username in driver.find_element(By.ID, 'app-header-user__BV_toggle_').text
        assert '/login' not in driver.current_url
    else:
        status = int(WebDriverWait(driver, 90, ignored_exceptions=(JavascriptException,)).until(lambda d: d.execute_script(
            "return sessionStorage.getItem('labLoginStatus')")))
        assert status == 401, f'Ожидался отказ авторизации HTTP 401, получен {status}'
        wait(driver).until(EC.visibility_of_element_located((By.ID, 'username')))
        assert not driver.find_elements(By.ID, 'app-header-user__BV_toggle_')
        if require_message:
            from selenium.common.exceptions import TimeoutException
            try:
                alert = WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
                    (By.ID, 'login-error-alert')))
            except TimeoutException:
                pytest.fail('Вход отклонён HTTP 401, но Web UI не показывает сообщение об ошибке')
            assert re.search(r'invalid|incorrect|unauthori|failed|locked', alert.text, re.I), alert.text


def logout(driver):
    buttons = driver.find_elements(By.ID, 'app-header-user__BV_toggle_')
    if buttons:
        buttons[0].click()
        wait(driver).until(EC.element_to_be_clickable((By.CSS_SELECTOR,
            '[data-test-id="appHeader-link-logout"]'))).click()
        wait(driver).until(EC.visibility_of_element_located((By.ID, 'username')))


def table(driver, route):
    target = BASE + '/#' + route
    if driver.current_url != target:
        driver.get(target)
    wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'main table')))
    # Дождаться завершения запросов Vue/Axios, а не только создания пустой таблицы.
    wait(driver).until(lambda d: not d.find_elements(By.CSS_SELECTOR, '.loading-overlay'))
    wait(driver).until(lambda d: d.find_element(By.CSS_SELECTOR, 'main table').get_attribute('aria-busy') != 'true')
    return driver.find_element(By.CSS_SELECTOR, 'main table')


def test_successful_login(browser):
    login(browser)


@pytest.mark.parametrize('username,password', [('lab4_missing', PASSWORD), (USER, 'WrongLabPassword1!')],
                         ids=['wrong_username', 'wrong_password'])
def test_invalid_credentials(browser, username, password):
    # Пункт задания: неверные данные отклонены, доступ не предоставлен.
    login(browser, username, password, success=False, require_message=False)


def test_voltage_monitoring(browser):
    """MON-02: показание выбранного датчика матплаты в заданных пределах."""
    login(browser)
    grid = table(browser, '/hardware-status/sensors')
    name = os.environ.get('VOLTAGE_SENSOR')
    if not name:
        rows = [r.text for r in grid.find_elements(By.CSS_SELECTOR, 'tbody tr')]
        pytest.skip('Blocked: датчик матплаты и допустимые пределы не заданы; строки UI: ' + repr(rows))
    rows = [r for r in grid.find_elements(By.CSS_SELECTOR, 'tbody tr') if name in r.text]
    assert len(rows) == 1, f'Датчик {name} не найден однозначно'
    if 'VOLTAGE_MIN' not in os.environ or 'VOLTAGE_MAX' not in os.environ:
        pytest.skip('Blocked: нужны допустимые VOLTAGE_MIN и VOLTAGE_MAX для выбранной линии')
    headers = [h.text.lower() for h in grid.find_elements(By.CSS_SELECTOR, 'thead th')]
    index = next(i for i, h in enumerate(headers) if 'current value' in h)
    for sample in range(3):
        if sample:
            time.sleep(5)
            browser.refresh()
            grid = table(browser, '/hardware-status/sensors')
        row = next(r for r in grid.find_elements(By.CSS_SELECTOR, 'tbody tr') if name in r.text)
        text = row.find_elements(By.CSS_SELECTOR, 'td')[index].text
        match = re.fullmatch(r'\s*([-+]?\d+(?:\.\d+)?)\s*V\s*', text)
        assert match, f'Ожидалось числовое значение в вольтах, получено {text!r}'
        assert float(os.environ['VOLTAGE_MIN']) <= float(match[1]) <= float(os.environ['VOLTAGE_MAX'])


def log_rows(driver):
    grid = table(driver, '/logs/event-logs')
    select = driver.find_elements(By.ID, 'pagination-items-per-page')
    if select:
        Select(select[0]).select_by_visible_text('View all')
    return {r.text for r in grid.find_elements(By.CSS_SELECTOR, 'tbody tr')
            if 'No items available' not in r.text and r.text.strip()}


def test_logs_on_error(browser):
    """LOG-02 через Web UI: новая запись об ошибке авторизации."""
    login(browser)
    before = log_rows(browser)
    logout(browser)
    login(browser, 'lab4_missing', 'WrongLabPassword1!', success=False, require_message=False)
    logout(browser)
    login(browser)
    deadline = time.monotonic() + 60
    new = set()
    while time.monotonic() < deadline:
        new = log_rows(browser) - before
        if any(re.search(r'login|auth|lab4_missing', row, re.I) and
               re.search(r'warning|critical', row, re.I) for row in new):
            return
        time.sleep(5)
        browser.refresh()
    pytest.fail('После подтверждённой ошибки входа за 60 с нет новой записи Warning/Critical '
                'об авторизации в Event logs. Новые строки: ' + repr(new))


def test_account_lockout(browser):
    """Порог берётся из конфигурации; отключённая блокировка — невыполненное предусловие."""
    policy = account_policy()
    threshold = policy['AccountLockoutThreshold']
    duration = policy['AccountLockoutDuration']
    if threshold == 0:
        pytest.skip('Blocked: AccountLockoutThreshold=0, блокировка отключена в образе')
    if duration == 0 or duration > 120 or threshold > 10:
        pytest.skip('Blocked: нужен отдельный тестовый аккаунт с ограниченной по времени блокировкой')
    login(browser)  # Сброс счётчика неудачных попыток.
    logout(browser)
    try:
        for _ in range(threshold):
            login(browser, USER, 'WrongLabPassword1!', success=False, require_message=False)
        # Отказ с правильным паролем отличает блокировку от обычного неверного ввода.
        login(browser, USER, PASSWORD, success=False, require_message=False)
    finally:
        time.sleep(duration + 2)
    login(browser)  # После истечения блокировки правильные данные снова работают.
