import unittest
import mock
from docker_ndp_daemon import config
import logging
from docker_ndp_daemon.daemon import DockerNdpDaemon
import docker
from docker import DockerClient
from docker.models.resource import Model
from docker.models.containers import Container
from subprocess import Popen

logger = logging.getLogger(__name__)
logging.basicConfig(format=config.logger.format)
logging.root.setLevel(config.logger.level)


class DockerNdpDaemonTest(unittest.TestCase):

    def setUp(self):
        """Sets _daemon with mocked :class:`DockerClient``
        """
        with mock.patch.object(DockerClient, '__init__', return_value=None):
            with mock.patch.object(DockerNdpDaemon, '_activate_ndp_proxy') as mock_activate:
                mock_activate.return_value = (0, "command", None)
                with mock.patch.object(DockerNdpDaemon, '_add_all_existing_containers_to_neigh_proxy'):
                    with mock.patch.object(DockerNdpDaemon, 'listen_network_connect_events'):
                        self._daemon = DockerNdpDaemon(socket_url="socket", ethernet_interface="ethernet")

    @mock.patch.object(DockerClient, '__init__', return_value=None)
    @mock.patch.object(DockerNdpDaemon, '_activate_ndp_proxy', side_effect=Exception("Command Error"))
    def test_init__fail(self, mock_activate_proxy, mock_client):
        """Tests if an exception raises when _activate_ndp_proxy's return code != 0"""
        try:
            DockerNdpDaemon(socket_url="socket", ethernet_interface="ethernet")
            self.fail("ValueError expected")
        except Exception as ex:
            logger.info("{}: {}".format(ex.__class__, ex))
            self.assertTrue(mock_activate_proxy.called)
            self.assertTrue(mock_client.called)

    @mock.patch.object(docker.models.containers.ContainerCollection, 'get')
    @mock.patch.object(DockerNdpDaemon, '_add_container_to_ipv6_ndp_proxy')
    def test_handle_network_connect_event__ok(self, mock_add_container, mock_containers):
        """Tests if the container ID was fetched out of the right element branch and IPv6 was returend and passed."""
        event = {'Actor': {'Attributes': {'container': 42}}}
        self._daemon._handle_network_connect_event(event)
        self.assertTrue(mock_containers.called)
        self.assertTrue(mock_add_container.called)

    @mock.patch.object(DockerNdpDaemon, '_try_fetch_ipv6_address', return_value="IPv6")
    @mock.patch.object(DockerNdpDaemon, '_add_ipv6_neigh_proxy', return_value=(0, "COMMAND", None))
    def test_add_container_to_ipv6_ndp_proxy__ok(self, mock_add_ip, mock_add_proxy):
        """Tests if IPv6 was returend and passed to 'add' method."""
        self._daemon._add_container_to_ipv6_ndp_proxy(Container())
        self.assertTrue(mock_add_proxy.called)
        self.assertTrue(mock_add_ip.called)
        self.assertEqual(("IPv6",), mock_add_ip.call_args[0])

    @mock.patch.object(DockerNdpDaemon, '_try_fetch_ipv6_address', return_value=None)
    @mock.patch.object(DockerNdpDaemon, '_add_ipv6_neigh_proxy')
    def test_add_container_to_ipv6_ndp_proxy__ok_no_ipv6_address(self, mock_add_ip, mock_add_proxy):
        """Tests if the method returns if no ipv6 address was found"""
        self._daemon._add_container_to_ipv6_ndp_proxy(Container())
        self.assertTrue(mock_add_proxy.called)
        self.assertFalse(mock_add_ip.called)  # Must not be called because method returned before

    @mock.patch.object(DockerNdpDaemon, '_try_fetch_ipv6_address', return_value="IPv6")
    @mock.patch.object(DockerNdpDaemon, '_add_ipv6_neigh_proxy', side_effect=Exception("Command Error"))
    def test_add_container_to_ipv6_ndp_proxy__fail_add_proxy_returns_1(self, mock_add_ip, mock_add_proxy):
        """Tests when called method _try_fetch_ipv6_address returned code != 0"""
        try:
            self._daemon._add_container_to_ipv6_ndp_proxy(Container())
            self.fail("Error expected")
        except Exception as ex:
            logger.info("{}: {}".format(ex.__class__, ex))
            self.assertTrue(mock_add_proxy.called)
            self.assertTrue(mock_add_ip.called)

    @mock.patch.object(DockerNdpDaemon, 'fetch_ipv6_address', return_value='IPv6')
    @mock.patch('docker.models.containers.Container')
    def test_try_fetch_ipv6_address__ok(self, mock_container, mock_ipv6_address):
        """Test if the method returns a found IPv6 address"""
        ipv6_address = self._daemon._try_fetch_ipv6_address(mock_container)
        self.assertEqual("IPv6", ipv6_address)
        self.assertTrue(mock_ipv6_address.called)

    @mock.patch.object(DockerNdpDaemon, 'fetch_ipv6_address', return_value=None)
    @mock.patch('docker.models.containers.Container')
    def test_try_fetch_ipv6_address__ok_no_ip_found(self, mock_container, mock_ipv6_address):
        """Test if the method returns None if no IPv6 address was found"""
        ipv6_address = self._daemon._try_fetch_ipv6_address(mock_container)
        self.assertEqual(None, ipv6_address)
        self.assertTrue(mock_ipv6_address.called)

    @mock.patch.object(DockerNdpDaemon, 'fetch_ipv6_address', side_effect=Exception("Command Error"))
    @mock.patch('docker.models.containers.Container')
    def test_try_fetch_ipv6_address__fail_error_fetching_ip_address(self, mock_container, mock_ipv6_address):
        """Test if the method raises Error if fetching ipv6 address returned code != 0"""
        try:
            self._daemon._try_fetch_ipv6_address(mock_container)
            self.fail("Exception expected!")
        except Exception as ex:
            self.assertTrue(mock_ipv6_address.called)

    # @mock.patch.object(Popen, 'communicate', return_value=(bytearray("\n", "utf-8"), bytearray("\n", "utf-8")))
    # def test_add_ipv6_neigh_proxy__ok(self, mock_communicate):
    #     """Tests if the right command was called to add an ipv6 address to the ndp proxy"""
    #     self._daemon._add_ipv6_neigh_proxy("fe80::1")
    #     # self.assertEqual(0, returncode)
    #     self.assertEqual("sudo ip -6 neigh add proxy {} dev {}".format("fe80::1", "ethernet"), command)
    #     self.assertIsNone(stderr)
    #     self.assertTrue(mock_communicate.called)

    # @mock.patch.object(Popen, 'communicate', return_value=(bytearray("\n", "utf-8"), bytearray("\n", "utf-8")))
    # def test__activate_ndp_proxy__ok(self, mock_communicate):
    #     """Tests if the right command was called to activate ipv6 ndp Proxy"""
    #     self._daemon._activate_ndp_proxy()
    #     # self.assertEqual(0, returncode)
    #     self.assertEqual("sudo sysctl net.ipv6.conf.{}.proxy_ndp=1".format("ethernet"), command)
    #     self.assertIsNone(stderr)
    #     self.assertTrue(mock_communicate.called)

    @mock.patch.object(docker.models.containers.ContainerCollection, 'list')
    @mock.patch.object(DockerNdpDaemon, '_add_container_to_ipv6_ndp_proxy')
    def test_add_all_existing_containers_to_neigh_proxy_ok(self, mock_add_container, mock_containers):
        """Tests if adding ipv6 to ndp proxy is called for all active containers"""
        mock_containers.return_value = [Container(), Container(), Container()]
        self._daemon._add_all_existing_containers_to_neigh_proxy()
        self.assertEqual(3, mock_add_container.call_count)
        self.assertTrue(mock_add_container.called)


if __name__ == '__main__':
    unittest.main()
