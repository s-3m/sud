import requests
import pandas as pd
import pandas.io.formats.excel

pandas.io.formats.excel.ExcelFormatter.header_style = None

headers = {
    'accept': '*/*',
    'accept-language': 'ru,en;q=0.9',
    'origin': 'https://matveevv.ru',
    'priority': 'u=1, i',
    'referer': 'https://matveevv.ru/',
    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "YaBrowser";v="25.4", "Yowser";v="2.5"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 YaBrowser/25.4.0.0 Safari/537.36',
}

def get_main_data():
    result = []
    for brand in ("SKIMS", "KHY"):
        params = {
            'storepartuid': '795517775491',
            'recid': '998242731',
            'c': '1748790254952',
            'getparts': 'true',
            'getoptions': 'true',
            'slice': '1',
            'filters[brand][0]': brand,
            'size': '300',
        }
        response = requests.get('https://store.tildaapi.com/api/getproductslist/', params=params, headers=headers)
        json_response = response.json()
        if json_response:
            items_list = json_response["products"]
            for item in items_list:
                size = ""
                title = item["title"]
                options = item["editions"]
                if options:
                    for option in options:
                        quantity = option["quantity"]
                        try:
                            size = option["Размер"]
                            new_title = f"{title} - {size}"
                            item_dict = {"Title": new_title,
                                         "Quantity": quantity,
                                         "Editions": f"Размер:{size}"}
                        except KeyError as e:
                            new_title = title
                            item_dict = {"Title": new_title,
                                         "Quantity": quantity,
                                         }

                        result.append(item_dict)
    return result

def main():
    print("Начался сбор информации")
    result = get_main_data()
    df = pd.DataFrame(result)
    df.to_csv("fashion_result.csv", sep=";", index=False, encoding="Windows-1251")
    input("Сбор данных завершен. Нажмите любую кнопку для выхода...")


if __name__ == '__main__':
    main()