#
# Copyright 2008-2009  Red Hat, Inc.
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
from virtinst import _virtinst as _

class VirtualAudio(VirtualDevice.VirtualDevice):

    _virtual_device_type = VirtualDevice.VirtualDevice.VIRTUAL_DEV_AUDIO

    MODEL_DEFAULT = "default"
    MODELS = [ "es1370", "sb16", "pcspk", "ac97", MODEL_DEFAULT ]

    def __init__(self, model=None, conn=None):
        VirtualDevice.VirtualDevice.__init__(self, conn)

        self._model = None

        if model == None:
            model = self.MODEL_DEFAULT
        self.model = model

    def get_model(self):
        return self._model
    def set_model(self, new_model):
        if type(new_model) != str:
            raise ValueError, _("'model' must be a string, "
                                " was '%s'." % type(new_model))
        if not self.MODELS.count(new_model):
            raise ValueError, _("Unsupported sound model '%s'" % new_model)
        self._model = new_model
    model = property(get_model, set_model)

    def get_xml_config(self):
        model = self.model
        if model == self.MODEL_DEFAULT:
            model = "es1370"

        return "    <sound model='%s'/>" % model
