import logging
from docker import DockerClient, from_env
import json
import signal
from subprocess import run, PIPE, DEVNULL
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
    _terminate = False

    def __init__(self, socket_url=None):
        """Creates a new DockerClient.

        :param socket_url: URL to the Docker server.

        Example:
            >>> DockerEventDaemon("unix://var/run/dockerndp.sock")
            >>> DockerEventDaemon("tcp://127.0.0.1:1234")
        """
        signal.signal(signal.SIGINT, self._handle_termination)
        signal.signal(signal.SIGTERM, self._handle_termination)
        self.socket_url = socket_url

        logger.info("Connecting ...")
        self._client = self.init_docker_client()
        assert self._client

    def init_docker_client(self):
        """
        :return: the docker client object
        """
        if self.socket_url is None:
            return from_env()
        else:
            return DockerClient(base_url=self.socket_url)

    # Listens for network connect client and calls handle_network_connect_event
    def listen_network_connect_events(self):
        logger.info("Listening for Events ...")

        try:
            for jsonEvent in self._client.events():
                event = json.loads(jsonEvent)
                if event['Type'] == 'network' and event['Action'] == 'connect':
                    self._handle_network_connect_event(event)
        except ReadTimeoutError:
            raise
        except Exception:
            if self._terminate:
                logger.warning("Error during termination", exc_info=True)
            else:
                raise

    def shutdown(self):
        """shuts down the daemon."""
        logger.info("Shutting down ...")
        self._terminate = True
        self._client.close()

    # Handler for all net work connection client
    def _handle_network_connect_event(self, event: dict):
        pass

    # Shutdown app (Param _ (frame) is not needed.
    def _handle_termination(self, signum, _):
        logger.info("Signal %r received.", signum)
        self.shutdown()

    # Fetches IPv6 address
    @staticmethod
    def fetch_ipv6_address(container) -> str:
        """Extracts the ipv6 address of a container.

        Since :class:`docker.DockerClient` does not have the ability to read the IPv6 address
        of a container this method retrieves it with calling the *docker* binary as a sub process.

        :param container: The container from which the
        :return: Tuple (Returncode, IPv6 address, STDERR if Returncode is not 0)
        """
        process = run([
            "docker",
            "container",
            "inspect",
            "--format={{range .NetworkSettings.Networks}}{{.GlobalIPv6Address}}{{end}}",
            container.id],
            stdin=DEVNULL, stdout=PIPE, stderr=PIPE, encoding='utf-8', check=True,
        )
        return process.stdout.strip() or None
