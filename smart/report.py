#
# Copyright (c) 2004 Conectiva, Inc.
#
# Written by Gustavo Niemeyer <niemeyer@conectiva.com>
#
# This file is part of Smart Package Manager.
#
# Smart Package Manager is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# Smart Package Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Smart Package Manager; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from smart.const import INSTALL, REMOVE

class Report(object):

    def __init__(self, changeset):
        self._changeset = changeset

        self.exclude = {}

        self.install = {}
        self.remove = {}

        self.removed = {}
        self.upgraded = {}
        self.downgraded = {}

        self.installing = {}
        self.upgrading = {}
        self.downgrading = {}

        self.notupgraded = {}

        self.conflicts = {}
        self.requires = {}
        self.requiredby = {}

    def reset(self):
        self.exclude.clear()
        self.install.clear()
        self.remove.clear()
        self.removed.clear()
        self.upgraded.clear()
        self.downgraded.clear()
        self.installing.clear()
        self.upgrading.clear()
        self.downgrading.clear()
        self.notupgraded.clear()
        self.conflicts.clear()
        self.requires.clear()
        self.requiredby.clear()

    def compute(self):
        changeset = self._changeset
        for pkg in changeset.getCache().getPackages():
            if pkg in self.exclude:
                continue
            if changeset.get(pkg) is REMOVE:
                self.remove[pkg] = True
                for prv in pkg.provides:
                    for upg in prv.upgradedby:
                        for upgpkg in upg.packages:
                            if changeset.get(upgpkg) is INSTALL:
                                if pkg in self.upgraded:
                                    self.upgraded[pkg].append(upgpkg)
                                else:
                                    self.upgraded[pkg] = [upgpkg]
                for upg in pkg.upgrades:
                    for prv in upg.providedby:
                        for prvpkg in prv.packages:
                            if changeset.get(prvpkg) is INSTALL:
                                if pkg in self.downgraded:
                                    self.downgraded[pkg].append(prvpkg)
                                else:
                                    self.downgraded[pkg] = [prvpkg]
                if (pkg not in self.upgraded and
                    pkg not in self.downgraded):
                    self.removed[pkg] = True
            elif changeset.get(pkg) is INSTALL:
                self.install[pkg] = True
                for upg in pkg.upgrades:
                    for prv in upg.providedby:
                        for prvpkg in prv.packages:
                            if prvpkg.installed:
                                if pkg in self.upgrading:
                                    self.upgrading[pkg].append(prvpkg)
                                else:
                                    self.upgrading[pkg] = [prvpkg]
                for prv in pkg.provides:
                    for upg in prv.upgradedby:
                        for upgpkg in upg.packages:
                            if upgpkg.installed:
                                if pkg in self.downgrading:
                                    self.downgrading[pkg].append(upgpkg)
                                else:
                                    self.downgrading[pkg] = [upgpkg]
                if (pkg not in self.upgrading and
                    pkg not in self.downgrading):
                    self.installing[pkg] = True
            elif pkg.installed:
                notupgraded = {}
                try:
                    for prv in pkg.provides:
                        for upg in prv.upgradedby:
                            for upgpkg in upg.packages:
                                if changeset.get(upgpkg) is INSTALL:
                                    raise StopIteration
                                else:
                                    notupgraded[upgpkg] = True
                except StopIteration:
                    pass
                else:
                    if notupgraded:
                        self.notupgraded[pkg] = notupgraded.keys()

            pkgop = changeset.get(pkg)
            if pkgop:
                map = {}
                for cnf in pkg.conflicts:
                    for prv in cnf.providedby:
                        for prvpkg in prv.packages:
                            if changeset.get(prvpkg):
                                map[prvpkg] = True
                for prv in pkg.provides:
                    for cnf in prv.conflictedby:
                        for cnfpkg in cnf.packages:
                            if changeset.get(cnfpkg):
                                map[cnfpkg] = True
                if map:
                    self.conflicts[pkg] = map.keys()
                    map.clear()
                for req in pkg.requires:
                    for prv in req.providedby:
                        for prvpkg in prv.packages:
                            if changeset.get(prvpkg) is pkgop:
                                map[prvpkg] = True
                if map:
                    self.requires[pkg] = map.keys()
                    map.clear()
                for prv in pkg.provides:
                    for req in prv.requiredby:
                        for reqpkg in req.packages:
                            if changeset.get(reqpkg) is pkgop:
                                map[reqpkg] = True
                if map:
                    self.requiredby[pkg] = map.keys()

# vim:ts=4:sw=4:et