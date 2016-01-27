#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

"""Availability Zone action implementations"""

import copy
import logging

from cliff import lister
from novaclient import exceptions as nova_exceptions
import six

from openstackclient.common import utils
from openstackclient.i18n import _  # noqa


def _xform_common_availability_zone(az, zone_info):
    if hasattr(az, 'zoneState'):
        zone_info['zone_status'] = ('available' if az.zoneState['available']
                                    else 'not available')
    if hasattr(az, 'zoneName'):
        zone_info['zone_name'] = az.zoneName


def _xform_compute_availability_zone(az, include_extra):
    result = []
    zone_info = {}
    _xform_common_availability_zone(az, zone_info)

    if not include_extra:
        result.append(zone_info)
        return result

    if hasattr(az, 'hosts') and az.hosts:
        for host, services in six.iteritems(az.hosts):
            host_info = copy.deepcopy(zone_info)
            host_info['host_name'] = host

            for svc, state in six.iteritems(services):
                info = copy.deepcopy(host_info)
                info['service_name'] = svc
                info['service_status'] = '%s %s %s' % (
                    'enabled' if state['active'] else 'disabled',
                    ':-)' if state['available'] else 'XXX',
                    state['updated_at'])
                result.append(info)
    else:
        zone_info['host_name'] = ''
        zone_info['service_name'] = ''
        zone_info['service_status'] = ''
        result.append(zone_info)
    return result


def _xform_volume_availability_zone(az):
    result = []
    zone_info = {}
    _xform_common_availability_zone(az, zone_info)
    result.append(zone_info)
    return result


class ListAvailabilityZone(lister.Lister):
    """List availability zones and their status"""

    log = logging.getLogger(__name__ + '.ListAvailabilityZone')

    def get_parser(self, prog_name):
        parser = super(ListAvailabilityZone, self).get_parser(prog_name)
        parser.add_argument(
            '--compute',
            action='store_true',
            default=False,
            help='List compute availability zones')
        parser.add_argument(
            '--volume',
            action='store_true',
            default=False,
            help='List volume availability zones')
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help=_('List additional fields in output'),
        )
        return parser

    def get_compute_availability_zones(self, parsed_args):
        compute_client = self.app.client_manager.compute
        try:
            data = compute_client.availability_zones.list()
        except nova_exceptions.Forbidden as e:  # policy doesn't allow
            try:
                data = compute_client.availability_zones.list(detailed=False)
            except Exception:
                raise e

        # Argh, the availability zones are not iterable...
        result = []
        for zone in data:
            result += _xform_compute_availability_zone(zone, parsed_args.long)
        return result

    def get_volume_availability_zones(self, parsed_args):
        volume_client = self.app.client_manager.volume
        try:
            data = volume_client.availability_zones.list()
        except Exception:
            message = "Availability zones list not supported by " \
                      "Block Storage API"
            self.log.warning(message)

        result = []
        for zone in data:
            result += _xform_volume_availability_zone(zone)
        return result

    @utils.log_method(log)
    def take_action(self, parsed_args):

        if parsed_args.long:
            columns = ('Zone Name', 'Zone Status',
                       'Host Name', 'Service Name', 'Service Status')
        else:
            columns = ('Zone Name', 'Zone Status')

        # Show everything by default.
        show_all = (not parsed_args.compute and not parsed_args.volume)

        result = []
        if parsed_args.compute or show_all:
            result += self.get_compute_availability_zones(parsed_args)
        if parsed_args.volume or show_all:
            result += self.get_volume_availability_zones(parsed_args)

        return (columns,
                (utils.get_dict_properties(
                    s, columns
                ) for s in result))