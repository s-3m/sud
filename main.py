import asyncio
from bs4 import BeautifulSoup as bs
import aiohttp

mos_sud_url = "https://mos-sud.ru/search"
kazan_sud_url = "https://mirsud.tatarstan.ru/search"

cur_states = ["af3545b", "80c39ae"]
codex = ["12.27", "12.8", "12.26"]
year = "2024"

# params = {
#     'formType': 'fullForm',
#     'caseNumber': '',
#     'uid': '',
#     'participant': '',
#     'year': '2024',
#     'caseDateFrom': '',
#     'caseDateTo': '',
#     'codex': '',
#     'caseFinalDateFrom': '',
#     'caseFinalDateTo': '',
#     'caseLegalForceDateFrom': '',
#     'caseLegalForceDateTo': '',
#     'publishingState': '',
# }
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

async def get_gather_data():
    async with (aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session):
        for cur_state in cur_states:
            params = {'year': year, 'formType': 'on',}
            for item in codex:
                params["publishingState"] = cur_state
                params["codex"] = item
                async with session.get(mos_sud_url, params=params, headers=headers, cookies=cookies) as response:
                    await asyncio.sleep(2)
                    soup = bs(await response.text(), 'lxml')
                    paginator = soup.find("div", class_="pagenav").find('input').get('value')
                    for num_page in range(1, int(paginator) + 1):
                        print(f'---------{num_page}-------------')
                        params['page'] = str(num_page)
                        async with session.get(mos_sud_url, params=params, headers=headers) as page_response:
                            await asyncio.sleep(1)
                            soup = bs(await page_response.text(), 'lxml')
                            data_rows = soup.find("table", class_="custom_table").find_all('tr')[1:]


                            for row in data_rows:
                                for cell in row.find_all('td'):
                                    print(cell.text.strip())
                                print('------------------------------------------------')





def main():
    asyncio.run(get_gather_data())




if __name__ == '__main__':
    main()
