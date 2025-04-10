from concurrent.futures import ThreadPoolExecutor
import time
import asyncio
import pandas as pd
import requests
import urllib3
from alive_progress import alive_it
from bs4 import BeautifulSoup as bs
import pandas.io.formats.excel
from loguru import logger

pandas.io.formats.excel.ExcelFormatter.header_style = None
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
mos_sud_url = "https://mos-sud.ru/search"

cur_states = [("af3545b", "Назначено судебное заседание"), ("80c39ae", "Отложено")]
codex = ["12.27", "12.8", "12.26"]
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'ru,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    # 'Cookie': '_ym_uid=1730271176292941916; _ym_d=1730271176; _ym_isad=2; maintenance_closed=true',
    'Referer': 'https://mos-sud.ru/search?formType=fullForm',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "YaBrowser";v="24.10", "Yowser";v="2.5"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}
cookies = {
    'currentCourt': '',
    '_ym_uid': '1730271176292941916',
    '_ym_d': '1730271176',
    '_ym_isad': '2',
    'c-dis': '1',
}
proxy = {
    "https": "http://ohbav3:3j9HtQ@45.139.109.130:8000",
    "http": "http://ohbav3:3j9HtQ@45.139.109.130:8000"
}


def get_case_data(case_link: str):
    try:
        case_result = {}
        response = requests.get(f"https://mos-sud.ru{case_link}", headers=headers, verify=False)
        soup = bs(response.text, "lxml")
        all_rows = soup.find_all("div", class_="row_card")
        if not soup.find("div", id="sessions"):
            print(case_link)
        mini_tabs = soup.find("div", id="sessions").find("tbody").find_all("td")


        for i in all_rows:
            title = i.find("div", class_="left").text.strip()
            value = i.find("div", class_="right").text.strip()
            case_result[title] = value
        case_result["Дата"] = mini_tabs[0].text.strip()
        case_result["Зал"] = mini_tabs[1].text.strip()
        case_result["Стадия"] = mini_tabs[2].text.strip()
        return case_result
    except Exception as e:
        logger.error(e)
        return None

async def get_gather_data():
    print("Анализирую данные...")
    tasks = []
    result = []
    for cur_state in cur_states:
        params = {'year': "2025", 'formType': 'fullForm', "processType": "3"}
        for item in codex:
            params["publishingState"] = cur_state[0]
            params["codex"] = item
            response =  requests.get(mos_sud_url, params=params, headers=headers, cookies=cookies, verify=False,)
            time.sleep(2)
            soup = bs(response.text, 'lxml')
            check = soup.find("div", class_="resultsearch_text").text
            if check.strip() == "По вашему запросу ничего не найдено":
                continue
            else:
                try:
                    paginator = soup.find("div", class_="pagenav").find('input').get('value')
                except AttributeError:
                    paginator = 1

            for page_num in range(1, int(paginator) + 1):
                params['page'] = str(page_num)
                tasks.append(params.copy())
            del params['page']
        time.sleep(2)

    print(f"Для обработки найдено {len(tasks)} страниц")
    time.sleep(2)
    print(f"Начинаю сбор данных")
    print(f"Состояние выполнения:")
    for param in alive_it(tasks):
        page_response = requests.get(mos_sud_url, params=param, headers=headers, verify=False)
        time.sleep(1)
        # try:
        soup = bs(page_response.text, 'lxml')
        data_cases = soup.find("table", class_="custom_table").find_all('nobr')[1:]
        cases_links = [i.find('a').get('href') for i in data_cases if i.find('a')]
        with ThreadPoolExecutor(max_workers=1) as executor:
            features = []
            for case_link in cases_links:
                task = executor.submit(get_case_data, case_link)
                features.append(task)
            for feature_result in features:
                if feature_result.result() is not None:
                    result.append(feature_result.result())

    pd.DataFrame(result).to_excel('mos_sud_result.xlsx', index=False)
    print("Сбор данных завершён успешно. Вы можете закрыть окно.")


def main():
    try:
        asyncio.run(get_gather_data())
    except:
        logger.exception("ERROR")
        print(
            "---------------!!!!!!!---------------\nПроизошла ошибка.\nВозможно проблемы с сайтом или вашим интернетом.\nПопробуйте перезапустить программу!\n---------------!!!!!!!---------------")
    print()
    input("Нажмите любую кнопку для выхода!")


if __name__ == '__main__':
    main()
