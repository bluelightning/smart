from cpm.const import DEBUG, INFO, WARNING, ERROR, CONFFILE
from cpm.control import Control, ControlFeedback
from cpm.progress import RPMStyleProgress
from cpm.sysconfig import SysConfig
from cpm.report import Report
from cpm.log import Logger
import os

class CommandLineFeedback(ControlFeedback):

    def __init__(self):
        self._progress = RPMStyleProgress()

    def fetcherCreated(self, fetcher):
        fetcher.setProgress(self._progress)

    def cacheCreated(self, cache):
        cache.setProgress(self._progress)

    def packageManagerCreated(self, pm):
        pm.setProgress(self._progress)

    def packageManagerStarting(self, fetcher):
        print

    def packageManagerFinished(self, fetcher):
        print

def initCmdLine(opts=None):
    sysconf = SysConfig()
    if opts and opts.log_level:
        level = {"error": ERROR, "warning": WARNING,
                 "debug": DEBUG, "info": INFO}.get(opts.log_level)
        if level is None:
            raise Error, "unknown log level"
        sysconf.set("log-level", level)
    from cpm import init
    init(sysconf, Logger())
    ctrl = Control(CommandLineFeedback())
    ctrl.loadSysConf(opts and opts.config_file)
    return ctrl

def confirmChanges(trans):
    report = Report(trans.getCache(), trans.getChangeSet())
    report.compute()

    print
    if report.upgrading or report.installing:
        pkgs = report.upgrading.keys()+report.installing.keys()
        pkgs.sort()
        print "The following packages are being installed:"
        for pkg in pkgs:
            print "   ", pkg
            for upgpkg in report.upgrading.get(pkg, ()):
                print "       Upgrades:", upgpkg
        print
    if report.upgraded or report.removed:
        print "The following packages are being removed:"
        pkgs = report.upgraded.keys()+report.removed.keys()
        pkgs.sort()
        for pkg in pkgs:
            print "   ", pkg
            for upgpkg in report.upgraded.get(pkg, ()):
                print "       Upgraded by:", upgpkg

        print
    res = raw_input("Confirm changes (y/N)? ").strip()
    if res and res[0].lower() == "y":
        return True
    return False

# vim:ts=4:sw=4:et
