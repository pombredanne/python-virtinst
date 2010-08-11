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

import unittest
import os
import libvirt
import urlgrabber.progress as progress

import virtinst
from virtinst import VirtualDisk
from virtinst import VirtualAudio
from virtinst import VirtualNetworkInterface
from virtinst import VirtualHostDeviceUSB, VirtualHostDevicePCI
from virtinst import VirtualCharDevice
from virtinst import VirtualVideoDevice
from virtinst import VirtualController
from virtinst import VirtualWatchdog
from virtinst import VirtualInputDevice
import tests

conn = tests.open_testdriver()
scratch = os.path.join(os.getcwd(), "tests", "testscratchdir")

def get_basic_paravirt_guest(testconn=conn, installer=None):
    g = virtinst.ParaVirtGuest(connection=testconn, type="xen")
    g.name = "TestGuest"
    g.memory = int(200)
    g.maxmemory = int(400)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    g.boot = ["/boot/vmlinuz","/boot/initrd"]
    g.graphics = (True, "vnc", None, "ja")
    g.vcpus = 5

    if installer:
        g.installer = installer

    g.installer._scratchdir = scratch
    return g

def get_basic_fullyvirt_guest(typ="xen", testconn=conn, installer=None):
    g = virtinst.FullVirtGuest(connection=testconn, type=typ,
                               emulator="/usr/lib/xen/bin/qemu-dm",
                               arch="i686")
    g.name = "TestGuest"
    g.memory = int(200)
    g.maxmemory = int(400)
    g.uuid = "12345678-1234-1234-1234-123456789012"
    g.cdrom = "/dev/loop0"
    g.graphics = (True, "sdl")
    g.features['pae'] = 0
    g.vcpus = 5
    if installer:
        g.installer = installer

    g.installer._scratchdir = scratch
    return g

def make_import_installer():
    inst = virtinst.ImportInstaller(type="xen", os_type="hvm", conn=conn)
    return inst

def make_distro_installer(location="/default-pool/default-vol", gtype="xen"):
    inst = virtinst.DistroInstaller(type=gtype, os_type="hvm", conn=conn,
                                    location=location)
    return inst

def make_live_installer(location="/dev/loop0", gtype="xen"):
    inst = virtinst.LiveCDInstaller(type=gtype, os_type="hvm",
                                    conn=conn, location=location)
    return inst

def make_pxe_installer(gtype="xen"):
    inst = virtinst.PXEInstaller(type=gtype, os_type="hvm", conn=conn)
    return inst

def build_win_kvm(path=None):
    g = get_basic_fullyvirt_guest("kvm")
    g.os_type = "windows"
    g.os_variant = "winxp"
    g.disks.append(get_filedisk(path))
    g.disks.append(get_blkdisk())
    g.nics.append(get_virtual_network())
    g.add_device(VirtualAudio())
    g.add_device(VirtualVideoDevice(g.conn))

    return g

def get_floppy(path = None):
    if not path:
        path = "/default-pool/testvol1.img"
    return VirtualDisk(path, conn=conn, device=VirtualDisk.DEVICE_FLOPPY)

def get_filedisk(path = None):
    if not path:
        path = "/tmp/test.img"
    return VirtualDisk(path, size=.0001, conn=conn)

def get_blkdisk():
    return VirtualDisk("/dev/loop0", conn=conn)

def get_virtual_network():
    dev = virtinst.VirtualNetworkInterface()
    dev.macaddr = "11:22:33:44:55:66"
    dev.type = virtinst.VirtualNetworkInterface.TYPE_VIRTUAL
    dev.network = "default"
    return dev

def qemu_uri():
    return "qemu:///system"

def xen_uri():
    return "xen:///"

def build_xmlfile(filebase):
    if not filebase:
        return None
    return os.path.join("tests/xmlconfig-xml", filebase + ".xml")

def sanitize_xml(xml):
    # Libvirt throws errors since we are defining domain
    # type='xen', when test driver can only handle type='test'
    # Sanitize the XML so we can define
    if not xml:
        return xml

    xml = xml.replace("<domain type='xen'>",
                      "<domain type='test'>")
    xml = xml.replace(">linux<", ">xen<")

    return xml

class TestXMLConfig(unittest.TestCase):

    def tearDown(self):
        if os.path.exists(scratch):
            os.rmdir(scratch)

    def _compare(self, guest, filebase, do_install, do_disk_boot=False):
        filename = build_xmlfile(filebase)

        guest._prepare_install(progress.BaseMeter())
        try:
            actualXML = guest.get_config_xml(install=do_install,
                                             disk_boot=do_disk_boot)

            tests.diff_compare(actualXML, filename)
            self._testCreate(guest.conn, actualXML)
        finally:
            guest._cleanup_install()

    def _testCreate(self, testconn, xml):
        xml = sanitize_xml(xml)

        dom = testconn.defineXML(xml)
        try:
            dom.create()
            dom.destroy()
            dom.undefine()
        except:
            try:
                dom.destroy()
            except:
                pass
            try:
                dom.undefine()
            except:
                pass

    def _testInstall(self, guest,
                     instxml=None, bootxml=None, contxml=None):
        instname = build_xmlfile(instxml)
        bootname = build_xmlfile(bootxml)
        contname = build_xmlfile(contxml)
        consolecb = None
        meter = None
        removeOld = None
        wait = True
        dom = None

        old_getxml = guest.get_config_xml
        def new_getxml(install=True, disk_boot=False):
            xml = old_getxml(install, disk_boot)
            return sanitize_xml(xml)
        guest.get_config_xml = new_getxml

        try:
            dom = guest.start_install(consolecb, meter, removeOld, wait)
            dom.destroy()

            # Replace kernel/initrd with known info
            if (guest.installer._install_bootconfig and
                guest.installer._install_bootconfig.kernel):
                guest.installer._install_bootconfig.kernel = "kernel"
                guest.installer._install_bootconfig.initrd = "initrd"

            xmlinst = guest.get_config_xml(True, False)
            xmlboot = guest.get_config_xml(False, False)
            xmlcont = guest.get_config_xml(True, True)

            if instname:
                tests.diff_compare(xmlinst, instname)
            if contname:
                tests.diff_compare(xmlcont, contname)
            if bootname:
                tests.diff_compare(xmlboot, bootname)

            if guest.get_continue_inst():
                guest.continue_install(consolecb, meter, wait)

        finally:
            if dom:
                try:
                    dom.destroy()
                except:
                    pass
                try:
                    dom.undefine()
                except:
                    pass


    def conn_function_wrappers(self, guest, funcargs,
                               func=None,
                               conn_version=None,
                               conn_uri=None,
                               libvirt_version=None):
        testconn = guest.conn

        def set_func(newfunc, funcname, obj, force=False):
            if newfunc or force:
                orig = None
                if hasattr(obj, funcname):
                    orig = getattr(obj, funcname)

                setattr(obj, funcname, newfunc)
                return orig, True

            return None, False

        def set_version(newfunc, force=False):
            return set_func(newfunc, "getVersion", testconn, force)
        def set_uri(newfunc, force=False):
            return set_func(newfunc, "getURI", testconn, force)
        def set_libvirt_version(newfunc, force=False):
            return set_func(newfunc, "getVersion", libvirt, force)

        old_version = None
        old_uri = None
        old_libvirt_version = None
        try:
            old_version = set_version(conn_version)
            old_uri = set_uri(conn_uri)
            old_libvirt_version = set_libvirt_version(libvirt_version)

            if not func:
                func = self._compare
            func(*funcargs)
        finally:
            set_version(*old_version)
            set_uri(*old_uri)
            set_libvirt_version(*old_libvirt_version)

    def testBootParavirtDiskFile(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "boot-paravirt-disk-file", False)

    def testBootParavirtDiskFileBlktapCapable(self):
        oldblktap = virtinst._util.is_blktap_capable
        try:
            virtinst._util.is_blktap_capable = lambda: True
            g = get_basic_paravirt_guest()
            g.disks.append(get_filedisk())
            self._compare(g, "boot-paravirt-disk-drv-tap", False)
        finally:
            virtinst._util.is_blktap_capable = oldblktap

    def testBootParavirtDiskBlock(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "boot-paravirt-disk-block", False)

    def testBootParavirtDiskDrvPhy(self):
        g = get_basic_paravirt_guest()
        disk = get_blkdisk()
        disk.driver_name = VirtualDisk.DRIVER_PHY
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-phy", False)

    def testBootParavirtDiskDrvFile(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_FILE
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-file", False)

    def testBootParavirtDiskDrvTap(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-tap", False)

    def testBootParavirtDiskDrvTapQCow(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW
        g.disks.append(disk)
        self._compare(g, "boot-paravirt-disk-drv-tap-qcow", False)

    def testBootParavirtManyDisks(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk("/tmp/test2.img")
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW

        g.disks.append(get_filedisk("/tmp/test1.img"))
        g.disks.append(disk)
        g.disks.append(get_blkdisk())
        self._compare(g, "boot-paravirt-many-disks", False)

    def testBootFullyvirtDiskFile(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "boot-fullyvirt-disk-file", False)

    def testBootFullyvirtDiskBlock(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "boot-fullyvirt-disk-block", False)



    def testInstallParavirtDiskFile(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "install-paravirt-disk-file", True)

    def testInstallParavirtDiskBlock(self):
        g = get_basic_paravirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "install-paravirt-disk-block", True)

    def testInstallParavirtDiskDrvPhy(self):
        g = get_basic_paravirt_guest()
        disk = get_blkdisk()
        disk.driver_name = VirtualDisk.DRIVER_PHY
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-phy", True)

    def testInstallParavirtDiskDrvFile(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_FILE
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-file", True)

    def testInstallParavirtDiskDrvTap(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-tap", True)

    def testInstallParavirtDiskDrvTapQCow(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk()
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW
        g.disks.append(disk)
        self._compare(g, "install-paravirt-disk-drv-tap-qcow", True)

    def testInstallParavirtManyDisks(self):
        g = get_basic_paravirt_guest()
        disk = get_filedisk("/tmp/test2.img")
        disk.driver_name = VirtualDisk.DRIVER_TAP
        disk.driver_type = VirtualDisk.DRIVER_TAP_QCOW

        g.disks.append(get_filedisk("/tmp/test1.img"))
        g.disks.append(disk)
        g.disks.append(get_blkdisk())
        self._compare(g, "install-paravirt-many-disks", True)

    def testInstallFullyvirtDiskFile(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-disk-file", True)

    def testInstallFullyvirtDiskBlock(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_blkdisk())
        self._compare(g, "install-fullyvirt-disk-block", True)

    def testInstallFVPXE(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-pxe", True)

    def testBootFVPXE(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        g.disks.append(get_filedisk())
        self._compare(g, "boot-fullyvirt-pxe", False)

    def testBootFVPXEAlways(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        g.disks.append(get_filedisk())

        g.installer.bootconfig.bootorder = [
            g.installer.bootconfig.BOOT_DEVICE_NETWORK]
        g.installer.bootconfig.enable_bootmenu = True

        self._compare(g, "boot-fullyvirt-pxe-always", False)

    def testInstallFVPXENoDisks(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "install-fullyvirt-pxe-nodisks", True)

    def testBootFVPXENoDisks(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "boot-fullyvirt-pxe-nodisks", False)

    def testInstallFVLiveCD(self):
        i = make_live_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "install-fullyvirt-livecd", False)

    def testDoubleInstall(self):
        # Make sure that installing twice generates the same XML, to ensure
        # we aren't polluting the device list during the install process
        i = make_live_installer()
        g = get_basic_fullyvirt_guest(installer=i)
        self._compare(g, "install-fullyvirt-livecd", False)
        self._compare(g, "install-fullyvirt-livecd", False)

    def testDefaultDeviceRemoval(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())

        inp = VirtualInputDevice(g.conn)
        cons = VirtualCharDevice.get_dev_instance(conn,
                                VirtualCharDevice.DEV_CONSOLE,
                                VirtualCharDevice.CHAR_PTY)
        g.add_device(inp)
        g.add_device(cons)

        g.remove_device(inp)
        g.remove_device(cons)

        self._compare(g, "boot-default-device-removal", False)

    def testOSDeviceDefaultChange(self):
        """
        Make sure device defaults are properly changed if we change OS
        distro/variant mid process
        """
        i = make_distro_installer(gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)

        do_install = False
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())

        # Call get_config_xml to set first round of defaults without an
        # os_variant set
        fargs = (do_install,)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri,
                                    func=g.get_config_xml)

        g.os_variant = "fedora11"
        fargs = (g, "install-f11", do_install)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testInstallFVImport(self):
        i = make_import_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-import", False)

    def testInstallFVImportKernel(self):
        i = make_import_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.disks.append(get_filedisk())
        g.installer.bootconfig.kernel = "kernel"
        g.installer.bootconfig.initrd = "initrd"
        g.installer.bootconfig.kernel_args = "my kernel args"

        self._compare(g, "install-fullyvirt-import-kernel", False)

    def testInstallFVImportMulti(self):
        i = make_import_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.installer.bootconfig.enable_bootmenu = False
        g.installer.bootconfig.bootorder = ["hd", "fd", "cdrom", "network"]
        g.disks.append(get_filedisk())
        self._compare(g, "install-fullyvirt-import-multiboot", False)

    def testInstallPVImport(self):
        i = make_import_installer()
        g = get_basic_paravirt_guest(installer=i)

        g.disks.append(get_filedisk())
        self._compare(g, "install-paravirt-import", False)

    def testQEMUDriverName(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_blkdisk())
        fargs = (g, "misc-qemu-driver-name", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk())
        fargs = (g, "misc-qemu-driver-type", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk("/default-pool/iso-vol"))
        fargs = (g, "misc-qemu-iso-disk", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk("/default-pool/iso-vol"))
        g.disks[0].driver_type = "qcow2"
        fargs = (g, "misc-qemu-driver-overwrite", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testXMLEscaping(self):
        g = get_basic_fullyvirt_guest()
        g.disks.append(get_filedisk("/tmp/ISO&'&s"))
        self._compare(g, "misc-xml-escaping", True)

    # OS Type/Version configurations
    def testF10(self):
        i = make_pxe_installer(gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora10"
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f10", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testF11(self):
        i = make_distro_installer(gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f11", False)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testF11AC97(self):
        def build_guest():
            i = make_distro_installer(gtype="kvm")
            g = get_basic_fullyvirt_guest("kvm", installer=i)

            g.os_type = "linux"
            g.os_variant = "fedora11"
            g.installer.cdrom = True
            g.disks.append(get_floppy())
            g.disks.append(get_filedisk())
            g.disks.append(get_blkdisk())
            g.nics.append(get_virtual_network())
            g.add_device(VirtualAudio())
            return g

        def libvirt_nosupport_ac97(drv=None):
            libver = 5000
            if drv:
                return (libver, libver)
            return libver

        def conn_nosupport_ac97():
            return 10000

        def conn_support_ac97():
            return 11000

        g = build_guest()
        fargs = (g, "install-f11-ac97", False)
        self.conn_function_wrappers(g, fargs,
                                    conn_uri=qemu_uri,
                                    conn_version=conn_support_ac97)

        g = build_guest()
        fargs = (g, "install-f11-noac97", False)
        self.conn_function_wrappers(g, fargs,
                                    libvirt_version=libvirt_nosupport_ac97,
                                    conn_uri=qemu_uri)

        g = build_guest()
        fargs = (g, "install-f11-noac97", False)
        self.conn_function_wrappers(g, fargs,
                                    conn_version=conn_nosupport_ac97,
                                    conn_uri=qemu_uri)


    def testF11Qemu(self):
        i = make_distro_installer(gtype="qemu")
        g = get_basic_fullyvirt_guest("qemu", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f11-qemu", False)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testF11Xen(self):
        i = make_distro_installer(gtype="xen")
        g = get_basic_fullyvirt_guest("xen", installer=i)

        g.os_type = "linux"
        g.os_variant = "fedora11"
        g.installer.cdrom = True
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        fargs = (g, "install-f11-xen", False)
        self.conn_function_wrappers(g, fargs, conn_uri=xen_uri)

    def testInstallWindowsKVM(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage1", True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testContinueWindowsKVM(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage2", True, True)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)

    def testBootWindowsKVM(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage3", False)
        self.conn_function_wrappers(g, fargs, conn_uri=qemu_uri)


    def testInstallWindowsXenNew(self):
        def old_xen_ver():
            return 3000001

        def new_xen_ver():
            return 3100000


        g = get_basic_fullyvirt_guest("xen")
        g.os_type = "windows"
        g.os_variant = "winxp"
        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        g.add_device(VirtualAudio())

        for f, xml in [(old_xen_ver, "install-windowsxp-xenold"),
                       (new_xen_ver, "install-windowsxp-xennew")]:

            fargs = (g, xml, True)
            self.conn_function_wrappers(g, fargs,
                                        conn_version=f, conn_uri=xen_uri)


    # Device heavy configurations
    def testManyDisks2(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.disks.append(get_filedisk())
        g.disks.append(get_blkdisk())
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_CDROM))
        g.disks.append(VirtualDisk(conn=g.conn, path=None,
                                   device=VirtualDisk.DEVICE_CDROM,
                                   bus="scsi"))
        g.disks.append(VirtualDisk(conn=g.conn, path=None,
                                   device=VirtualDisk.DEVICE_FLOPPY))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_FLOPPY))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   bus="virtio"))

        self._compare(g, "boot-many-disks2", False)

    def testManyNICs(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        net1 = VirtualNetworkInterface(type="user",
                                       macaddr="11:11:11:11:11:11")
        net2 = get_virtual_network()
        net3 = get_virtual_network()
        net3.model = "e1000"
        net4 = VirtualNetworkInterface(bridge="foobr0",
                                       macaddr="22:22:22:22:22:22")

        g.nics.append(net1)
        g.nics.append(net2)
        g.nics.append(net3)
        g.nics.append(net4)
        self._compare(g, "boot-many-nics", False)

    def testManyHostdevs(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        dev1 = VirtualHostDeviceUSB(g.conn)
        dev1.product = "0x1234"
        dev1.vendor = "0x4321"

        dev2 = VirtualHostDevicePCI(g.conn)
        dev2.bus = "0x11"
        dev2.slot = "0x22"
        dev2.function = "0x33"

        g.hostdevs.append(dev1)
        g.hostdevs.append(dev2)
        self._compare(g, "boot-many-hostdevs", False)

    def testManySounds(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.sound_devs.append(VirtualAudio("sb16", conn=g.conn))
        g.sound_devs.append(VirtualAudio("es1370", conn=g.conn))
        g.sound_devs.append(VirtualAudio("pcspk", conn=g.conn))
        g.sound_devs.append(VirtualAudio(conn=g.conn))

        self._compare(g, "boot-many-sounds", False)

    def testManyChars(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        dev1 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_SERIAL,
                                                  VirtualCharDevice.CHAR_NULL)
        dev2 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_PARALLEL,
                                                  VirtualCharDevice.CHAR_UNIX)
        dev2.source_path = "/tmp/foobar"
        dev3 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_SERIAL,
                                                  VirtualCharDevice.CHAR_TCP)
        dev3.protocol = "telnet"
        dev3.source_host = "my.source.host"
        dev3.source_port = "1234"
        dev4 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_PARALLEL,
                                                  VirtualCharDevice.CHAR_UDP)
        dev4.bind_host = "my.bind.host"
        dev4.bind_port = "1111"
        dev4.source_host = "my.source.host"
        dev4.source_port = "2222"

        dev5 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_CHANNEL,
                                                  VirtualCharDevice.CHAR_PTY)
        dev5.target_type = dev5.CHAR_CHANNEL_TARGET_VIRTIO
        dev5.target_name = "foo.bar.frob"

        dev6 = VirtualCharDevice.get_dev_instance(g.conn,
                                                  VirtualCharDevice.DEV_CONSOLE,
                                                  VirtualCharDevice.CHAR_PTY)
        dev6.target_type = dev5.CHAR_CONSOLE_TARGET_VIRTIO

        g.add_device(dev1)
        g.add_device(dev2)
        g.add_device(dev3)
        g.add_device(dev4)
        g.add_device(dev5)
        g.add_device(dev6)
        self._compare(g, "boot-many-chars", False)

    def testManyDevices(self):
        i = make_pxe_installer()
        g = get_basic_fullyvirt_guest(installer=i)

        g.description = "foooo barrrr \n baz && snarf. '' \"\" @@$\n"

        # Hostdevs
        dev1 = VirtualHostDeviceUSB(g.conn)
        dev1.product = "0x1234"
        dev1.vendor = "0x4321"
        g.hostdevs.append(dev1)

        # Sound devices
        g.sound_devs.append(VirtualAudio("sb16", conn=g.conn))
        g.sound_devs.append(VirtualAudio("es1370", conn=g.conn))

        # Disk devices
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   device=VirtualDisk.DEVICE_FLOPPY))
        g.disks.append(VirtualDisk(conn=g.conn, path="/dev/loop0",
                                   bus="scsi"))
        g.disks.append(VirtualDisk(conn=g.conn, path="/tmp", device="floppy"))
        d3 = VirtualDisk(conn=g.conn, path="/default-pool/testvol1.img",
                         bus="scsi", driverName="qemu")
        g.disks.append(d3)

        # Controller devices
        c1 = VirtualController.get_class_for_type(VirtualController.CONTROLLER_TYPE_IDE)(g.conn)
        c1.index = "3"
        c2 = VirtualController.get_class_for_type(VirtualController.CONTROLLER_TYPE_VIRTIOSERIAL)(g.conn)
        c2.ports = "32"
        c2.vectors = "17"
        g.add_device(c1)
        g.add_device(c2)

        # Network devices
        net1 = get_virtual_network()
        net1.model = "e1000"
        net2 = VirtualNetworkInterface(type="user",
                                       macaddr="11:11:11:11:11:11")
        g.nics.append(net1)
        g.nics.append(net2)

        # Character devices
        cdev1 = VirtualCharDevice.get_dev_instance(g.conn,
                                                   VirtualCharDevice.DEV_SERIAL,
                                                   VirtualCharDevice.CHAR_NULL)
        cdev2 = VirtualCharDevice.get_dev_instance(g.conn,
                                                   VirtualCharDevice.DEV_PARALLEL,
                                                   VirtualCharDevice.CHAR_UNIX)
        cdev2.source_path = "/tmp/foobar"
        g.add_device(cdev1)
        g.add_device(cdev2)

        # Video Devices
        vdev1 = VirtualVideoDevice(g.conn)
        vdev1.model_type = "vmvga"

        vdev2 = VirtualVideoDevice(g.conn)
        vdev2.model_type = "cirrus"
        vdev2.vram = 10 * 1024
        vdev2.heads = 3

        vdev3 = VirtualVideoDevice(g.conn)
        g.add_device(vdev1)
        g.add_device(vdev2)
        g.add_device(vdev3)

        wdev2 = VirtualWatchdog(g.conn)
        wdev2.model = "ib700"
        wdev2.action = "none"
        g.add_device(wdev2)

        g.clock.offset = "localtime"

        seclabel = virtinst.Seclabel(g.conn)
        seclabel.type = seclabel.SECLABEL_TYPE_STATIC
        seclabel.model = "selinux"
        seclabel.label = "foolabel"
        seclabel.imagelabel = "imagelabel"
        g.seclabel = seclabel

        self._compare(g, "boot-many-devices", False)

    def testCpuset(self):
        testconn = libvirt.open("test:///default")
        g = get_basic_fullyvirt_guest(testconn=testconn)

        # Cpuset
        cpustr = g.generate_cpuset(g.conn, g.memory)
        g.cpuset = cpustr

        self._compare(g, "boot-cpuset", False)


    #
    # Full Install tests: try to mimic virt-install as much as possible
    #

    def testFullKVMRHEL6(self):
        i = make_distro_installer(location="tests/cli-test-xml/fakerhel6tree",
                                  gtype="kvm")
        g = get_basic_fullyvirt_guest("kvm", installer=i)
        g.disks.append(get_floppy())
        g.disks.append(get_filedisk("/default-pool/rhel6.img"))
        g.disks.append(get_blkdisk())
        g.nics.append(get_virtual_network())
        g.add_device(VirtualAudio())
        g.add_device(VirtualVideoDevice(g.conn))
        g.os_autodetect = True

        fargs = (g, "rhel6-kvm-stage1", "rhel6-kvm-stage2")
        self.conn_function_wrappers(g, fargs, func=self._testInstall,
                                    conn_uri=qemu_uri)

    def testFullKVMWinxp(self):
        g = build_win_kvm("/default-pool/winxp.img")
        fargs = (g, "winxp-kvm-stage1", "winxp-kvm-stage3", "winxp-kvm-stage2")
        self.conn_function_wrappers(g, fargs, func=self._testInstall,
                                    conn_uri=qemu_uri)

if __name__ == "__main__":
    unittest.main()
