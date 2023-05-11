import logging
from zoneinfo import ZoneInfo


DEFAULT_TZ = ZoneInfo("Europe/Moscow")

def get_logger():
    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    log.addHandler(stdout_handler)
    return log