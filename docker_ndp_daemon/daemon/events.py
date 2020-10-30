import logging
from docker import DockerClient, from_env
from urllib3.exceptions import ReadTimeoutError

logger = logging.getLogger(__name__)


class DockerEventDaemon:
    """High level docker client for listening to dockerndp client.

    The class is a wrapper around the :class:`docker.client.DockerClient`
    for use as a daemon.

    It provides:
        * Listeing to dockerndp Events
        * Listening to SIGNALS for safe termination.
    """

    # Properties
    socket_url = None
    _client = None

    def __init__(self, *, socket_url=None):
        """Creates a new DockerClient.

        :param socket_url: URL to the Docker server.

        Example:
            >>> DockerEventDaemon(socket_url="unix://var/run/dockerndp.sock")
            >>> DockerEventDaemon(socket_url="tcp://127.0.0.1:1234")
        """
        self.socket_url = socket_url

        logger.info("Connecting ...")

    def __enter__(self):
        self._client = self.init_docker_client()
        assert self._client
        return self

    def __exit__(self, *exc):
        self._client.close()

    def init_docker_client(self):
        """
        :return: the docker client object
        """
        if self.socket_url is None:
            return from_env()
        else:
            return DockerClient(base_url=self.socket_url)

    def listen_network_connect_events(self):
        logger.info("Listening for Events ...")

        try:
            for event in self._client.events(decode=True):
                method = f"handle_{event['Type']}_{event['Action']}_event"
                if hasattr(self, method):
                    getattr(self, method)(event)
        except ReadTimeoutError as ex:
            raise TimeoutError from ex
