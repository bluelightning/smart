from cpm.transaction import Transaction, PolicyInstall, FIX
from cpm.cmdline import initCmdLine, confirmChanges
from cpm.matcher import MasterMatcher
from cpm.option import OptionParser
from cpm import *
import string
import re

USAGE="cpm fix [options] packages"

def parse_options(argv):
    parser = OptionParser(usage=USAGE)
    opts, args = parser.parse_args(argv)
    opts.args = args
    return opts

def main(opts):
    ctrl = initCmdLine(opts)
    ctrl.fetchRepositories()
    ctrl.loadCache()
    cache = ctrl.getCache()
    trans = Transaction(cache, PolicyInstall)
    pkgs = cache.getPackages()
    if opts.args:
        newpkgs = []
        for arg in opts.args:
            matcher = MasterMatcher(arg)
            fpkgs = matcher.filter(pkgs)
            if not fpkgs:
                raise Error, "'%s' matches no packages" % arg
            newpkgs.extend(fpkgs)
        pkgs = dict.fromkeys(newpkgs).keys()
    for pkg in pkgs:
        trans.enqueue(pkg, FIX)
    print "Resolving problems..."
    trans.run()
    if not trans:
        print "No problems to resolve!"
    elif confirmChanges(trans):
        ctrl.commitTransaction(trans)

# vim:ts=4:sw=4:et