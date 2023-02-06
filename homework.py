from dotenv import load_dotenv
from http import HTTPStatus
import logging
import os
import requests
import sys
import time
import telegram

load_dotenv()
logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def send_message(bot, message):
    """Отправка сообщения ботом."""
    logger.debug(f'Бот отправил сообщение: {message}')
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except telegram.error.TelegramError as error:
        logger.error(f'Не удалось отправить сообщение "{message}"'
                     f'Причина {error}')


def get_api_answer(timestamp):
    """Проверка запроса к API."""
    logger.info('Отправляем запрос к API')
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        error = 'Проблемы подключения к серверу'
        raise ConnectionError(error)
    if response.status_code != HTTPStatus.OK:
        error = (
            f'Эндпоинт {ENDPOINT} недоступен.'
            f'Причина: {response.reason}, {response.text}'
            f'Код ответа: {response.status_code}'
        )
        raise Exception(error)
    return response.json()


def check_response(response):
    """Проверка ответа от API на соответствие документации."""
    logger.info('Начинаем проверку ответа API')
    if not isinstance(response, dict):
        error = 'Некорректный ответ от API - ожидался словарь'
        raise TypeError(error)
    if ('homeworks' not in response) or ('current_date' not in response):
        error = (
            'Неправильный ответ от API - отсутствует необходимый ключ'
        )
        raise KeyError(error)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        error = (
            'Неправильный ответ от API - ожидался тип list'
        )
        raise TypeError(error)
    return homeworks


def parse_status(homework):
    """Получаем статус последней домашней работы из ответа API."""
    if 'homework_name' not in homework:
        error = (
            'В словаре отсутствует ключ "homework_name"'
        )
        raise KeyError(error)
    homework_name = homework['homework_name']
    if 'status' not in homework:
        error = (
            'В словаре отсутствует ключ "status"'
        )
        raise KeyError(error)
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        error = (
            'Недокументированный статус домашней работы'
        )
        raise KeyError(error)
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    else:
        logger.critical('Отсутствует обязательная переменная окружения')
        raise SystemExit('Программа принудительно остановлена.')
    timestamp = int(time.time())
    prev_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != prev_message:
                    send_message(bot, message)
                    prev_message = message
            else:
                logger.info('В ответе нет нового статуса')
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой работы программы: {error}'
            logger.error(message)
            if message != prev_message:
                send_message(bot, message)
                prev_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)
    formatter = logging.Formatter(
        '%(asctime)s, %(lineno)d, %(name)s, %(lineno)d, %(message)s'
    )
    handler.setFormatter(formatter)
    main()
