import asyncio
import time
from urllib.parse import urljoin

import pandas as pd
import requests
import urllib3
from alive_progress import alive_it
from bs4 import BeautifulSoup as bs
from loguru import logger
from playwright.async_api import async_playwright
from requests.exceptions import RequestException


# -------------------- НАСТРОЙКИ --------------------

mos_sud_url = "https://mos-sud.ru/search"
BASE_URL = "https://mos-sud.ru"

cur_states = [
    ("af3545b", "Назначено судебное заседание"),
    ("80c39ae", "Отложено"),
]

codex = ["12.27", "12.8", "12.26"]

OUTPUT_FILE = "mos_sud_result.xlsx"
FAILED_CASES_FILE = "mos_sud_failed.xlsx"
FAILED_SEARCH_FILE = "mos_sud_failed_search.xlsx"

REQUEST_RETRIES = 5
REQUEST_TIMEOUT = (20, 90)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# -------------------- БРАУЗЕРНАЯ СЕССИЯ --------------------

async def get_browser_data():
    """Открывает сайт в Chromium и получает актуальные cookies и базовые headers."""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
        )

        page = await context.new_page()

        try:
            response = await page.goto(
                mos_sud_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            await page.wait_for_timeout(3000)

            if response is not None and response.status >= 400:
                logger.warning(
                    f"Браузер получил HTTP {response.status} при открытии сайта"
                )

            cookies_list = await context.cookies()

            headers = {
                "User-Agent": await page.evaluate("navigator.userAgent"),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Referer": mos_sud_url,
            }

            cookies = {
                cookie["name"]: cookie["value"]
                for cookie in cookies_list
            }

            return headers, cookies

        finally:
            await browser.close()


# -------------------- HTTP С ПОВТОРНЫМИ ПОПЫТКАМИ --------------------

def request_with_retry(session, url, params=None, max_retries=REQUEST_RETRIES):
    """GET-запрос с повторами при сетевых и временных серверных ошибках."""

    retry_statuses = {408, 425, 429, 500, 502, 503, 504}
    error_markers = (
        "504 Gateway Time-out",
        "502 Bad Gateway",
        "503 Service Unavailable",
        "500 Internal Server Error",
        "The server encountered an internal error",
    )

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                verify=False,
            )

            if response.status_code in retry_statuses:
                raise RequestException(f"HTTP {response.status_code}")

            response.raise_for_status()

            if any(marker in response.text for marker in error_markers):
                raise RequestException("Сервер вернул HTML-страницу ошибки")

            return response

        except RequestException as exc:
            if attempt == max_retries:
                logger.error(
                    f"Запрос не выполнен после {max_retries} попыток. "
                    f"URL: {response.url if 'response' in locals() else url}. "
                    f"Параметры: {params}. Ошибка: {exc}"
                )
                return None

            delay = min(2 ** attempt, 30)
            logger.warning(
                f"Ошибка запроса ({attempt}/{max_retries}): {exc}. "
                f"Повтор через {delay} сек. URL: {url}"
            )
            time.sleep(delay)

    return None


# -------------------- ПАРСИНГ КАРТОЧКИ ДЕЛА --------------------

def get_case_data(case_link: str, session, max_retries=REQUEST_RETRIES):
    """Загружает и разбирает карточку одного дела."""

    url = urljoin(BASE_URL, case_link)

    for attempt in range(1, max_retries + 1):
        try:
            response = request_with_retry(
                session,
                url,
                max_retries=1,
            )

            if response is None:
                raise RequestException("Не удалось получить ответ от сервера")

            soup = bs(response.text, "lxml")
            all_rows = soup.find_all("div", class_="row_card")

            if not all_rows:
                raise ValueError("В ответе не найдены данные карточки дела")

            case_result = {}

            for row in all_rows:
                title_element = row.find("div", class_="left")
                value_element = row.find("div", class_="right")

                if title_element and value_element:
                    title = title_element.get_text(" ", strip=True)
                    value = value_element.get_text(" ", strip=True)
                    case_result[title] = value

            # Отсутствие блока заседаний не означает ошибку карточки.
            case_result["Дата"] = ""
            case_result["Зал"] = ""
            case_result["Стадия"] = ""

            sessions = soup.find("div", id="sessions")
            if sessions:
                tbody = sessions.find("tbody")
                if tbody:
                    cells = tbody.find_all("td")
                    if len(cells) > 0:
                        case_result["Дата"] = cells[0].get_text(" ", strip=True)
                    if len(cells) > 1:
                        case_result["Зал"] = cells[1].get_text(" ", strip=True)
                    if len(cells) > 2:
                        case_result["Стадия"] = cells[2].get_text(" ", strip=True)

            return case_result

        except (RequestException, ValueError) as exc:
            if attempt == max_retries:
                logger.error(
                    f"Не удалось обработать дело {case_link} "
                    f"после {max_retries} попыток: {exc}"
                )
                return None

            delay = min(2 ** attempt, 30)
            logger.warning(
                f"Ошибка карточки {case_link} ({attempt}/{max_retries}): "
                f"{exc}. Повтор через {delay} сек."
            )
            time.sleep(delay)

        except Exception:
            logger.exception(f"Непредвиденная ошибка при обработке {case_link}")
            return None

    return None


# -------------------- ОСНОВНОЙ СБОР --------------------

async def get_gather_data():
    print("Анализирую данные...")

    headers, cookies = await get_browser_data()

    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)

    result = []
    search_tasks = []
    failed_search_tasks = []
    failed_count_queries = []
    failed_cases = []
    seen_case_links = set()

    try:
        # ЭТАП 1. Определяем количество страниц для каждого фильтра.
        for cur_state in cur_states:
            for item in codex:
                params = {
                    "year": "2026",
                    "formType": "fullForm",
                    "processType": "3",
                    "publishingState": cur_state[0],
                    "codex": item,
                }

                response = request_with_retry(
                    session,
                    mos_sud_url,
                    params=params,
                )

                if response is None:
                    failed_count_queries.append(params.copy())
                    continue

                soup = bs(response.text, "lxml")
                check_element = soup.find("div", class_="resultsearch_text")

                if check_element is None:
                    logger.warning(
                        f"Не найден блок результата поиска. Параметры: {params}"
                    )
                    failed_count_queries.append(params.copy())
                    continue

                check = check_element.get_text(strip=True)
                if check == "По вашему запросу ничего не найдено":
                    time.sleep(2)
                    continue

                paginator = 1
                paginator_input = soup.select_one("div.pagenav input")
                if paginator_input:
                    try:
                        paginator = max(1, int(paginator_input.get("value", "1")))
                    except (TypeError, ValueError):
                        logger.warning(
                            f"Не удалось определить число страниц. Параметры: {params}"
                        )
                        failed_count_queries.append(params.copy())
                        time.sleep(2)
                        continue

                for page_num in range(1, paginator + 1):
                    page_params = params.copy()
                    page_params["page"] = str(page_num)
                    search_tasks.append(page_params)

                time.sleep(2)

        # Повторяем запросы, для которых не удалось определить число страниц.
        if failed_count_queries:
            print(
                f"Повторно определяю количество страниц для запросов: "
                f"{len(failed_count_queries)}"
            )
            queries_to_retry = failed_count_queries
            failed_count_queries = []

            for params in alive_it(queries_to_retry):
                response = request_with_retry(session, mos_sud_url, params=params)
                if response is None:
                    failed_count_queries.append(params.copy())
                    continue

                soup = bs(response.text, "lxml")
                check_element = soup.find("div", class_="resultsearch_text")
                if check_element is None:
                    failed_count_queries.append(params.copy())
                    continue

                if check_element.get_text(strip=True) == "По вашему запросу ничего не найдено":
                    continue

                paginator = 1
                paginator_input = soup.select_one("div.pagenav input")
                if paginator_input:
                    try:
                        paginator = max(1, int(paginator_input.get("value", "1")))
                    except (TypeError, ValueError):
                        failed_count_queries.append(params.copy())
                        continue

                for page_num in range(1, paginator + 1):
                    page_params = params.copy()
                    page_params["page"] = str(page_num)
                    if page_params not in search_tasks:
                        search_tasks.append(page_params)
                time.sleep(2)

        print(f"Для обработки найдено {len(search_tasks)} страниц")
        print("Начинаю сбор ссылок на дела")

        # ЭТАП 2. Получаем ссылки на карточки дел.
        # Неудачные страницы складываем отдельно и повторяем один раз в конце.
        case_links = []
        seen_case_links = set()

        def collect_case_links(page_params):
            page_response = request_with_retry(
                session,
                mos_sud_url,
                params=page_params,
            )

            if page_response is None:
                return False

            soup = bs(page_response.text, "lxml")
            table = soup.find("table", class_="custom_table")

            if table is None:
                logger.warning(f"Таблица не найдена. Страница: {page_params}")
                return False

            for item in table.find_all("nobr")[1:]:
                link_tag = item.find("a")
                if not link_tag:
                    continue

                case_link = link_tag.get("href")
                if case_link and case_link not in seen_case_links:
                    seen_case_links.add(case_link)
                    case_links.append(case_link)

            return True

        for page_params in alive_it(search_tasks):
            if not collect_case_links(page_params):
                failed_search_tasks.append(page_params.copy())
            time.sleep(1)

        # Повторяем только страницы поиска, которые не удалось прочитать.
        if failed_search_tasks:
            print(f"Повторно загружаю проблемные страницы: {len(failed_search_tasks)}")
            pages_to_retry = failed_search_tasks
            failed_search_tasks = []

            for page_params in alive_it(pages_to_retry):
                if not collect_case_links(page_params):
                    failed_search_tasks.append(page_params.copy())
                time.sleep(2)

        print(f"Уникальных карточек для обработки: {len(case_links)}")

        # ЭТАП 3. Обрабатываем карточки. Один поток оставлен намеренно,
        # чтобы не создавать дополнительную нагрузку на сайт.
        for case_link in alive_it(case_links):
            case_result = get_case_data(case_link, session)
            if case_result is not None:
                result.append(case_result)
            else:
                failed_cases.append(case_link)
            time.sleep(1)

        # ЭТАП 4. Дополнительный проход по карточкам, которые не удалось получить.
        if failed_cases:
            print(f"Повторно обрабатываю неудачные карточки: {len(failed_cases)}")

            remaining_failed_cases = []
            for case_link in alive_it(failed_cases):
                case_result = get_case_data(
                    case_link,
                    session,
                    max_retries=REQUEST_RETRIES,
                )
                if case_result is not None:
                    result.append(case_result)
                else:
                    remaining_failed_cases.append(case_link)
                time.sleep(2)
            failed_cases = remaining_failed_cases

        # ЭТАП 5. Сохраняем результаты и списки проблем.
        pd.DataFrame(result).to_excel(OUTPUT_FILE, index=False)

        if failed_cases:
            pd.DataFrame({"Необработанные ссылки": failed_cases}).to_excel(
                FAILED_CASES_FILE,
                index=False,
            )
        else:
            logger.info("Все карточки дел обработаны успешно.")

        if failed_search_tasks:
            pd.DataFrame(failed_search_tasks).to_excel(
                FAILED_SEARCH_FILE,
                index=False,
            )

        print("Сбор данных завершён.")
        print(f"Успешно собрано дел: {len(result)}")
        print(f"Необработанных карточек: {len(failed_cases)}")
        print(f"Необработанных страниц поиска: {len(failed_search_tasks)}")
        print(f"Не удалось определить число страниц для запросов: {len(failed_count_queries)}")
        if failed_count_queries:
            pd.DataFrame(failed_count_queries).to_excel(
                "mos_sud_failed_count_queries.xlsx",
                index=False,
            )
        print(f"Результат сохранён в {OUTPUT_FILE}")

    finally:
        session.close()


def main():
    try:
        asyncio.run(get_gather_data())
    except KeyboardInterrupt:
        print("\nСбор остановлен пользователем.")
    except Exception:
        logger.exception("Критическая ошибка выполнения")
        print(
            "Произошла ошибка. Подробности записаны в журнал. "
            "Проверьте доступность сайта и интернет-соединение."
        )

    input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    main()
