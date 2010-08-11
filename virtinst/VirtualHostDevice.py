#
# Copyright 2009  Red Hat, Inc.
# Cole Robinson <crobinso@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free  Software Foundation; either version 2 of the License, or
# (at your option)  any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.

import VirtualDevice
import NodeDeviceParser
import logging
import libvirt

from virtinst import support
from virtinst import _util
from virtinst import _virtinst as _

class VirtualHostDevice(VirtualDevice.VirtualDevice):

    _virtual_device_type = VirtualDevice.VirtualDevice.VIRTUAL_DEV_HOSTDEV

    def device_from_node(conn, name=None, nodedev=None):
        """
        Convert the passed device name to a VirtualHostDevice
        instance, with proper error reporting. Name can be any of the
        values accepted by NodeDeviceParser.lookupNodeName. If a node
        device name is not specified, a virtinst.NodeDevice instance can
        be passed in to create a dev from.

        @param conn: libvirt.virConnect instance to perform the lookup on
        @param name: optional libvirt node device name to lookup
        @param nodedev: optional L{virtinst.NodeDevice} instance to use

        @rtype: L{virtinst.VirtualHostDevice} instance
        """

        if not name and not nodedev:
            raise ValueError(_("'name' or 'nodedev' required."))

        if nodedev:
            nodeinst = nodedev
        else:
            nodeinst = NodeDeviceParser.lookupNodeName(conn, name)

        if isinstance(nodeinst, NodeDeviceParser.PCIDevice):
            return VirtualHostDevicePCI(conn, nodedev=nodeinst)
        elif isinstance(nodeinst, NodeDeviceParser.USBDevice):
            return VirtualHostDeviceUSB(conn, nodedev=nodeinst)
        elif isinstance(nodeinst, NodeDeviceParser.NetDevice):
            parentname = nodeinst.parent
            try:
                return VirtualHostDevice.device_from_node(conn,
                                                          name=parentname)
            except:
                logging.exception("Fetching net parent device failed.")

        raise ValueError(_("Node device type '%s' cannot be attached to "
                           " guest.") % nodeinst.device_type)

    device_from_node = staticmethod(device_from_node)

    def __init__(self, conn, nodedev):
        """
        @param conn: Connection the device/guest will be installed on
        @type conn: libvirt.virConnect
        @param nodedev: Optional NodeDevice instance for device being
                         attached to the guest
        @type nodedev: L{virtinst.NodeDeviceParser.NodeDevice}
        """
        VirtualDevice.VirtualDevice.__init__(self, conn)

        self.mode = None
        self.type = None

        self.managed = True
        if _util.get_uri_driver(self.conn.getURI()).lower() == "xen":
            self.managed = False

        self._nodedev = nodedev

    def _get_source_xml(self):
        raise NotImplementedError("Must be implemented in subclass")

    def setup(self, conn = None):
        """
        Perform DeviceDetach and DeviceReset calls if necessary

        @param conn: libvirt virConnect instance to use (defaults to devices
                     connection)
        """
        raise NotImplementedError

    def get_xml_config(self):
        xml =  ("    <hostdev mode='%s' type='%s' managed='%s'>\n" % \
                (self.mode, self.type, self.managed and "yes" or "no"))
        xml += "      <source>\n"
        xml += self._get_source_xml()
        xml += "      </source>\n"
        xml += "    </hostdev>"
        return xml


class VirtualHostDeviceUSB(VirtualHostDevice):

    def __init__(self, conn, nodedev=None):
        VirtualHostDevice.__init__(self, conn, nodedev)

        self.mode = "subsystem"
        self.type = "usb"

        self.vendor = None
        self.product = None

        self.bus = None
        self.device = None

        self._set_from_nodedev(self._nodedev)


    def _set_from_nodedev(self, nodedev):
        if not nodedev:
            return

        if not isinstance(nodedev, NodeDeviceParser.USBDevice):
            raise ValueError(_("'nodedev' must be a USBDevice instance."))

        self.vendor = nodedev.vendor_id
        self.product = nodedev.product_id
        self.bus = nodedev.bus
        self.device = nodedev.device

    def _get_source_xml(self):
        xml = ""
        if self.vendor and self.product:
            xml += "        <vendor id='%s'/>\n" % self.vendor
            xml += "        <product id='%s'/>\n" % self.product
        elif self.bus and self.device:
            xml += "        <address bus='%s' device='%s'/>\n" % (self.bus,
                                                                  self.device)
        else:
            raise RuntimeError(_("'vendor' and 'product', or 'bus' and "
                                 " 'device' are required."))
        return xml

    def setup_dev(self, conn=None, meter=None):
        return self.setup(conn)

    def setup(self, conn = None):
        """
        DEPRECATED: Please use setup_dev instead
        """
        if not conn:
            conn = self.conn

        # No libvirt api support for USB Detach/Reset yet
        return

class VirtualHostDevicePCI(VirtualHostDevice):

    def __init__(self, conn, nodedev=None):
        VirtualHostDevice.__init__(self, conn, nodedev)

        self.mode = "subsystem"
        self.type = "pci"

        self.domain = "0x0"
        self.bus = None
        self.slot = None
        self.function = None

        self._set_from_nodedev(self._nodedev)


    def _set_from_nodedev(self, nodedev):
        if not nodedev:
            return

        if not isinstance(nodedev, NodeDeviceParser.PCIDevice):
            raise ValueError(_("'nodedev' must be a PCIDevice instance."))

        self.domain = nodedev.domain
        self.bus = nodedev.bus
        self.slot = nodedev.slot
        self.function = nodedev.function

    def _get_source_xml(self):
        if not (self.domain and self.bus and self.slot and self.function):
            raise RuntimeError(_("'domain', 'bus', 'slot', and 'function' "
                                 "must be specified."))

        xml = "        <address domain='%s' bus='%s' slot='%s' function='%s'/>\n"
        return xml % (self.domain, self.bus, self.slot, self.function)

    def setup_dev(self, conn=None, meter=None):
        """
        Perform DeviceDetach and DeviceReset calls if necessary

        @param conn: libvirt virConnect instance to use (defaults to devices
                     connection)
        """
        return self.setup(conn)

    def setup(self, conn = None):
        """
        DEPRECATED: Please use setup_dev instead
        """
        if not conn:
            conn = self.conn

        if not NodeDeviceParser.is_pci_detach_capable(conn):
            return

        try:
            try:
                # Do this as a sanity check, so that we don't fail at domain
                # start time. This is independent of the 'managed' state, since
                # this should work regardless.
                node = conn.nodeDeviceLookupByName(self._nodedev.name)
                node.dettach()
                node.reset()
            except libvirt.libvirtError, e:
                if not support.is_error_nosupport(e):
                    raise
        except Exception, e:
            raise RuntimeError(_("Could not detach PCI device: %s" % str(e)))


