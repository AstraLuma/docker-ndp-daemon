import logging
from .events import DockerEventDaemon
from subprocess import run, PIPE, DEVNULL

logger = logging.getLogger(__name__)


class DockerNdpDaemon(DockerEventDaemon):
    """A special :class:`DockerEventDaemon` that adds IPv6 addresses of
    recently started docker containers to the NDP proxy for
    getting IPv6 internet connectivity.
    """
    ethernet_interface = None

    def __init__(self, *, socket_url=None, ethernet_interface):
        """ Creates a new instance.

        :param (str) socket_url: Path of the dockerndp socket file.
        :param (str) ethernet_interface: Name of the ethernet interface that is
           an internet gateway.
        """
        super().__init__(socket_url=socket_url)
        self.ethernet_interface = ethernet_interface
        self._address_cache = {}  # (container id, network name) -> ip address

    def __enter__(self):
        rv = super().__enter__()
        self._activate_ndp_proxy()
        self._add_all_existing_containers_to_neigh_proxy()
        return rv

    def handle_network_connect_event(self, event):
        logger.debug("event: %r", event)
        # Fetches Container from id in event
        container_id = event['Actor']['Attributes']['container']
        network = event['Actor']['Attributes']['name']
        container = self._client.containers.get(container_id)
        logger.debug("Event: Container %r connected to %s network",
                     container.name, network)
        self._add_container_to_ipv6_ndp_proxy(container, network)

    def handle_network_disconnect_event(self, event):
        logger.debug("event: %r", event)
        # Fetches Container from id in event
        container_id = event['Actor']['Attributes']['container']
        network = event['Actor']['Attributes']['name']
        container = self._client.containers.get(container_id)
        logger.debug("Event: Container %r disconnected from %s network",
                     container.name, network)
        self._del_container_from_ipv6_ndp_proxy(container, network)

    def _add_container_to_ipv6_ndp_proxy(self, container, network):
        ipv6_address = container.attrs['NetworkSettings']['Networks'][network]['GlobalIPv6Address']
        if not ipv6_address:
            logger.info(
                "Ignoring container %r on %r. It has no IPv6 address.", container.name, network,
            )
            return

        self._address_cache[container, network] = ipv6_address

        self._add_ipv6_neigh_proxy(ipv6_address)

        logger.info("Set IPv6 ndp proxy for container %r: %r", container.name, ipv6_address)

    def _del_container_from_ipv6_ndp_proxy(self, container, network):
        try:
            ipv6_address = self._address_cache[container, network]
        except KeyError:
            logger.info(
                "Ignoring container %r on %r. I don't remember its IPv6 address.",
                container.name, network,
            )
            return

        self._del_ipv6_neigh_proxy(ipv6_address)

        logger.info("Removed IPv6 ndp proxy for container %r: %r", container.name, ipv6_address)

    def _add_ipv6_neigh_proxy(self, ipv6_address) -> (int, str, str):
        # Sets IPv6 neighbour discovery to ethernet interface.
        logger.info("Adding %r to proxy on %r ...", ipv6_address, self.ethernet_interface)
        run(
            ['ip', '-6', 'neigh', 'add', 'proxy', ipv6_address, 'dev', self.ethernet_interface],
            stdin=DEVNULL, stdout=PIPE, encoding='utf-8', check=True,
        )

    def _del_ipv6_neigh_proxy(self, ipv6_address) -> (int, str, str):
        # Remove IPv6 neighbour discovery to ethernet interface.
        logger.info("Removing %r from %r ...", ipv6_address, self.ethernet_interface)
        run(
            ['ip', '-6', 'neigh', 'del', 'proxy', ipv6_address, 'dev', self.ethernet_interface],
            stdin=DEVNULL, stdout=PIPE, encoding='utf-8', check=True,
        )

    def _activate_ndp_proxy(self):
        # Activates the ndp proxy
        logger.info("Activating IPv6 ndp proxy on %r ...", self.ethernet_interface)
        run(
            ["sysctl", f"net.ipv6.conf.{self.ethernet_interface}.proxy_ndp=1"],
            stdin=DEVNULL, stdout=PIPE, stderr=PIPE, encoding='utf-8', check=True,
        )

    def _add_all_existing_containers_to_neigh_proxy(self):
        # Adds all running containers to the IPv6 neighbour discovery proxy
        logger.info("Adding all runnning containers to IPv6 ndp proxy...")
        for container in self._client.containers.list():
            for network in container.attrs['NetworkSettings']['Networks'].keys():
                self._add_container_to_ipv6_ndp_proxy(container, network)
