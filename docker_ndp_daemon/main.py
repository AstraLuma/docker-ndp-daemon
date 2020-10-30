import logging
import sys

from .daemon import DockerNdpDaemon
from . import config


def init_app():
    try:
        logger = logging.getLogger(__name__)
        daemon = None

        logging.basicConfig(format=config.logger.format)
        logging.root.setLevel(config.logger.level)

        while True:
            try:
                daemon = DockerNdpDaemon(ethernet_interface=config.host.gateway)
                daemon.listen_network_connect_events()
            except TimeoutError as ex:
                logger.debug(ex)
                logger.info("Docker connection read timed out. Reconnecting ...")
                if daemon:
                    daemon.shutdown()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)

    # Just let other kinds of exceptions blow up the app with python's default handler
