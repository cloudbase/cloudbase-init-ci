from oslo_log import log
from tempest import config
from tempest.common import fixed_network
from tempest.common import waiters
from tempest.common.utils import data_utils
from tempest.scenario import manager

from argus import util

ARGUS_CONF = util.get_config()
CONF = config.CONF
LOG = log.getLogger(__name__)

# Starting size as number of lines and tolerance.
OUTPUT_SIZE = 128
OUTPUT_EPSILON = int(OUTPUT_SIZE / 10)
OUTPUT_STATUS_OK = [200]


class TempestBackend(manager.ScenarioTest):

    def __init__(self):
        self.__class__.setUpClass()

    @classmethod
    def setup_instance(cls):
        """Sets up an Openstack instance"""
        cls.image = None
        cls.server = cls._create_server()
        cls.fip = cls._create_fip()
        cls.floating_ips_client.associate_floating_ip_to_server(
            cls.fip['ip'], cls.server['id'])
        cls.security_group = cls._create_security_group()
        cls.servers_client.add_security_group(cls.server['id'],
                                              cls.security_group['name'])
        cls.remote_client = cls.get_remote_client()
        cls.introspection = cls.introspection_class(cls.remote_client)
        if cls.recipe_class:
            recipe = cls.recipe_class(
                cls.server['id'], cls.manager, cls.remote_client, cls.image, cls.service_type, None)
            recipe.prepare()

    @classmethod
    def _create_server(cls, name=None, image=None, flavor=None,
                       wait_on_boot=True, create_kwargs=None):
        """Creates VM instance.
        @param image: image from which to create the instance
        @param wait_on_boot: wait for status ACTIVE before continue
        @param create_kwargs: additional details for instance creation
        @return: server dict
        """
        if name is None:
            name = data_utils.rand_name(cls.__name__)
        if image is None:
            image = CONF.compute.image_ref
        if flavor is None:
            flavor = CONF.compute.flavor_ref
        if create_kwargs is None:
            create_kwargs = {}
        network = cls.get_tenant_network()
        create_kwargs = fixed_network.set_networks_kwarg(network,
                                                         create_kwargs)
        # add dns nameservers to subnet
        cred_provider = cls._get_credentials_provider()
        primary_creds = cred_provider.get_primary_creds()
        subnet = getattr(primary_creds, 'subnet', None)
        cls.network_client.update_subnet(subnet['id'], dns_nameservers=['8.8.8.8'])

        LOG.debug("Creating a server (name: %s, image: %s, flavor: %s)",
                  name, image, flavor)
        server = cls.servers_client.create_server(name, image, flavor,
                                                  **create_kwargs)

        if wait_on_boot:
            waiters.wait_for_server_status(cls.servers_client,
                                           server_id=server['id'],
                                           status='ACTIVE')

        # The instance retrieved on creation is missing network
        # details, necessitating retrieval after it becomes active to
        # ensure correct details.
        server = cls.servers_client.show_server(server['id'])
        return server

    @classmethod
    def get_remote_client(cls, fip=None, username=None, password=None,
                          service_type=None):
        if not fip:
            fip = cls.fip['ip']
        if not username:
            username = cls.image.default_ci_username
        if not password:
            password = cls.image.default_ci_password
        if not service_type:
            service_type = cls.service_type
        return util.WinRemoteClient(fip, username, password, service_type)

    @property
    def run_command_verbose(self):
        return self.remote_client.run_command_verbose

    @classmethod
    def _create_fip(cls):
        return cls.floating_ips_client.create_floating_ip()

    @classmethod
    def _create_security_group(cls):
        sg_name = util.rand_name(cls.__name__)
        sg_desc = sg_name + " description"
        secgroup = cls.security_groups_client.create_security_group(
            sg_name, sg_desc)
        # Add rules to the security group.
        rulesets = [
            {
                # http RDP
                'ip_proto': 'tcp',
                'from_port': 3389,
                'to_port': 3389,
                'cidr': '0.0.0.0/0',
            },
            {
                # http winrm
                'ip_proto': 'tcp',
                'from_port': 5985,
                'to_port': 5985,
                'cidr': '0.0.0.0/0',
            },
            {
                # https winrm
                'ip_proto': 'tcp',
                'from_port': 5986,
                'to_port': 5986,
                'cidr': '0.0.0.0/0',
            },
            {
                # ssh
                'ip_proto': 'tcp',
                'from_port': 22,
                'to_port': 22,
                'cidr': '0.0.0.0/0',
            },
            {
                # ping
                'ip_proto': 'icmp',
                'from_port': -1,
                'to_port': -1,
                'cidr': '0.0.0.0/0',
            },
        ]
        for ruleset in rulesets:
            cls.security_groups_client.create_security_group_rule(
                secgroup['id'], **ruleset)
        return secgroup

    @classmethod
    def _instance_output(cls, limit):
        ret = cls.manager.servers_client.get_console_output(
            cls.server['id'], limit)
        return ret.response, ret.data

    def instance_output(self, limit=OUTPUT_SIZE):
        """Get the console output, sent from the instance."""
        content = None
        while True:
            resp, content = self._instance_output(limit)
            if resp.status not in OUTPUT_STATUS_OK:
                LOG.error("Couldn't get console output <%d>.", resp.status)
                return

            if len(content.splitlines()) >= (limit - OUTPUT_EPSILON):
                limit *= 2
            else:
                break
        return content

    @classmethod
    def get_server(cls):
        return cls.manager.servers_client.show_server(cls.server['id'])

    @classmethod
    def get_metadata(cls):
        return cls.metadata

    @classmethod
    def instance_password(cls):
        """Get the password posted by the instance."""
        encoded_password = cls.manager.servers_client.get_password(
            cls.server['id'])
        return util.decrypt_password(
            private_key=ARGUS_CONF.argus.path_to_private_key,
            password=encoded_password['password'])

    @classmethod
    def cleanup(cls):
        # TODO (ionuthulub) make sure all the resources are cleaned
        cls.servers_client.delete_server(cls.server['id'])
        cls.servers_client.wait_for_server_termination(cls.server['id'])
