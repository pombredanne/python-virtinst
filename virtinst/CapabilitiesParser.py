#
# Some code for parsing libvirt's capabilities XML
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

from virtinst import _virtinst as _
import _util

class CapabilitiesParserException(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

# Whether a guest can be created with a certain feature on resp. off
FEATURE_ON      = 0x01
FEATURE_OFF     = 0x02

class Features(object):
    """Represent a set of features. For each feature, store a bit mask of
       FEATURE_ON and FEATURE_OFF to indicate whether the feature can
       be turned on or off. For features for which toggling doesn't make sense
       (e.g., 'vmx') store FEATURE_ON when the feature is present."""

    def __init__(self, node = None):
        self.features = {}
        if node is not None:
            self.parseXML(node)

    def __getitem__(self, feature):
        if self.features.has_key(feature):
            return self.features[feature]
        return 0

    def names(self):
        return self.features.keys()

    def parseXML(self, node):
        d = self.features

        feature_list = []
        if node.name == "features":
            node_list = node.xpathEval("*")
            for n in node_list:
                feature_list.append(n.name)
        else:
            # New style features
            node_list = node.xpathEval("feature/@name")
            for n in node_list:
                feature_list.append(n.content)

        for feature in feature_list:
            if not d.has_key(feature):
                d[feature] = 0

            self._extractFeature(feature, d, n)

    def _extractFeature(self, feature, d, node):
        """Extract the value of FEATURE from NODE and set DICT[FEATURE] to
        its value. Abstract method, must be overridden"""
        raise NotImplementedError("Abstract base class")

class CapabilityFeatures(Features):
    def __init__(self, node = None):
        Features.__init__(self, node)

    def _extractFeature(self, feature, d, n):
        default = xpathString(n, "@default")
        toggle = xpathString(n, "@toggle")

        if default is not None:
            # Format for guest features
            if default == "on":
                d[feature] = FEATURE_ON
            elif default == "off":
                d[feature] = FEATURE_OFF
            else:
                raise CapabilitiesParserException("Feature %s: value of default must be 'on' or 'off', but is '%s'" % (feature, default))
            if toggle == "yes":
                d[feature] |= d[feature] ^ (FEATURE_ON|FEATURE_OFF)
        else:
            # Format for old HOST features, on OLD old guest features
            # back compat is just <$featurename>, like <svm/>
            if feature == "nonpae":
                d["pae"] |= FEATURE_OFF
            else:
                d[feature] |= FEATURE_ON

class CPU(object):
    def __init__(self, node=None):
        # e.g. "i686" or "x86_64"
        self.arch = None
        self.model = None
        self.sockets = 1
        self.cores = 1
        self.threads = 1
        self.features = CapabilityFeatures()

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        newstyle_features = False

        child = node.children
        while child:
            # Do a first pass to try and detect new style features
            if child.name == "feature":
                newstyle_features = True
                break
            child = child.next

        if newstyle_features:
            self.features = CapabilityFeatures(node)

        child = node.children
        while child:
            if child.name == "arch":
                self.arch = child.content
            elif child.name == "model":
                self.model = child.content
            elif child.name == "topology":
                self.sockets = xpathString(child, "@sockets") or 1
                self.cores = xpathString(child, "@cores") or 1
                self.threads = xpathString(child, "@threads") or 1

            elif child.name == "features" and not newstyle_features:
                self.features = CapabilityFeatures(child)

            child = child.next

class Host(object):
    def __init__(self, node = None):
        self.cpu = CPU()
        self.topology = None
        self.secmodel = None

        if not node is None:
            self.parseXML(node)

    # Back compat for CPU class
    def get_arch(self):
        return self.cpu.arch
    def set_arch(self, val):
        self.cpu.arch = val
    arch = property(get_arch, set_arch)

    def get_features(self):
        return self.cpu.features
    def set_features(self, val):
        self.cpu.features = val
    features = property(get_features, set_features)

    def parseXML(self, node):
        child = node.children
        while child:
            if child.name == "topology":
                self.topology = Topology(child)

            if child.name == "secmodel":
                self.secmodel = SecurityModel(child)

            if child.name == "cpu":
                self.cpu = CPU(child)

            child = child.next


class Guest(object):
    def __init__(self, node = None):
        # e.g. "xen" or "hvm"
        self.os_type = None
        # e.g. "i686" or "x86_64"
        self.arch = None

        self.domains = []

        self.features = CapabilityFeatures()

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        child = node.children
        while child:
            if child.name == "os_type":
                self.os_type = child.content
            elif child.name == "features":
                self.features = CapabilityFeatures(child)
            elif child.name == "arch":
                self.arch = child.prop("name")
                machines = []
                emulator = None
                loader = None
                n = child.children
                while n:
                    if n.name == "machine":
                        machines.append(n.content)
                    elif n.name == "emulator":
                        emulator = n.content
                    elif n.name == "loader":
                        loader = n.content
                    n = n.next

                n = child.children
                while n:
                    if n.name == "domain":
                        self.domains.append(Domain(n.prop("type"), emulator, loader, machines, n))
                    n = n.next

            child = child.next


    def bestDomainType(self, accelerated=None):
        if len(self.domains) == 0:
            raise CapabilitiesParserException(_("No domains available for "
                                                "virt type '%(type)s', arch "
                                                "%(arch)s.") % \
                                                {'type': self.os_type,
                                                 'arch': self.arch})
        if accelerated is None:
            # Picking last in list so we favour KVM/KQEMU over QEMU
            return self.domains[-1]
        else:
            priority = ["openvz", "kvm", "xen", "kqemu", "qemu"]
            if not accelerated:
                priority.reverse()

            for t in priority:
                for d in self.domains:
                    if d.hypervisor_type == t:
                        return d

            # Fallback, just return last item in list
            return self.domains[-1]


class Domain(object):
    def __init__(self, hypervisor_type, emulator = None, loader = None, machines = None, node = None):
        self.hypervisor_type = hypervisor_type
        self.emulator = emulator
        self.loader = loader
        self.machines = machines

        if node is not None:
            self.parseXML(node)


    def parseXML(self, node):
        child = node.children
        machines = []
        while child:
            if child.name == "emulator":
                self.emulator = child.content
            elif child.name == "machine":
                machines.append(child.content)
            child = child.next

        if len(machines) > 0:
            self.machines = machines

class Topology(object):
    def __init__(self, node = None):
        self.cells = []

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        child = node.children
        if child.name == "cells":
            for cell in child.children:
                if cell.name == "cell":
                    self.cells.append(TopologyCell(cell))

class TopologyCell(object):
    def __init__(self, node = None):
        self.id = None
        self.cpus = []

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        self.id = int(node.prop("id"))
        child = node.children
        if child.name == "cpus":
            for cpu in child.children:
                if cpu.name == "cpu":
                    self.cpus.append(TopologyCPU(cpu))

class TopologyCPU(object):
    def __init__(self, node = None):
        self.id = None

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        self.id = int(node.prop("id"))


class SecurityModel(object):
    def __init__(self, node = None):
        self.model = None
        self.doi = None

        if not node is None:
            self.parseXML(node)

    def parseXML(self, node):
        for child in node.children or []:
            if child.name == "model":
                self.model = child.content
            elif child.name == "doi":
                self.doi = child.content

class Capabilities(object):
    def __init__(self, node = None):
        self.host = None
        self.guests = []
        self._topology = None

        if not node is None:
            self.parseXML(node)


        self._fixBrokenEmulator()

    def _is_xen(self):
        for g in self.guests:
            if g.os_type != "xen":
                continue

            for d in g.domains:
                if d.hypervisor_type == "xen":
                    return True

        return False

    def no_install_options(self):
        """
        Return True if there are no install options available
        """
        for g in self.guests:
            if len(g.domains) > 0:
                return False

        return True

    def hw_virt_supported(self):
        """
        Return True if the machine supports hardware virtualization.

        For some cases (like qemu caps pre libvirt 0.7.4) this info isn't
        sufficiently provided, so we will return True in cases that we
        aren't sure.
        """
        # Obvious case of feature being specified
        if (self.host.features["vmx"] == FEATURE_ON or
            self.host.features["svm"] == FEATURE_ON):
            return True

        # If there is other features, but no virt bit, then HW virt
        # isn't supported
        if len(self.host.features.names()):
            return False

        # Xen caps have always shown this info, so if we didn't find any
        # features, the host really doesn't have the necc support
        if self._is_xen():
            return False

        # Otherwise, we can't be sure, because there was a period for along
        # time that qemu caps gave no indication one way or the other.
        return True

    def is_kvm_available(self):
        """
        Return True if kvm guests can be installed
        """
        for g in self.guests:
            if g.os_type != "hvm":
                continue

            for d in g.domains:
                if d.hypervisor_type == "kvm":
                    return True

        return False

    def is_xenner_available(self):
        """
        Return True if xenner install option is available
        """
        for g in self.guests:
            if g.os_type != "xen":
                continue

            for d in g.domains:
                if d.hypervisor_type == "kvm":
                    return True

        return False

    def is_bios_virt_disabled(self):
        """
        Try to determine if fullvirt may be disabled in the bios.

        Check is basically:
        - We support HW virt
        - We appear to be xen
        - There are no HVM install options

        We don't do this check for KVM, since no KVM options may mean
        KVM isn't installed or the module isn't loaded (and loading the
        module will give an appropriate error
        """
        if not self.hw_virt_supported():
            return False

        if not self._is_xen():
            return False

        for g in self.guests:
            if g.os_type == "hvm":
                return False

        return True

    def guestForOSType(self, type = None, arch = None):
        if self.host is None:
            return None

        if arch is None:
            archs = [self.host.arch, None]
        else:
            archs = [arch]
        for a in archs:
            for g in self.guests:
                if (type is None or g.os_type == type) and \
                   (a is None or g.arch == a):
                    return g

    # 32-bit HVM emulator path, on a 64-bit host is wrong due
    # to bug in libvirt capabilities. We fix by copying the
    # 64-bit emualtor path
    def _fixBrokenEmulator(self):
        if self.host.arch != "x86_64":
            return

        fixEmulator = None
        for g in self.guests:
            if g.os_type != "hvm" or g.arch != "x86_64":
                continue
            for d in g.domains:
                if d.emulator is not None and d.emulator.find("lib64") != -1:
                    fixEmulator = d.emulator

        if not fixEmulator:
            return

        for g in self.guests:
            if g.os_type != "hvm" or g.arch != "i686":
                continue
            for d in g.domains:
                if d.emulator is not None and d.emulator.find("lib64") == -1:
                    d.emulator = fixEmulator

    def parseXML(self, node):
        child = node.children
        while child:
            if child.name == "host":
                self.host = Host(child)
            elif child.name == "guest":
                self.guests.append(Guest(child))
            if child.name == "topology":
                self._topology = Topology(child)
            child = child.next

        # Libvirt < 0.4.1 placed topology info at the capabilities level
        # rather than the host level. This is just for back compat
        if self.host.topology is None:
            self.host.topology = self._topology

def parse(xml):
    return _util.parse_node_helper(xml, "capabilities",
                                   Capabilities,
                                   CapabilitiesParserException)

def guest_lookup(conn, caps=None, os_type=None, arch=None, type=None,
                 accelerated=False):
    """
    Simple virtualization availability lookup

    Convenience function for looking up 'Guest' and 'Domain' capabilities
    objects for the desired virt type. If type, arch, or os_type are none,
    we return the default virt type associated with those values. These are
    typically:

    - os_type    : hvm, then xen
    - type : kvm over plain qemu
    - arch    : host arch over all others

    Otherwise the default will be the first listed in the capabilities xml.
    This function throws C{ValueError}s if any of the requested values are
    not found.

    @param conn: virConnect instance
    @type conn: libvirt.virConnect
    @param caps: Optional L{Capabilities} instance (saves a lookup)
    @type conn: L{Capabilities}
    @param type: Virtualization type ('hvm', 'xen', ...)
    @type type: C{str}
    @param arch: Guest architecture ('x86_64', 'i686' ...)
    @type arch: C{str}
    @param os_type: Hypervisor name ('qemu', 'kvm', 'xen', ...)
    @type os_type: C{str}
    @param accelerated: Whether to look for accelerated domain if none is
                        specifically requested
    @type accelerated: C{bool}

    @returns: A (Capabilities Guest, Capabilities Domain) tuple
    """

    if not caps:
        caps = parse(conn.getCapabilities())

    guest = caps.guestForOSType(type=os_type, arch=arch)
    if not guest:
        archstr = _("for arch '%s'") % arch
        if not arch:
            archstr = ""

        osstr = _("virtualization type '%s'") % os_type
        if not os_type:
            osstr = _("any virtualization options")

        raise ValueError(_("Host does not support %(virttype)s %(arch)s") %
                           {'virttype' : osstr, 'arch' : archstr})

    domain = None
    if type:
        for d in guest.domains:
            if d.hypervisor_type == type.lower():
                domain = d
                break
    else:
        domain = guest.bestDomainType(accelerated=accelerated)

    if domain == None:
        raise ValueError(_("Host does not support domain type "
                           "'%(domain)s' for virtualization type "
                           "'%(virttype)s' arch '%(arch)s'") %
                           {'domain': type, 'virttype': guest.os_type,
                            'arch': guest.arch})

    return (guest, domain)


def xpathString(node, path, default = None):
    result = node.xpathEval("string(%s)" % path)
    if len(result) == 0:
        result = default
    return result
