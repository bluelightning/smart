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
from smart.transaction import Transaction, PolicyUpgrade, \
                              UPGRADE, INSTALL, REMOVE
from smart.option import OptionParser
from smart.cache import Package
from smart import *
import cPickle
import string
import re
import os

USAGE=_("smart upgrade [options] [package] ...")

DESCRIPTION=_("""
This command will upgrade one or more packages which
are currently installed in the system. If no packages
are given, all installed packages will be checked.

If pkgname is prefixed by a '+', it will be installed
even if it was not currently installed in the system.
If pkgname is prefixed with a '-', it will be removed.
""")

EXAMPLES=_("""
smart upgrade
smart upgrade pkgname
smart upgrade '*kgnam*'
smart upgrade pkgname-1.0
smart upgrade pkgname-1.0-1
smart upgrade pkgname1 pkgname2
""")

def option_parser():
    parser = OptionParser(usage=USAGE,
                          description=DESCRIPTION,
                          examples=EXAMPLES)
    parser.allow_interspersed_args = False
    parser.add_option("--stepped", action="store_true",
                      help=_("split operation in steps"))
    parser.add_option("--urls", action="store_true",
                      help=_("dump needed urls and don't commit operation"))
    parser.add_option("--metalink", action="store_true",
                      help=_("dump metalink xml and don't commit operation"))
    parser.add_option("--download", action="store_true",
                      help=_("download packages and don't commit operation"))
    parser.add_option("--update", action="store_true",
                      help=_("update channel information before trying "
                             "to upgrade"))
    parser.add_option("--check", action="store_true",
                      help=_("just check if there are upgrades to be done"))
    parser.add_option("--check-update", action="store_true",
                      help=_("check if there are upgrades to be done, and "
                             "update the known upgrades"))
    parser.add_option("--explain", action="store_true",
                      help=_("include additional information about changes,"
                             "when possible"))
    parser.add_option("--flag", action="store", default=None,
                      help=_("check only upgrades with the given flag set"))
    parser.add_option("-y", "--yes", action="store_true",
                      help=_("do not ask for confirmation"))
    parser.add_option("--dump", action="store_true",
                      help=_("dump package names and versions to stderr but "
                             "don't commit operation"))
    return parser

def parse_options(argv):
    parser = option_parser()
    opts, args = parser.parse_args(argv)
    opts.args = args
    return opts

def main(ctrl, opts):

    if opts.explain:
        sysconf.set("explain-changesets", True, soft=True)

    if opts.update or sysconf.get("auto-update"):
        from smart.commands import update
        updateopts = update.parse_options([])
        update.main(ctrl, updateopts)
    else:
        ctrl.reloadChannels()

    cache = ctrl.getCache()
    trans = Transaction(cache, PolicyUpgrade)

    if opts.args:

        for arg in opts.args:

            op = UPGRADE
            if arg.startswith('+'):
                arg = arg[1:]
                op = INSTALL
            if arg.startswith('-'):
                arg = arg[1:]
                op = REMOVE

            ratio, results, suggestions = ctrl.search(arg)

            if not results:
                if suggestions:
                    dct = {}
                    for r, obj in suggestions:
                        if isinstance(obj, Package):
                            if obj.installed or op == INSTALL:
                                dct[obj] = True
                        else:
                            for pkg in obj.packages:
                                if pkg.installed or op == INSTALL:
                                    dct[pkg] = True
                    if not dct:
                        del suggestions[:]
                if suggestions:
                    raise Error, _("'%s' matches no packages. "
                                   "Suggestions:\n%s") % \
                                 (arg, "\n".join(["    "+str(x) for x in dct]))
                else:
                    raise Error, _("'%s' matches no packages") % arg

            foundany = False
            foundinstalled = False
            for obj in results:
                if isinstance(obj, Package):
                    if (obj.installed or op == INSTALL) and (not opts.flag or pkgconf.testFlag(opts.flag, obj)):
                        trans.enqueue(obj, op)
                        foundinstalled = obj.installed
                    foundany = True
            if not foundany:
                for obj in results:
                    if not isinstance(obj, Package):
                        for pkg in obj.packages:
                            if (pkg.installed or op == INSTALL) and (not opts.flag or pkgconf.testFlag(opts.flag, pkg)):
                                foundinstalled = pkg.installed
                                trans.enqueue(pkg, op)
                            foundany = True
            if not foundinstalled and op != INSTALL:
                iface.warning(_("'%s' matches no installed packages") % arg)
    else:
        for pkg in cache.getPackages():
            if pkg.installed and (not opts.flag or pkgconf.testFlag(opts.flag, pkg)):
                trans.enqueue(pkg, UPGRADE)

    iface.showStatus(_("Computing transaction..."))
    trans.run()

    if trans and opts.check or opts.check_update:
        checkfile = os.path.expanduser("~/.smart/upgradecheck")
        if os.path.isfile(checkfile):
            file = open(checkfile)
            checkstate = cPickle.load(file)
            file.close()
        else:
            checkstate = None
        changeset = trans.getChangeSet()
        state = changeset.getPersistentState()
        if opts.check_update:
            dirname = os.path.dirname(checkfile)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            file = open(checkfile, "w")
            cPickle.dump(state, file, 2)
            file.close()
        if not state:
            iface.showStatus(_("No interesting upgrades available."))
            return 2
        elif checkstate:
            for entry in state:
                if checkstate.get(entry) != state[entry]:
                    break
            else:
                iface.showStatus(_("There are pending upgrades!"))
                return 1
        iface.showStatus(_("There are new upgrades available!"))
    elif not trans:
        iface.showStatus(_("No interesting upgrades available."))
    else:
        iface.hideStatus()
        confirm = not opts.yes
        if opts.urls:
            ctrl.dumpTransactionURLs(trans)
        elif opts.metalink:
            ctrl.dumpTransactionMetalink(trans)
        elif opts.dump:
            ctrl.dumpTransactionPackages(trans, install=True)
        elif opts.download:
            ctrl.downloadTransaction(trans, confirm=confirm)
        elif opts.stepped:
            ctrl.commitTransactionStepped(trans, confirm=confirm)
        else:
            ctrl.commitTransaction(trans, confirm=confirm)

# vim:ts=4:sw=4:et
