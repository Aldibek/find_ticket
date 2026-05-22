
 
from langchain_core.tools import tool
import agentql
import json
import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from dotenv import load_dotenv
from time import sleep
from dict_city_date import CITY,MONTH_NUM,MONTHS_RU
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()

From = ""
To = ""
openai_api_key = os.getenv("OPENAI_API_KEY")
agenql_api_key = os.getenv("AGENTQL_API_KEY")


while True:
    try:
        From = CITY[input('Откуда: ')]
        To = CITY[input('Куда: ')]
        break
    except KeyError:
        print("Город не найден. Пожалуйста, проверьте правильность ввода.")
        
print("Введите интервал времени где вы хотите поехать:(Например 23.02) ")
date_from = input('От: ')
date_to = input('До: ')
url = f'https://freedom-travel.kz/railways/direction/{From}_{To}/'




from datetime import datetime, timedelta


def parse_input_date(text, year=2026):
    return datetime.strptime(f"{text}.{year}", "%d.%m.%Y").date()


def generate_dates(date_from, date_to, year=2026):
    start = parse_input_date(date_from, year)
    end = parse_input_date(date_to, year)

    if end < start:
        end = parse_input_date(date_to, year + 1)

    current = start

    while current <= end:
        yield current
        current += timedelta(days=1)


def build_date_url(start_url, current_date):
    date_for_url = current_date.strftime("%d.%m.%Y")
    return start_url + date_for_url
def get_ticket_links(date_from: str, date_to: str) -> list[str]:
    """
    Возвращает ссылки на страницы билетов за период дат.
    """
    return get_links(url, date_from, date_to)

def get_links(url, date_from, date_to):
    """
    Получает ссылки на страницы с билетами для каждой даты в указанном диапазоне.
    Использует Playwright для взаимодействия с сайтом и получения динамически загружаемых данных.
    и возвращает список ссылок на страницы с билетами для каждой даты.Чтобы потом с ними работать и парсить информацию о билетах.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url)
        timesleep = 5
        page.wait_for_timeout(timesleep)
        page.get_by_text("Найти билеты").click()
        page.wait_for_timeout(5000)
        new_url = page.url
        #print("OLD URL:", old_url)

    
        new_url = page.url
        print(new_url)
        start_url = new_url[:-10]
        link = []
        for current_date in generate_dates(date_from, date_to):
            url = build_date_url(start_url, current_date)
            link.append(url)
            #print(f"Проверяю дату {current_date.strftime('%d.%m.%Y')}")
            #print(url)
        browser.close()
    return link
    #page.goto(url, wait_until="domcontentloaded")
    #page.wait_for_timeout(1000)


def parse_ticket_info(url):
    """Парсит информацию о билетах с указанного     URL и возвращает данные в виде словаря.
    """

    TICKETS_QUERY = """
    {
    train_trips[] {
        train_name(The name or number of the train)

        departure_date(The departure date, for example 7 September or 07.09)
        departure_time(The time of departure)

        arrival_date(The arrival date, for example 8 September or 08.09)
        arrival_time(The time of arrival)

        travel_duration(The total time the trip takes)

        ticket_categories[] {
        ticket_type(The class or type of ticket, for example platzkart, coupe, lux)
        available_seats(The number of free places)
        price(The cost of the ticket)
        }
    }
    }
    """
    answer = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = agentql.wrap(browser.new_page())

        for current_link in url:
            page.goto(current_link)
            page.wait_for_timeout(5000)
            try:
                result = page.query_data(TICKETS_QUERY)
                print(json.dumps(result, ensure_ascii=False, indent=4))
                answer.append([result,current_link]) 
            except PlaywrightTimeoutError:
                print(f"Не удалось получить данные для {current_link}. Пропускаю эту ссылку.")
                continue
        browser.close()       
    
    return answer

llm = ChatOpenAI(model="gpt-4o-mini",temperature=0.5,api_key=openai_api_key)  # type: ignore
system_prompt = """
Ты помощник для поиска билетов.
Твоя задача:
- анализировать найденные билеты
- выбирать самый дешевый вариант по каждому классу (платцкарт, купе, люкс) и рядом вывести ссылку на страницу с этим билетом
- выбирать самый оптимальный вариант по цене и времени
- отвечать кратко на русском
"""


links = get_links(url, date_from, date_to)
tickets = parse_ticket_info(links)

response = llm.invoke([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"""
    Вот найденные билеты:

    {tickets}

    Выбери:
    1. Самый дешевый билет по каждому классу
    2. Самый оптимальный вариант по цене и времени
    3. Дай ссылку рядом с вариантом
    """}
])



print(response.content)
