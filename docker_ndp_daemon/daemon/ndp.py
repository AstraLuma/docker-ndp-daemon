import logging
from .events import DockerEventDaemon
from subprocess import run, PIPE, DEVNULL

logger = logging.getLogger(__name__)


class DockerNdpDaemon(DockerEventDaemon):
    """A special :class:`DockerEventDaemon` that adds IPv6 addresses of
    recently started docker containers to the NDP proxy for
    getting IPv6 internet connectivity.
    """
    _ethernet_interface = None

    def __init__(self, *, socket_url=None, ethernet_interface):
        """ Creates a new instance.

        :param (str) socket_url: Path of the dockerndp socket file.
        :param (str) ethernet_interface: Name of the ethernet interface that is
           an internet gateway.
        """
        super().__init__(socket_url=socket_url)
        self._ethernet_interface = ethernet_interface

    def __enter__(self):
        rv = super().__enter__()
        self._activate_ndp_proxy()
        self._add_all_existing_containers_to_neigh_proxy()
        return rv

    def _handle_network_connect_event(self, event):
        # Fetches Container from id in event
        container_id = event['Actor']['Attributes']['container']
        container = self._client.containers.get(container_id)
        logger.debug("Event: Container '{}' connected to dockerndp network."
                     .format(container.name))
        self._add_container_to_ipv6_ndp_proxy(container)

    def _add_container_to_ipv6_ndp_proxy(self, container):
        ipv6_address = self._try_fetch_ipv6_address(container)
        if not ipv6_address:
            logger.info("Ignoring container %r. It has no IPv6 address.", container.name)
            return

        self._add_ipv6_neigh_proxy(ipv6_address)

        logger.info("Set IPv6 ndp proxy for container %r: %r", container.name, ipv6_address)

    @staticmethod
    def _try_fetch_ipv6_address(container):
        # Adds the passed container to the ipv6 neighbour discovery proxy
        ipv6_address = DockerNdpDaemon.fetch_ipv6_address(container)

        if not ipv6_address:
            return None

        logger.debug("Event: Container  %r connected to dockerndp network has IPv6 address %r",
                     container.name, ipv6_address)
        return ipv6_address

    def _add_ipv6_neigh_proxy(self, ipv6_address) -> (int, str, str):
        # Sets IPv6 neighbour discovery to ethernet interface.
        run(
            ['ip', '-6', 'neigh', 'add', 'proxy', ipv6_address, 'dev', self._ethernet_interface],
            stdin=DEVNULL, stdout=PIPE, stderr=PIPE, encoding='utf-8', check=True,
        )

    def _activate_ndp_proxy(self):
        # Activates the ndp proxy
        logger.info("Activating IPv6 ndp proxy on '{}' ...".format(self._ethernet_interface))
        run(
            ["sysctl", f"net.ipv6.conf.{self._ethernet_interface}.proxy_ndp=1"],
            stdin=DEVNULL, stdout=PIPE, stderr=PIPE, encoding='utf-8', check=True,
        )

    def _add_all_existing_containers_to_neigh_proxy(self):
        # Adds all running containers to the IPv6 neighbour discovery proxy
        logger.info("Adding all runnning containers to IPv6 ndp proxy...")
        for container in self._client.containers.list():
            self._add_container_to_ipv6_ndp_proxy(container)
