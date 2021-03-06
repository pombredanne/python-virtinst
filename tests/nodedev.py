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

import tests
import os.path
import unittest
import virtinst.NodeDeviceParser as nodeparse
from virtinst import VirtualHostDevice

conn = tests.open_testdriver()

unknown_xml = """
<device>
  <name>foodevice</name>
  <parent>computer</parent>
  <capability type='frobtype'>
    <hardware>
      <vendor>LENOVO</vendor>
    </hardware>
  </capability>
</device>
"""

class TestNodeDev(unittest.TestCase):

    def _nodeDevFromName(self, devname):
        node = conn.nodeDeviceLookupByName(devname)
        xml = node.XMLDesc(0)
        return nodeparse.parse(xml)

    def _testCompare(self, devname, vals, devxml=None):
        if devxml:
            dev = nodeparse.parse(devxml)
        else:
            dev = self._nodeDevFromName(devname)

        for attr in vals.keys():
            self.assertEqual(vals[attr], getattr(dev, attr))

    def _testNode2DeviceCompare(self, nodename, devfile, nodedev=None):
        devfile = os.path.join("tests/nodedev-xml/devxml", devfile)
        if not nodedev:
            nodedev = self._nodeDevFromName(nodename)

        dev = VirtualHostDevice.device_from_node(conn, nodedev=nodedev)
        tests.diff_compare(dev.get_xml_config() + "\n", devfile)

    def testSystemDevice(self):
        devname = "computer"
        vals = {"hw_vendor": "LENOVO", "hw_version": "ThinkPad T61",
                "hw_serial": "L3B2616",
                "hw_uuid": "97e80381-494f-11cb-8e0e-cbc168f7d753",
                "fw_vendor": "LENOVO", "fw_version": "7LET51WW (1.21 )",
                "fw_date": "08/22/2007",
                "device_type": nodeparse.CAPABILITY_TYPE_SYSTEM,
                "name": "computer", "parent": None}
        self._testCompare(devname, vals)

    def testNetDevice1(self):
        devname = "net_00_1c_25_10_b1_e4"
        vals = {"name": "net_00_1c_25_10_b1_e4", "parent": "pci_8086_1049",
                "device_type": nodeparse.CAPABILITY_TYPE_NET,
                "interface": "eth0", "address": "00:1c:25:10:b1:e4",
                "capability_type": "80203"}
        self._testCompare(devname, vals)

    def testNetDevice2(self):
        devname = "net_00_1c_bf_04_29_a4"
        vals = {"name": "net_00_1c_bf_04_29_a4", "parent": "pci_8086_4227",
                "device_type": nodeparse.CAPABILITY_TYPE_NET,
                "interface": "wlan0", "address": "00:1c:bf:04:29:a4",
                "capability_type": "80211"}
        self._testCompare(devname, vals)

    def testPCIDevice1(self):
        devname = "pci_1180_592"
        vals = {"name": "pci_1180_592", "parent": "pci_8086_2448",
                "device_type": nodeparse.CAPABILITY_TYPE_PCI,
                "domain": "0", "bus": "21", "slot": "0", "function": "4",
                "product_id": "0x0592", "vendor_id": "0x1180",
                "product_name": "R5C592 Memory Stick Bus Host Adapter",
                "vendor_name": "Ricoh Co Ltd",}
        self._testCompare(devname, vals)

    def testPCIDevice2(self):
        devname = "pci_8086_1049"
        vals = {"name": "pci_8086_1049", "parent": "computer",
                "device_type": nodeparse.CAPABILITY_TYPE_PCI,
                "domain": "0", "bus": "0", "slot": "25", "function": "0",
                "product_id": "0x1049", "vendor_id": "0x8086",
                "product_name": "82566MM Gigabit Network Connection",
                "vendor_name": "Intel Corporation",}
        self._testCompare(devname, vals)

    def testUSBDevDevice1(self):
        devname = "usb_device_781_5151_2004453082054CA1BEEE"
        vals = {"name": "usb_device_781_5151_2004453082054CA1BEEE",
                "parent": "usb_device_1d6b_2_0000_00_1a_7",
                "device_type": nodeparse.CAPABILITY_TYPE_USBDEV,
                "bus": "1", "device": "4", "product_id": '0x5151',
                "vendor_id": '0x0781',
                "vendor_name": "SanDisk Corp.",
                "product_name": "Cruzer Micro 256/512MB Flash Drive" }
        self._testCompare(devname, vals)

    def testUSBDevDevice2(self):
        devname = "usb_device_483_2016_noserial"
        vals = {"name": "usb_device_483_2016_noserial",
                "parent": "usb_device_1d6b_1_0000_00_1a_0",
                "device_type": nodeparse.CAPABILITY_TYPE_USBDEV,
                "bus": "3", "device": "2", "product_id": '0x2016',
                "vendor_id": '0x0483',
                "vendor_name": "SGS Thomson Microelectronics",
                "product_name": "Fingerprint Reader" }
        self._testCompare(devname, vals)

    def testStorageDevice1(self):
        devname = "storage_serial_SATA_WDC_WD1600AAJS__WD_WCAP95119685"
        vals = {"name": "storage_serial_SATA_WDC_WD1600AAJS__WD_WCAP95119685",
                "parent": "pci_8086_27c0_scsi_host_scsi_device_lun0",
                "device_type": nodeparse.CAPABILITY_TYPE_STORAGE,
                "block": "/dev/sda", "bus": "scsi", "drive_type": "disk",
                "model": "WDC WD1600AAJS-2", "vendor": "ATA",
                "size": 160041885696, "removable": False,
                "hotpluggable": False, "media_available": False,
                "media_size": 0, "media_label": None}
        self._testCompare(devname, vals)

    def testStorageDevice2(self):
        devname = "storage_serial_SanDisk_Cruzer_Micro_2004453082054CA1BEEE_0_0"
        vals = {"name": "storage_serial_SanDisk_Cruzer_Micro_2004453082054CA1BEEE_0_0",
                "parent": "usb_device_781_5151_2004453082054CA1BEEE_if0_scsi_host_0_scsi_device_lun0",
                "device_type": nodeparse.CAPABILITY_TYPE_STORAGE,
                "block": "/dev/sdb", "bus": "usb", "drive_type": "disk",
                "model": "Cruzer Micro", "vendor": "SanDisk", "size": 0,
                "removable": True, "hotpluggable": True,
                "media_available": True, "media_size": 12345678 }
        self._testCompare(devname, vals)

    def testUSBBus(self):
        devname = "usb_device_1d6b_1_0000_00_1d_1_if0"
        vals = {"name": "usb_device_1d6b_1_0000_00_1d_1_if0",
                "parent": "usb_device_1d6b_1_0000_00_1d_1",
                "device_type": nodeparse.CAPABILITY_TYPE_USBBUS,
                "number": "0", "classval": "9", "subclass": "0",
                "protocol": "0"}
        self._testCompare(devname, vals)

    def testSCSIBus(self):
        devname = "pci_8086_2829_scsi_host_1"
        vals = {"name": "pci_8086_2829_scsi_host_1",
                "parent": "pci_8086_2829",
                "device_type": nodeparse.CAPABILITY_TYPE_SCSIBUS,
                "host": "2"}
        self._testCompare(devname, vals)

    def testNPIV(self):
        devname = "pci_10df_fe00_0_scsi_host"
        vals = {"name": "pci_10df_fe00_0_scsi_host",
                "device_type": nodeparse.CAPABILITY_TYPE_SCSIBUS,
                "host": "4", "fc_host": True, "vport_ops" : True,
                "wwnn": "20000000c9848141", "wwpn": "10000000c9848141"}
        self._testCompare(devname, vals)

    def testSCSIDevice(self):
        devname = "pci_8086_2829_scsi_host_scsi_device_lun0"
        vals = {"name": "pci_8086_2829_scsi_host_scsi_device_lun0",
                "parent": "pci_8086_2829_scsi_host",
                "host": "0", "bus": "0", "target": "0", "lun": "0",
                "type": "disk"}
        self._testCompare(devname, vals)

    def testUnknownDevice(self):
        vals = {"name": "foodevice", "parent": "computer",
                "device_type": "frobtype"}
        self._testCompare(None, vals, devxml=unknown_xml)

        # NodeDevice 2 Device XML tests
    def testNodeDev2USB1(self):
        nodename = "usb_device_781_5151_2004453082054CA1BEEE"
        devfile = "usbdev1.xml"
        self._testNode2DeviceCompare(nodename, devfile)

    def testNodeDev2USB2(self):
        nodename = "usb_device_781_5151_2004453082054CA1BEEE"
        devfile = "usbdev2.xml"
        nodedev = self._nodeDevFromName(nodename)

        # Force xml building to use bus, addr
        nodedev.product_id = None
        nodedev.vendor_id = None

        self._testNode2DeviceCompare(nodename, devfile, nodedev=nodedev)

    def testNodeDev2PCI(self):
        nodename = "pci_1180_592"
        devfile = "pcidev.xml"
        self._testNode2DeviceCompare(nodename, devfile)

    def testNodeDevFail(self):
        nodename = "usb_device_1d6b_1_0000_00_1d_1_if0"
        devfile = ""

        # This should exist, since usbbus is not a valid device to
        # pass to a guest.
        self.assertRaises(ValueError,
                          self._testNode2DeviceCompare, nodename, devfile)

if __name__ == "__main__":
    unittest.main()
