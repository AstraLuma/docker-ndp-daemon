import logging

from .daemon import DockerNdpDaemon
from . import config


def init_app():
    logger = logging.getLogger(__name__)
    daemon = None

    logging.basicConfig(format=config.logger.format)
    logging.root.setLevel(config.logger.level)

    try:
        daemon = DockerNdpDaemon(
            config.docker.socket,
            config.host.gateway)
    except TimeoutError as ex:
        logger.debug(ex)
        logger.info("Docker connection read timed out. Reconnecting ...")
        if daemon:
            daemon.shutdown()
        init_app()
    except (KeyboardInterrupt, SystemExit):
        return

    # Just let other kinds of exceptions blow up the app with python's default handler
