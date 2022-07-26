import logging
import os
import sys
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

from settings import ENDPOINT, HEADERS, HOMEWORK_STATUSES, RETRY_TIME

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    filename='main.log',
    filemode='w'
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Бот отправил сообщение: {message}.')
    except Exception:
        logging.error(f'Сбой при отправке сообщения: {message}.')
        raise Exception(f'Сбой при отправке сообщения: {message}.')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        logging.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT}'
                      f'недоступен. Код ответа API: {response.status_code}.')
        raise Exception(f'Эндпоинт {ENDPOINT} недоступен.'
                        f'Код ответа API: {response.status_code}.')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT}'
                      f'недоступен. Код ответа API: {response.status_code}.')
        raise Exception(f'Эндпоинт {ENDPOINT} недоступен.'
                        f'Код ответа API: {response.status_code}.')
    try:
        response = response.json()
    except JSONDecodeError:
        logging.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT} не '
                      f'выдает JSON. Код ответа API: {response.status_code}.')
        raise ValueError(f'Эндпоинт {ENDPOINT} не выдает JSON.'
                         f'Код ответа API: {response.status_code}.')
    return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) is dict:
        homework_list = response['homeworks']
        if type(homework_list) != list:
            logging.error('homeworks не содержит список')
            raise KeyError('homeworks не содержит список')
    else:
        logging.error('JSON пришел без словаря.')
        raise TypeError('JSON пришел без словаря.')
    return homework_list


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе."""
    status = homework['status']
    homework_name = homework['homework_name']
    if not status:
        logging.error('В полученных с сервера данных '
                      'отсутствует ключ status.')
        raise KeyError('В полученных с сервера данных '
                       'отсутствует ключ status.')
    elif not homework_name:
        logging.error('В полученных с сервера данных '
                      'отсутствует ключ homework_name.')
        raise KeyError('В полученных с сервера данных '
                       'отсутствует ключ homework_name.')
    if status not in HOMEWORK_STATUSES.keys():
        logging.error(f'Статус {status} отсутствует '
                      'в словаре HOMEWORK_STATUSES.')
        raise KeyError(f'Статус {status} отсутствует '
                       'в словаре HOMEWORK_STATUSES.')
    verdict = HOMEWORK_STATUSES[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует обязательная переменная окружения. '
                         'Программа принудительно остановлена.')
        raise Exception('Отсутствует обязательная переменная окружения. '
                        'Программа принудительно остановлена.')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    error_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logging.debug('В ответе отсутствуют новые статусы.')
            else:
                for homework in homeworks:
                    send_message(bot, parse_status(homework))
            current_timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if error_message != message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
