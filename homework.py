import logging
import os
import sys
import time
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO)

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
    try:
        response = response.json()
    except JSONDecodeError:
        logging.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT} не '
                      f'выдает JSON. Код ответа API: {response.status_code}.')
        raise ValueError(f'Эндпоинт {ENDPOINT} не выдает JSON.'
                         f'Код ответа API: {response.status_code}.')
    else:
        return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        homework_list = response['homeworks']
    except Exception:
        logging.error('В полученных с сервера данных '
                      'отсутствует ключ homeworks.')
        raise KeyError('В полученных с сервера данных '
                       'отсутствует ключ homeworks.')
    return homework_list


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе
       статус этой работы.
    """
    try:
        homework_status = homework['status']
    except Exception:
        logging.error('В полученных с сервера данных '
                      'отсутствует ключ status.')
        raise KeyError('В полученных с сервера данных '
                       'отсутствует ключ status.')
    try:
        homework_name = homework['lesson_name']
    except Exception:
        logging.error('В полученных с сервера данных '
                      'отсутствует ключ lesson_name.')
        raise KeyError('В полученных с сервера данных '
                       'отсутствует ключ lesson_name.')

    if homework_status not in HOMEWORK_STATUSES.keys():
        logging.error(f'Статус {homework_status} отсутствует '
                      'в словаре HOMEWORK_STATUSES.')
        raise KeyError(f'Статус {homework_status} отсутствует '
                       'в словаре HOMEWORK_STATUSES.')
    verdict = HOMEWORK_STATUSES[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    venv = {'PRACTICUM_TOKEN': bool(PRACTICUM_TOKEN),
            'TELEGRAM_TOKEN': bool(TELEGRAM_TOKEN),
            'TELEGRAM_CHAT_ID': bool(TELEGRAM_CHAT_ID)}
    for key, value in venv.items():
        if not value:
            logging.critical("Отсутствует обязательная переменная окружения: "
                             f"'{key}'. Программа принудительно остановлена.")
            raise Exception("Отсутствует обязательная переменная окружения: "
                            f"'{key}'. Программа принудительно остановлена.")
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    error_message = ''

    check_tokens()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                logging.debug('В ответе отсутствуют новые статусы.')
            else:
                for homework in homeworks:
                    msg = parse_status(homework)
                    bot.send_message(TELEGRAM_CHAT_ID, msg)
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
