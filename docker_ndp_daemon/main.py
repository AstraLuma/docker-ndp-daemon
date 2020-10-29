import sys
import logging

from .daemon import DockerNdpDaemon
from .daemon import DaemonException
from .daemon import DaemonTimeoutException
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
    except DaemonTimeoutException as ex:
        logger.debug(ex)
        logger.info("Docker connection read timed out. Reconnecting ...")
        if daemon:
            daemon.shutdown()
        init_app()
        return()

    except DaemonException as ex:
        logger.critical("CRITICAL: {}".format(ex))
        sys.exit(1)

    except Exception as ex:
        logger.critical("CRITICAL: Unexpected exception '{}' catched - possible bug: {}".format(ex.__class__, ex))
        sys.exit(2)