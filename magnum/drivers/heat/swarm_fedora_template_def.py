# Copyright 2016 Rackspace Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from magnum.drivers.heat import template_def
from oslo_config import cfg

CONF = cfg.CONF
DOCKER_PORT = '2376'


class SwarmApiAddressOutputMapping(template_def.OutputMapping):

    def set_output(self, stack, cluster_template, cluster):
        if self.cluster_attr is None:
            return

        output_value = self.get_output_value(stack)
        if output_value is not None:
            # Note(rocha): protocol should always be tcp as the docker
            # command client does not handle https (see bug #1604812).
            params = {
                'protocol': 'tcp',
                'address': output_value,
                'port': DOCKER_PORT,
            }
            value = "%(protocol)s://%(address)s:%(port)s" % params
            setattr(cluster, self.cluster_attr, value)


class SwarmFedoraTemplateDefinition(template_def.BaseTemplateDefinition):
    """Docker swarm template for a Fedora Atomic VM."""

    def __init__(self):
        super(SwarmFedoraTemplateDefinition, self).__init__()
        self.add_parameter('cluster_uuid',
                           cluster_attr='uuid',
                           param_type=str)
        self.add_parameter('docker_volume_size',
                           cluster_attr='docker_volume_size')
        self.add_parameter('volume_driver',
                           cluster_template_attr='volume_driver')
        self.add_parameter('external_network',
                           cluster_template_attr='external_network_id',
                           required=True)
        self.add_parameter('fixed_network',
                           cluster_template_attr='fixed_network')
        self.add_parameter('fixed_subnet',
                           cluster_template_attr='fixed_subnet')
        self.add_parameter('network_driver',
                           cluster_template_attr='network_driver')
        self.add_parameter('tls_disabled',
                           cluster_template_attr='tls_disabled',
                           required=True)
        self.add_parameter('registry_enabled',
                           cluster_template_attr='registry_enabled')
        self.add_parameter('docker_storage_driver',
                           cluster_template_attr='docker_storage_driver')
        self.add_parameter('swarm_version',
                           cluster_attr='coe_version')

        self.add_output('api_address',
                        cluster_attr='api_address',
                        mapping_type=SwarmApiAddressOutputMapping)
        self.add_output('swarm_master_private',
                        cluster_attr=None)
        self.add_output('swarm_nodes_private',
                        cluster_attr=None)
        self.add_output('discovery_url',
                        cluster_attr='discovery_url')

    def add_nodegroup_params(self, cluster):
        super(SwarmFedoraTemplateDefinition,
              self).add_nodegroup_params(cluster)
        master_ng = cluster.default_ng_master
        worker_ng = cluster.default_ng_worker
        self.add_parameter('number_of_nodes',
                           nodegroup_attr='node_count',
                           nodegroup_uuid=worker_ng.uuid,
                           param_class=template_def.NodeGroupParameterMapping)
        self.add_parameter('node_flavor',
                           nodegroup_attr='flavor_id',
                           nodegroup_uuid=worker_ng.uuid,
                           param_class=template_def.NodeGroupParameterMapping)
        self.add_parameter('master_flavor',
                           nodegroup_attr='flavor_id',
                           nodegroup_uuid=master_ng.uuid,
                           param_class=template_def.NodeGroupParameterMapping)

    def update_outputs(self, stack, cluster_template, cluster):
        worker_ng = cluster.default_ng_worker
        master_ng = cluster.default_ng_master

        self.add_output('swarm_masters',
                        nodegroup_attr='node_addresses',
                        nodegroup_uuid=master_ng.uuid,
                        mapping_type=template_def.NodeGroupOutputMapping)
        self.add_output('swarm_nodes',
                        nodegroup_attr='node_addresses',
                        nodegroup_uuid=worker_ng.uuid,
                        mapping_type=template_def.NodeGroupOutputMapping)
        self.add_output('number_of_nodes',
                        nodegroup_attr='node_count',
                        nodegroup_uuid=worker_ng.uuid,
                        is_stack_param=True,
                        mapping_type=template_def.NodeGroupOutputMapping)
        super(SwarmFedoraTemplateDefinition,
              self).update_outputs(stack, cluster_template, cluster)

    def get_params(self, context, cluster_template, cluster, **kwargs):
        extra_params = kwargs.pop('extra_params', {})
        extra_params['discovery_url'] = self.get_discovery_url(cluster)
        # HACK(apmelton) - This uses the user's bearer token, ideally
        # it should be replaced with an actual trust token with only
        # access to do what the template needs it to do.
        osc = self.get_osc(context)
        extra_params['magnum_url'] = osc.magnum_url()

        label_list = ['flannel_network_cidr', 'flannel_backend',
                      'flannel_network_subnetlen', 'rexray_preempt',
                      'swarm_strategy']

        extra_params['auth_url'] = context.auth_url
        extra_params['nodes_affinity_policy'] = \
            CONF.cluster.nodes_affinity_policy

        # set docker_volume_type
        # use the configuration default if None provided
        docker_volume_type = cluster.labels.get(
            'docker_volume_type', CONF.cinder.default_docker_volume_type)
        extra_params['docker_volume_type'] = docker_volume_type

        for label in label_list:
            extra_params[label] = cluster.labels.get(label)

        if cluster_template.registry_enabled:
            extra_params['swift_region'] = CONF.docker_registry.swift_region
            extra_params['registry_container'] = (
                CONF.docker_registry.swift_registry_container)

        return super(SwarmFedoraTemplateDefinition,
                     self).get_params(context, cluster_template, cluster,
                                      extra_params=extra_params,
                                      **kwargs)

    def get_env_files(self, cluster_template, cluster):
        env_files = []

        template_def.add_priv_net_env_file(env_files, cluster_template)
        template_def.add_volume_env_file(env_files, cluster)
        template_def.add_lb_env_file(env_files, cluster_template)

        return env_files
