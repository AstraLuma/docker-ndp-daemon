import logging
import configparser
from pathlib import Path

log = logging.getLogger(__name__)


class Config(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


loglevel_map = {'critical': logging.CRITICAL,
                'fatal': logging.FATAL,
                'error': logging.ERROR,
                'warning': logging.WARNING,
                'warn': logging.WARNING,
                'info': logging.INFO,
                'debug': logging.DEBUG
                }

conf = configparser.ConfigParser()
conf.read([
    Path(__file__).resolve().parent.parent / "dnd.ini",
    '/etc/docker-ndp-daemon.ini',
])

try:
    # Create sections with attributes
    host = Config(conf['host'])
    logger = Config(conf['logger'])
except Exception as ex:
    raise ImportError(
        "Missing config sections"
    ) from ex

logger.level = loglevel_map[logger.level.lower()]
