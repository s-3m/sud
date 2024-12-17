import time
from pprint import pprint

import pandas as pd
import undetected_chromedriver as uc
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import threading

from urllib3.exceptions import MaxRetryError

cookies = {
    '_ym_uid': '1730894777226644708',
    '_ym_d': '1730894777',
    '_ym_isad': '2',
}

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ru,en;q=0.9',
    'Connection': 'keep-alive',
    # 'Cookie': '_ym_uid=1730894777226644708; _ym_d=1730894777; _ym_isad=2',
    'Referer': 'https://mirsud.spb.ru/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 YaBrowser/24.10.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "YaBrowser";v="24.10", "Yowser";v="2.5"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

all_result = []
page_count = 0


def get_data_on_page(page):
    global page_count
    soup = BeautifulSoup(page, 'lxml')
    table = soup.find('table')
    all_rows = table.find_all('tr')[1:]
    for row in all_rows:
        row_data = row.find_all('td')
        result = {
            "Участок": row_data[0].text.replace("№", "").strip(),
            "Номер дела": row_data[1].text.strip(),
            "Статья": row_data[2].text.strip(),
            "Дата": row_data[3].text.strip(),
            "Статус": row_data[4].text.strip(),
            "Участники": row_data[5].text.strip(),
        }
        pprint(result)
        all_result.append(result)
    page_count += 1
    print(f"\rСделал {page_count} страниц из 600 (значение примерное).", end='')
    # page_result.append(result)


def get_page(article, month_number=1):
    # all_result = []
    count = 1
    for i in range(month_number, 3):
        driver = uc.Chrome(headless=True, no_sandbox=False, driver_executable_path="chromedriver.exe")
        wait = WebDriverWait(driver, 20)
        driver.get("https://mirsud.spb.ru/cases/")
        wait.until(EC.visibility_of_element_located(
            (By.XPATH, "/html/body/div[1]/main/section[2]/div[1]/div/form/div/div[2]/div/div[2]/fieldset/button")))

        art_input = driver.find_element(By.ID, "id_article")
        art_input.clear()
        art_input.send_keys(f"{article}")

        # print(f'\n--- {i} ---{threading.current_thread().name}')
        date_from_input = driver.find_element(By.XPATH,
                                              "/html/body/div[1]/main/section[2]/div[1]/div/form/div/div[1]/div[2]/div[3]/div/input")
        month = i
        date_from_input.clear()
        date_from_input.send_keys(f"01.{month}.2024")

        date_to_input = driver.find_element(By.XPATH,
                                            "/html/body/div[1]/main/section[2]/div[1]/div/form/div/div[1]/div[2]/div[4]/div/input")
        date_to_input.clear()
        if month == 12:
            date_to_input.send_keys(f"31.{month}.2024")
        else:
            date_to_input.send_keys(f"01.{month + 1}.2024")
        date_to_input.send_keys(Keys.ENTER)
        # page_source = driver.page_source
        while True:
            try:
                wait.until(EC.visibility_of_element_located((By.XPATH, "//tr[@ng-repeat='case in cases']")))
                # page_source = driver.page_source
            except TimeoutException:
                try:
                    wait.until(EC.visibility_of_element_located((By.XPATH, "//td[contains(text(), 'Судебные дела, удовлетворяющие запросу, не найдены')]")))
                    break
                except:
                    driver.close()
                    driver.quit()
                    get_page(article, i)
            time.sleep(2)
            try:
                get_data_on_page(driver.page_source)
            except:
                pass
            try:
                if count % 50 == 0:
                    time.sleep(120)
                next_page_btn = driver.find_element(By.CLASS_NAME, "pag__next")
                next_page_btn.click()
                count += 1
            except:
                driver.quit()
                break


def main():
    try:
        print("Начинаю сбор данных...")
        print()
        threads = []
        articles = ["12.26", "12.27", "12.8"]
        for article in articles:
            thread = threading.Thread(target=get_page, args=(article,))
            thread.start()
            threads.append(thread)
            time.sleep(4)
        for thread in threads:
            thread.join()
    except:
        pass

    # for article in articles:
    #     get_page(article)


    print()


if __name__ == '__main__':
    main()
    pd.DataFrame(all_result).drop_duplicates(subset="Номер дела").to_excel("spb_result.xlsx", index=False)
    input("Сбор данных завершён.\n Вы можете закрыть окно!")


