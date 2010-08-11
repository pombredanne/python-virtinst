#
# Copyright 2006-2009  Red Hat, Inc.
# Daniel P. Berrange <berrange@redhat.com>
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

import logging
import os
import sys
import shutil
import subprocess
import tempfile

import _util
import Installer
from VirtualDisk import VirtualDisk
from User import User
import OSDistro

from virtinst import _virtinst as _

def _is_url(url, is_local):
    """
    Check if passed string is a (pseudo) valid http, ftp, or nfs url.
    """
    if is_local and os.path.exists(url):
        if os.path.isdir(url):
            return True
        else:
            return False

    return (url.startswith("http://") or url.startswith("ftp://") or
            url.startswith("nfs:"))

def _sanitize_url(url):
    """
    Do nothing for http or ftp, but make sure nfs is in the expected format
    """
    if url.startswith("nfs://"):
        # Convert RFC compliant NFS      nfs://server/path/to/distro
        # to what mount/anaconda expect  nfs:server:/path/to/distro
        # and carry the latter form around internally
        url = "nfs:" + url[6:]

        # If we need to add the : after the server
        index = url.find("/", 4)
        if index == -1:
            raise ValueError(_("Invalid NFS format: No path specified."))
        if url[index - 1] != ":":
            url = url[:index] + ":" + url[index:]

    return url

class DistroInstaller(Installer.Installer):
    def __init__(self, type = "xen", location = None, boot = None,
                 extraargs = None, os_type = None, conn = None):
        Installer.Installer.__init__(self, type, location, boot, extraargs,
                                 os_type, conn=conn)

        # True == location is a filesystem path
        # False == location is a url
        self._location_is_path = True

    # DistroInstaller specific methods/overwrites

    def get_location(self):
        return self._location
    def set_location(self, val):
        """
        Valid values for location:
        1) it can be a local file (ex. boot.iso), directory (ex. distro tree)
           or physical device (ex. cdrom media)
        2) tuple of the form (poolname, volname) pointing to a file or device
           which will set location as that path
        3) http, ftp, or nfs path for an install tree
        """
        is_tuple = False
        validated = True
        self._location_is_path = True
        is_local = (not self.conn or
                    not _util.is_uri_remote(self.conn.getURI()))

        # Basic validation
        if type(val) is not str and (type(val) is not tuple and len(val) != 2):
            raise ValueError(_("Invalid 'location' type %s." % type(val)))

        if type(val) is tuple and len(val) == 2:
            logging.debug("DistroInstaller location is a (poolname, volname)"
                          " tuple")
            if not self.conn:
                raise ValueError(_("'conn' must be specified if 'location' is"
                                   " a storage tuple."))
            is_tuple = True

        elif _is_url(val, is_local):
            val = _sanitize_url(val)
            self._location_is_path = False
            logging.debug("DistroInstaller location is a network source.")

        elif os.path.exists(os.path.abspath(val)) and is_local:
            val = os.path.abspath(val)
            logging.debug("DistroInstaller location is a local "
                          "file/path: %s" % val)

        else:
            # Didn't determine anything about the location
            validated = False

        if self._location_is_path or (validated == False and self.conn and
                                      _util.is_storage_capable(self.conn)):
            # If user passed a storage tuple, OR
            # We couldn't determine the location type and a storage capable
            #   connection was passed:
            # Pass the parameters off to VirtualDisk to validate, and pull
            # out the path
            stuple = (is_tuple and val) or None
            path = (not is_tuple and val) or None

            try:
                d = VirtualDisk(path=path,
                                device=VirtualDisk.DEVICE_CDROM,
                                transient=True,
                                readOnly=True,
                                conn=self.conn,
                                volName=stuple)
                val = d.path
            except Exception, e:
                logging.debug(str(e))
                raise ValueError(_("Checking installer location failed: "
                                   "Could not find media '%s'." % str(val)))
        elif not validated:
            raise ValueError(_("Install media location must be an NFS, HTTP "
                               "or FTP network install source, or an existing "
                               "file/device"))

        if (not self._location_is_path and val.startswith("nfs:") and not
            User.current().has_priv(User.PRIV_NFS_MOUNT,
                                    (self.conn and self.conn.getURI()))):
            raise ValueError(_('Privilege is required for NFS installations'))

        self._location = val
    location = property(get_location, set_location)


    # Private helper methods

    def _prepare_cdrom(self, guest, meter):
        if not self._location_is_path:
            # Xen needs a boot.iso if its a http://, ftp://, or nfs: url
            (store_ignore, os_type_ignore, os_variant_ignore, media) = \
             OSDistro.acquireBootDisk(guest, self.location, meter,
                                      self.scratchdir)
            cdrom = media

            self._tmpfiles.append(cdrom)
        else:
            cdrom = self.location

        disk = VirtualDisk(path=cdrom,
                           conn=guest.conn,
                           device=VirtualDisk.DEVICE_CDROM,
                           readOnly=True,
                           transient=True)
        self.install_devices.append(disk)

    def _perform_initrd_injections(self):
        """
        Insert files into the root directory of the initial ram disk
        """
        logging.debug("Unpacking initrd.")
        initrd = self._install_bootconfig.initrd
        tempdir = tempfile.mkdtemp(dir=self.scratchdir)
        os.chmod(tempdir, 0775)

        gzip_proc = subprocess.Popen(['gzip', '-dc', initrd],
                                     stdout=subprocess.PIPE, stderr=sys.stderr)
        cpio_proc = subprocess.Popen(['cpio', '-i', '-d', '--quiet'],
                                     stdin=gzip_proc.stdout,
                                     stderr=sys.stderr, cwd=tempdir)
        cpio_proc.wait()
        gzip_proc.wait()

        for filename in self._initrd_injections:
            logging.debug("Copying %s to the initrd." % filename)
            shutil.copy(filename, tempdir)

        logging.debug("Repacking the initrd.")
        find_proc = subprocess.Popen(['find', '.', '-print0'],
                                     stdout=subprocess.PIPE,
                                     stderr=sys.stderr, cwd=tempdir)
        cpio_proc = subprocess.Popen(['cpio', '-o', '--null', '-c', '--quiet'],
                                     stdin=find_proc.stdout,
                                     stdout=subprocess.PIPE,
                                     stderr=sys.stderr, cwd=tempdir)
        new_initrd = initrd + '.new'
        f = open(new_initrd, 'w')
        gzip_proc = subprocess.Popen(['gzip'], stdin=cpio_proc.stdout,
                                     stdout=f, stderr=sys.stderr)
        f.close()
        cpio_proc.wait()
        find_proc.wait()
        gzip_proc.wait()
        os.rename(new_initrd, initrd)
        shutil.rmtree(tempdir)

    def _prepare_kernel_and_initrd(self, guest, meter):
        disk = None

        # If installing off a local path, map it through to a virtual CD/disk
        if (self.location is not None and
            self._location_is_path and
            not os.path.isdir(self.location)):
            device = VirtualDisk.DEVICE_DISK
            if guest._lookup_osdict_key('pv_cdrom_install'):
                device = VirtualDisk.DEVICE_CDROM

            disk = VirtualDisk(conn=guest.conn,
                               device=device,
                               path=self.location,
                               readOnly=True,
                               transient=True)

        if self._install_bootconfig.kernel:
            return disk

        # Need to fetch the kernel & initrd from a remote site, or
        # out of a loopback mounted disk image/device
        ignore, os_type, os_variant, media = OSDistro.acquireKernel(guest,
                                                self.location, meter,
                                                self.scratchdir,
                                                self.os_type)
        (kernelfn, initrdfn, args) = media

        if guest.get_os_autodetect():
            if os_type:
                logging.debug("Auto detected OS type as: %s" % os_type)
                guest.os_type = os_type

            if (os_variant and guest.os_type == os_type):
                logging.debug("Auto detected OS variant as: %s" % os_variant)
                guest.os_variant = os_variant

        self._install_bootconfig.kernel = kernelfn
        self._install_bootconfig.initrd = initrdfn
        self._install_bootconfig.kernel_args = args

        self._tmpfiles.append(kernelfn)
        if initrdfn:
            self._tmpfiles.append(initrdfn)

        if self._initrd_injections:
            self._perform_initrd_injections()

        return disk

    def _get_bootdev(self, isinstall, guest):
        if isinstall:
            bootdev = self.bootconfig.BOOT_DEVICE_CDROM
        else:
            bootdev = self.bootconfig.BOOT_DEVICE_HARDDISK
        return bootdev

    # General Installer methods

    def scratchdir_required(self):
        is_url = not self._location_is_path
        mount_dvd = self._location_is_path and not self.cdrom

        return bool(is_url or mount_dvd)

    def prepare(self, guest, meter):
        self.cleanup()

        dev = None
        if self.cdrom:
            if self.location:
                dev = self._prepare_cdrom(guest, meter)
            else:
                # Booting from a cdrom directly allocated to the guest
                pass
        else:
            dev = self._prepare_kernel_and_initrd(guest, meter)

        if dev:
            self.install_devices.append(dev)

    def detect_distro(self):
        try:
            dist_info = OSDistro.detectMediaDistro(location=self.location,
                                                   arch=self.arch)
        except:
            logging.exception("Error attempting to detect distro.")
            return (None, None)

        # detectMediaDistro should only return valid values
        dtype, dvariant = dist_info
        return (dtype, dvariant)
