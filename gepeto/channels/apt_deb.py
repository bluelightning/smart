#
# Copyright (c) 2004 Conectiva, Inc.
#
# Written by Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of Gepeto.
#
# Gepeto is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Gepeto is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gepeto; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from gepeto.backends.deb.loader import DebTagFileLoader
from gepeto.backends.deb import DEBARCH
from gepeto.channel import Channel, ChannelDataError
from gepeto.util.strtools import strToBool
from gepeto.const import SUCCEEDED, FAILED, NEVER
from gepeto.cache import LoaderSet
from gepeto import *
import posixpath
import tempfile
import commands
import os

class APTDEBChannel(Channel):

    def __init__(self, baseurl, distro, comps, fingerprint, *args):
        Channel.__init__(self, *args)
        
        self._baseurl = baseurl
        self._distro = distro
        self._comps = comps
        if fingerprint:
            self._fingerprint = "".join([x for x in fingerprint
                                         if not x.isspace()])
        else:
            self._fingerprint = None

        self._loader = LoaderSet()

    def _getURL(self, filename="", component=None, subpath=False):
        if subpath:
            distrourl = ""
        else:
            distrourl = posixpath.join(self._baseurl, "dists", self._distro)
        if component:
            return posixpath.join(distrourl, component,
                                  "binary-"+DEBARCH, filename)
        else:
            return posixpath.join(distrourl, filename)

    def getCacheCompareURLs(self):
        return [self._getURL("Release")]

    def getFetchSteps(self):
        # Release files are not being used
        #return len(self._comps)*2+2
        return len(self._comps)+2

    def fetch(self, fetcher, progress):

        fetcher.reset()

        # Fetch release file
        item = fetcher.enqueue(self._getURL("Release"))
        gpgitem = fetcher.enqueue(self._getURL("Release.gpg"))
        fetcher.run(progress=progress)
        failed = item.getFailedReason()
        if failed:
            if fetcher.getCaching() is NEVER:
                iface.warning("Failed acquiring release file for '%s':" % self)
                iface.warning("%s: %s" % (item.getURL(), failed))
            progress.add(self.getFetchSteps()-2)
            progress.show()
            return

        # Parse release file
        md5sum = {}
        insidemd5sum = False
        for line in open(item.getTargetPath()):
            if not insidemd5sum:
                if line.startswith("MD5Sum:"):
                    insidemd5sum = True
            elif not line.startswith(" "):
                insidemd5sum = False
            else:
                try:
                    md5, size, path = line.split()
                except ValueError:
                    pass
                else:
                    md5sum[path] = (md5, int(size))

        if self._fingerprint:
            try:
                failed = gpgitem.getFailedReason()
                if failed:
                    raise Error, "Channel '%s' has fingerprint but download " \
                                 "of Release.gpg failed: %s" % (self, failed)

                status, output = commands.getstatusoutput(
                    "gpg --batch --no-secmem-warning --status-fd 1 "
                    "--verify %s %s" % (gpgitem.getTargetPath(),
                                        item.getTargetPath()))

                badsig = False
                goodsig = False
                validsig = None
                for line in output.splitlines():
                    if line.startswith("[GNUPG:]"):
                        tokens = line[8:].split()
                        first = tokens[0]
                        if first == "VALIDSIG":
                            validsig = tokens[1]
                        elif first == "GOODSIG":
                            goodsig = True
                        elif first == "BADSIG":
                            badsig = True
                if badsig:
                    raise Error, "Channel '%s' has bad signature" % self
                if not goodsig or validsig != self._fingerprint:
                    raise Error, "Channel '%s' signed with unknown key" % self
            except Error, e:
                progress.add(self.getFetchSteps()-2)
                progress.show()
                raise

        # Fetch component package lists and release files
        fetcher.reset()
        pkgitems = []
        #relitems = []
        for comp in self._comps:
            packages = self._getURL("Packages", comp, subpath=True)
            url = self._getURL("Packages", comp)
            if packages+".bz2" in md5sum:
                upackages = packages
                packages += ".bz2"
                url += ".bz2"
            elif packages+".gz" in md5sum:
                upackages = packages
                packages += ".gz"
                url += ".gz"
            elif packages not in md5sum:
                iface.warning("Component '%s' is not in Release file" % comp)
                continue
            else:
                upackages = None
            info = {"component": comp, "uncomp": True}
            info["md5"], info["size"] = md5sum[packages]
            if upackages:
                info["uncomp_md5"], info["uncomp_size"] = md5sum[upackages]
            pkgitems.append(fetcher.enqueue(url, **info))

            #release = self._getURL("Release", comp, subpath=True)
            #if release in md5sum:
            #    url = self._getURL("Release", comp)
            #    info = {"component": comp}
            #    info["md5"], info["size"] = md5sum[release]
            #    relitems.append(fetcher.enqueue(url, **info))
            #else:
            #    progress.add(1)
            #    progress.show()
            #    relitems.append(None)

        fetcher.run(progress=progress)

        firstfailure = True
        for i in range(len(pkgitems)):
            pkgitem = pkgitems[i]
            #relitem = relitems[i]
            if pkgitem.getStatus() == SUCCEEDED:
                # Release files for components are not being used.
                #if relitem and relitem.getStatus() == SUCCEEDED:
                #    try:
                #        for line in open(relitem.getTargetPath()):
                #            if line.startswith("..."):
                #                pass
                #    except (IOError, ValueError):
                #        pass
                localpath = pkgitem.getTargetPath()
                loader = DebTagFileLoader(localpath, self._baseurl)
                loader.setChannel(self)
                self._loader.append(loader)
            else:
                if firstfailure:
                    firstfailure = False
                    iface.warning("Failed acquiring information for '%s':" %
                                  self)
                iface.warning("%s: %s" %
                              (pkgitem.getURL(), pkgitem.getFailedReason()))

def create(type, alias, data):
    name = None
    description = None
    priority = 0
    manual = False
    removable = False
    baseurl = None
    distro = None
    comps = None
    fingerprint = None
    if isinstance(data, dict):
        name = data.get("name")
        description = data.get("description")
        baseurl = data.get("baseurl")
        distro = data.get("distribution")
        comps = (data.get("components") or "").split()
        priority = data.get("priority", 0)
        manual = strToBool(data.get("manual", False))
        removable = strToBool(data.get("removable", False))
        fingerprint = data.get("fingerprint")
    elif getattr(data, "tag", None) == "channel":
        for n in data.getchildren():
            if n.tag == "name":
                name = n.text
            elif n.tag == "description":
                description = n.text
            elif n.tag == "priority":
                priority = n.text
            elif n.tag == "manual":
                manual = strToBool(n.text)
            elif n.tag == "removable":
                removable = strToBool(n.text)
            elif n.tag == "baseurl":
                baseurl = n.text
            elif n.tag == "distribution":
                distro = n.text
            elif n.tag == "components":
                comps = n.text.split()
    else:
        raise ChannelDataError
    if not baseurl:
        raise Error, "Channel '%s' has no baseurl" % alias
    if not distro:
        raise Error, "Channel '%s' has no distribution" % alias
    if not comps:
        raise Error, "Channel '%s' has no components" % alias
    try:
        priority = int(priority)
    except ValueError:
        raise Error, "Invalid priority"
    return APTDEBChannel(baseurl, distro, comps, fingerprint,
                         type, alias, name, description,
                         priority, manual, removable)

# vim:ts=4:sw=4:et
