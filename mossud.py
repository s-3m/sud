import asyncio
import pandas as pd
from alive_progress import alive_it
from bs4 import BeautifulSoup as bs
import aiohttp
import pandas.io.formats.excel
from loguru import logger

pandas.io.formats.excel.ExcelFormatter.header_style = None

mos_sud_url = "https://mos-sud.ru/search"

cur_states = [("af3545b", "Назначено судебное заседание"), ("80c39ae", "Отложено")]
codex = ["12.27", "12.8", "12.26"]
years = ["2024", "2025"]
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'ru,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    # 'Cookie': '_ym_uid=1730271176292941916; _ym_d=1730271176; _ym_isad=2; maintenance_closed=true',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 YaBrowser/24.10.0.0 Safari/537.36',
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


def wright_to_file(result):
    df = pd.DataFrame(result).to_excel('mos_sud_result.xlsx', index=False)
    # writer = pd.ExcelWriter('mos_sud_result.xlsx')
    # df.to_excel(writer, sheet_name='result', index=False, na_rep='NaN')
    #
    # for column in df:
    #     col_idx = df.columns.get_loc(column)
    #     writer.sheets['result'].set_column(col_idx, col_idx, 20)
    # writer.close()


async def get_case_data(session: aiohttp.ClientSession, case_link: str):
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        # 'Cookie': '_ym_uid=1730396567762587290; _ym_d=1736012922; _ym_isad=2; c-dis=1',
        'Referer': 'https://mos-sud.ru/search?formType=fullForm&uid=&caseNumber=&participant=&processType=3&codex=12.27&judge=&publishingState=af3545b&documentType=&year=2025&caseDateFrom=&caseDateTo=&caseFinalDateFrom=&caseFinalDateTo=&caseLegalForceDateFrom=&caseLegalForceDateTo=&documentStatus=&documentText=',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 YaBrowser/25.2.0.0 Safari/537.36',
        'sec-ch-ua': '"Not A(Brand";v="8", "Chromium";v="132", "YaBrowser";v="25.2", "Yowser";v="2.5"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }

    params = {
        'documentMainArticle': '12.27',
        'publishingState': 'af3545b',
        'year': '2025',
        'formType': 'fullForm',
    }
    async with session.get(f"https://mos-sud.ru{case_link}", headers=headers) as response:
        soup = bs(await response.text(), "lxml")
        all_rows = soup.find_all("div", class_="row_card")
        mini_tabs = soup.find("div", id="sessions").find("tbody").find_all("td")
        print('asass')







async def get_gather_data():
    print("Анализирую данные...")
    tasks = []
    result = []
    async with (aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session):
        # for year in years:
        for cur_state in cur_states[:1]:
            params = {'year': "2025", 'formType': 'on', }
            for item in codex[:1]:
                params["publishingState"] = cur_state[0]
                params["codex"] = item
                async with session.get(mos_sud_url, params=params, headers=headers, cookies=cookies) as response:
                    await asyncio.sleep(2)
                    soup = bs(await response.text(), 'lxml')
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

        print(f"Для обработки найдено {len(tasks)} страниц")
        await asyncio.sleep(2)
        print(f"Начинаю сбор данных")
        print(f"Состояние выполнения:")
        for param in alive_it(tasks):
            async with session.get(mos_sud_url, params=param, headers=headers) as page_response:
                await asyncio.sleep(1)
                # try:
                soup = bs(await page_response.text(), 'lxml')
                data_cases = soup.find("table", class_="custom_table").find_all('nobr')[1:]
                cases_links = [i.find('a').get('href') for i in data_cases]
                state = True if param["publishingState"] == "80c39ae" else False
            for case_link in cases_links:
                case_result = await get_case_data(session, case_link)
                result.append(case_result)



                        # row = row.find_all('td')
                        # side = row[1].text.strip().split(": ")[-1]
                        # if "Другие участники" in row[1].text.strip():
                        #     side = f"{row[1].find('br').previous.text},\n {row[1].find('br').next.next_sibling.text} "
                        #
                        # row_result = {"СТ": param["codex"],
                        #               "ДЕЛО": row[0].text.strip(),
                        #               "УЧ": row[3].text.strip().split("№ ")[-1],
                        #               "ТС": "O" if state else "Н",
                        #               "СОСТОЯНИЕ": row[2].text.strip().split(" до ")[-1] if state else
                        #               row[2].text.strip().split(" на ")[-1],
                        #               "СТОРОНЫ": side
                        #               }
                        #
                        # result.append(row_result)
                # except Exception as e:
                #     with open("error.txt", "a+") as f:
                #         f.write(f'{param["page"]} - {param["codex"]} - {param["publishingState"]} ------> {e}\n')
                #     continue

    wright_to_file(result)
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
