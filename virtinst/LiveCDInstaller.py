#
# An installer class for LiveCD images
#
# Copyright 2007  Red Hat, Inc.
# Mark McLoughlin <markmc@redhat.com>
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

import Installer
from VirtualDisk import VirtualDisk
from virtinst import _virtinst as _

class LiveCDInstallerException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class LiveCDInstaller(Installer.Installer):
    def __init__(self, type = "xen", location = None, os_type = None,
                 conn = None):
        self._install_disk = None
        Installer.Installer.__init__(self, type=type, location=location,
                                     os_type=os_type, conn=conn)

    # LiveCD specific methods/overwrites

    def _get_location(self):
        return self._location
    def _set_location(self, val):
        path = None
        vol_tuple = None
        if type(val) is tuple:
            vol_tuple = val
        else:
            path = val

        if path or vol_tuple:
            self._install_disk = VirtualDisk(path=path, conn=self.conn,
                                             volName=vol_tuple,
                                             device = VirtualDisk.DEVICE_CDROM,
                                             readOnly = True)

        self._location = val
        self.cdrom = True
    location = property(_get_location, _set_location)


    # General Installer methods
    def prepare(self, guest, meter):
        self.cleanup()

        if not self._install_disk:
            raise ValueError(_("CDROM media must be specified for the live "
                               "CD installer."))

        self.install_devices.append(self._install_disk)

    def post_install_check(self, guest):
        return True

    # Internal methods
    def _get_bootdev(self, isinstall, guest):
        if isinstall:
            return None
        return self.bootconfig.BOOT_DEVICE_CDROM