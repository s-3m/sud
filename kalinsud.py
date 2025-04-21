import datetime
import calendar
import os

import pandas as pd
import undetected_chromedriver as uc
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.expected_conditions import any_of
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
from twocaptcha import TwoCaptcha
from alive_progress import alive_it
from loguru import logger
import pandas.io.formats.excel
from dotenv import load_dotenv
from twocaptcha.api import ApiException

load_dotenv(".env")

pandas.io.formats.excel.ExcelFormatter.header_style = None

solver = TwoCaptcha(os.getenv("CAPTCHA_TOKEN"))
print(os.getenv("CAPTCHA_TOKEN"))
URL = "https://lenms1.kln.msudrf.ru/modules.php?name=sud_delo&op=hl"
sud = None

def get_dates_list(period):
    year = datetime.datetime.now().year
    now_month = datetime.datetime.now().month
    if period == "1":
        month_range = now_month + 1
    else:
        month_range = 13
    now_day = datetime.datetime.now().day
    dates = []
    for month in range(now_month, month_range):
        # Получаем количество дней в месяце
        _, num_days = calendar.monthrange(year, month)
        # Генерируем все даты месяца
        for day in range(now_day, num_days + 1):
            dates.append(datetime.date(year, month, day))
            now_day = 1
    formated_dates = [i.strftime("%d.%m.%Y") for i in dates]
    return formated_dates


def get_row_data(row: BeautifulSoup, date: str, sud_name: str) -> dict | None:
    td_list = row.find_all("td")
    codex = td_list[-2].text.split("- ст. ")[-1].replace(";", "").strip()
    if codex.split(" ")[0] in ("12.26", "12.27", "12.8"):
        row_data = {
            "Суд": sud_name,
            "Номер дела": td_list[0].text,
            "Дата": date,
            "Время слушания": td_list[1].text,
            "Событие": td_list[2].text,
            "ФИО": td_list[3].text.split(" - ст")[0],
        }
        return row_data
    return None


def get_table_data(page_html, date) -> list[dict]:
    table_data = []
    soup = BeautifulSoup(page_html, "lxml")
    sud_name = soup.find("p", class_="court-name").text.strip()
    needed_rows = soup.find_all("tr", {"valign": "top"})
    for row in needed_rows:
        row_data = get_row_data(row, date, sud_name)
        if row_data:
            table_data.append(row_data)
    return table_data


def get_captcha_answer(img_path: str) -> str:
    result = solver.normal(file=img_path, lang="ru")
    return result.get("code")


def generate_sud_urls():
    linin_area = [(f"https://lenms{i}.kln.msudrf.ru/modules.php?name=sud_delo&op=hl&H_date=", "Ленинский район", f"{i} участок из 8") for i in range(1, 9)]
    msk_area = [(f"https://moskms{i}.kln.msudrf.ru/modules.php?name=sud_delo&op=hl&H_date=", "Московский район", f"{i} участок из 8") for i in range(1, 9)]
    centr_area = [(f"https://centms{i}.kln.msudrf.ru/modules.php?name=sud_delo&op=hl&H_date=", "Центральный район", f"{i} участок из 6") for i in range(1, 7)]

    return linin_area + msk_area + centr_area


def get_search_result(driver, period):
    all_data = []

    all_urls = generate_sud_urls()

    locators = [
        EC.presence_of_element_located((By.XPATH, '//*[@id="tablcont"]')),
        EC.presence_of_element_located((By.XPATH, '//*[@id="search_results"]/div')),
        EC.presence_of_element_located((By.XPATH, '//*[@id="kcaptchaForm"]/div/div[1]/img'))
    ]

    dates = get_dates_list(period)
    for search_pcs in all_urls:
        logger.info(f"Собираю данные по {search_pcs[1]} - {search_pcs[2]}")
        for date in alive_it(dates):
            try:
                driver.get(f"{search_pcs[0]}{date}")
                try:
                    element_on_page = WebDriverWait(driver, 120).until(
                        any_of(*locators)
                    )
                    elem_tag = element_on_page.tag_name
                except TimeoutException:
                    continue
                page_source = None
                if elem_tag == "img":
                    captcha_flag = False
                    while True:
                        try:
                            element_on_page = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, '//*[@id="kcaptchaForm"]/div/div[1]/img')))
                        except TimeoutException:
                            captcha_flag = True
                            break
                        for _ in range(5):
                            try:
                                element_on_page = WebDriverWait(driver, 20).until(
                                    EC.presence_of_element_located((By.XPATH, '//*[@id="kcaptchaForm"]/div/div[1]/img')))
                                element_on_page.screenshot(f"captcha.png")
                                captcha_answer = get_captcha_answer("captcha.png")
                                break
                            except ApiException:
                                driver.refresh()
                            except TimeoutException:
                                continue
                        try:
                            driver.find_element(By.XPATH, '//*[@id="kcaptchaForm"]/div/div[2]/input').send_keys(captcha_answer,
                                                                                                                Keys.ENTER)
                        except NoSuchElementException:
                            pass
                        after_captcha_tag_name = "div"
                        try:
                            after_captcha = WebDriverWait(driver, 20).until(
                                any_of(*locators)
                            )
                            after_captcha_tag_name = after_captcha.tag_name
                        except TimeoutException:
                            for _ in range(5):
                                driver.refresh()
                                try:
                                    after_captcha = WebDriverWait(driver, 20).until(
                                        any_of(*locators)
                                    )
                                    after_captcha_tag_name = after_captcha.tag_name
                                    break
                                except TimeoutException:
                                    pass

                        if after_captcha_tag_name == "table":
                            page_source = driver.page_source
                            break
                        elif after_captcha_tag_name == "div":
                            captcha_flag = True
                            break

                    if captcha_flag:
                        continue
                elif elem_tag == "div":
                    continue

                elif elem_tag == "table":
                    page_source = driver.page_source

                table_data = get_table_data(page_source, date)
                all_data.extend(table_data)
            except Exception as e:
                logger.exception(e)
                continue

    try:
        pd.DataFrame(all_data).sort_values(by="Дата").to_excel("Kaliningrad.xlsx", index=False)
    except Exception as e:
        logger.exception(e)
        pd.DataFrame(all_data).to_excel("Kaliningrad.xlsx", index=False)

def main():
    while True:
        period = input("На какой период требуется собрать данные?\n[1] - На текущий месяц\n[2] - На весь год\nВведите номер позиции и нажмите ENTER: ")
        if period in ("1", "2",):
            break
        else:
            print("Указан неверный номер позиции!")


    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")  # Игнорировать ошибки сертификата
    chrome_options.add_argument("--allow-insecure-localhost")  # Разрешить небезопасные локальные хосты
    try:
        driver = uc.Chrome(headless=True, version_main=134, options=chrome_options)
        # driver.set_page_load_timeout(13) # Ждём загрузку страницы только 13 секунды
        get_search_result(driver, period)
        input("Сбор данных успешно завершён. Нажмите любую кнопку для выхода")
    except Exception as e:
        logger.exception(e)
        print("Во время сбора данных произошла ошибка. Сайт работает не стабильно. Повторите позже.")
    finally:
        os.remove("captcha.png")
        driver.quit()


if __name__ == '__main__':
    main()
