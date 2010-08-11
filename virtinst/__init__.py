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

import gettext

gettext_dir = "::LOCALEDIR::"
gettext_app = "virtinst"

gettext.bindtextdomain(gettext_app, gettext_dir)

def _virtinst(msg):
    return gettext.dgettext(gettext_app, msg)

from version import __version__
__version_info__ = tuple([ int(num) for num in __version__.split('.')])

import Storage
import Interface
from Guest import Guest, XenGuest
from VirtualDevice import VirtualDevice
from VirtualNetworkInterface import VirtualNetworkInterface, \
                                    XenNetworkInterface
from VirtualGraphics import VirtualGraphics
from VirtualAudio import VirtualAudio
from VirtualInputDevice import VirtualInputDevice
from VirtualDisk import VirtualDisk, XenDisk
from VirtualHostDevice import (VirtualHostDevice, VirtualHostDeviceUSB,
                               VirtualHostDevicePCI)
from VirtualCharDevice import VirtualCharDevice
from VirtualVideoDevice import VirtualVideoDevice
from VirtualController import VirtualController
from VirtualWatchdog import VirtualWatchdog
from FullVirtGuest import FullVirtGuest
from ParaVirtGuest import ParaVirtGuest
from DistroInstaller import DistroInstaller
from PXEInstaller import PXEInstaller
from LiveCDInstaller import LiveCDInstaller
from ImportInstaller import ImportInstaller
from ImageInstaller import ImageInstaller
from CloneManager import CloneDesign
from User import User
from Clock import Clock
from Seclabel import Seclabel
import util
import support

# This represents the PUBLIC API. Any changes to these classes (or 'util.py')
# must be mindful of this fact.
__all__ = ["Guest", "XenGuest", "VirtualNetworkInterface",
           "XenNetworkInterface", "VirtualGraphics", "VirtualAudio",
           "VirtualDisk", "XenDisk", "FullVirtGuest", "ParaVirtGuest",
           "DistroInstaller", "PXEInstaller", "LiveCDInstaller",
           "ImportInstaller", "ImageInstaller", "CloneDesign",
           "Storage", "Interface",
           "User", "util", "support", "VirtualDevice", "Clock", "Seclabel",
           "VirtualHostDevice", "VirtualHostDeviceUSB", "VirtualVideoDevice",
           "VirtualHostDevicePCI", "VirtualCharDevice", "VirtualInputDevice",
           "VirtualController", "VirtualWatchdog"]
