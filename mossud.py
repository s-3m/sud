import asyncio
import pandas as pd
from alive_progress import alive_it
from bs4 import BeautifulSoup as bs
import aiohttp
import pandas.io.formats.excel

pandas.io.formats.excel.ExcelFormatter.header_style = None

mos_sud_url = "https://mos-sud.ru/search"

cur_states = [("af3545b", "Назначено судебное заседание"), ("80c39ae", "Отложено")]
codex = ["12.27", "12.8", "12.26"]
year = "2024"
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'ru,en;q=0.9',
    'Connection': 'keep-alive',
    # 'Cookie': 'currentCourt=; _ym_uid=1730271176292941916; _ym_d=1730271176; _ym_isad=2; c-dis=1',
    'Referer': 'https://mos-sud.ru/search',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 YaBrowser/24.7.0.0 Safari/537.36',
    'cache-control': 'no-cache',
    'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "YaBrowser";v="24.7", "Yowser";v="2.5"',
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
    df = pd.DataFrame(result)
    writer = pd.ExcelWriter('mos_sud_result.xlsx')
    df.to_excel(writer, sheet_name='result', index=False, na_rep='NaN')

    for column in df:
        col_idx = df.columns.get_loc(column)
        writer.sheets['result'].set_column(col_idx, col_idx, 20)
    writer.close()

async def get_gather_data():
    print("Анализирую данные...")
    tasks = []
    result = []
    async with (aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session):
        for cur_state in cur_states:
            params = {'year': year, 'formType': 'on',}
            for item in codex:
                params["publishingState"] = cur_state[0]
                params["codex"] = item
                async with session.get(mos_sud_url, params=params, headers=headers, cookies=cookies) as response:
                    await asyncio.sleep(2)
                    soup = bs(await response.text(), 'lxml')
                    paginator = soup.find("div", class_="pagenav").find('input').get('value')
                    for page_num in range(1, int(paginator) + 1):
                        params['page'] = str(page_num)
                        tasks.append(params.copy())
        print(f"Для обработки найдено {len(tasks)} страниц")
        await asyncio.sleep(2)
        print(f"Начинаю сбор данных")
        print(f"Состояние выполнения:")
        for param in alive_it(tasks):
            async with session.get(mos_sud_url, params=param, headers=headers) as page_response:
                await asyncio.sleep(1)
                try:
                    soup = bs(await page_response.text(), 'lxml')
                    data_rows = soup.find("table", class_="custom_table").find_all('tr')[1:]
                    state = True if param["publishingState"] == "80c39ae" else False
                    for row in data_rows:
                        row = row.find_all('td')
                        side = row[1].text.strip().split(": ")[-1]
                        if "Другие участники" in row[1].text.strip():
                            side = f"{row[1].find('br').previous.text},\n {row[1].find('br').next.next_sibling.text} "


                        row_result = {"СТ": param["codex"],
                                      "ДЕЛО": row[0].text.strip(),
                                      "УЧ": row[3].text.strip().split("№ ")[-1],
                                      "ТС": "O" if state else "Н",
                                      "СОСТОЯНИЕ": row[2].text.strip().split(" до ")[-1] if state else row[2].text.strip().split(" на ")[-1],
                                      "СТОРОНЫ": side
                                      }

                        result.append(row_result)
                except Exception as e:
                    with open("error.txt", "a+") as f:
                        f.write(f'{param["page"]} - {param["codex"]} - {param["publishingState"]} ------> {e}\n')
                    continue



    wright_to_file(result)
    print("Сбор данных завершён успешно. Вы можете закрыть окно.")

def main():
    try:
        asyncio.run(get_gather_data())
    except:
         print("---------------!!!!!!!---------------\nПроизошла ошибка.\nВозможно проблемы с сайтом или вашим интернетом.\nПопробуйте перезапустить программу!\n---------------!!!!!!!---------------")
    print()
    input("Нажмите любую кнопку для выхода!")




if __name__ == '__main__':
    main()
