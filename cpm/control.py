from cpm.transaction import ChangeSet, ChangeSetSplitter, INSTALL, REMOVE
from cpm.repository import createRepository
from cpm.fetcher import Fetcher
from cpm.cache import Cache
from cpm.const import *
from cpm import *
import os

class Control:

    def __init__(self, feedback=None):
        self._conffile = CONFFILE
        self._replst = []
        self._sysconfreplst = []
        if not feedback:
            feedback = ControlFeedback()
        self._feedback = feedback
        self._cache = Cache()
        feedback.cacheCreated(self._cache)
        self._fetcher = Fetcher()
        feedback.fetcherCreated(self._fetcher)

    def setFeedback(self, feedback):
        self._feedback = feedback

    def getFeedback(self, feedback):
        return self._feedback

    def getRepositories(self):
        return self._replst

    def addRepository(self, repos):
        self._replst.append(repos)

    def removeRepository(self, repos):
        if repos in self._sysconfreplst:
            raise Error, "repository is in system configuration"
        self._replst.remove(repos)

    def getCache(self):
        return self._cache

    def getFetcher(self):
        return self._fetcher

    def loadCache(self):
        self._cache.load()

    def reloadCache(self):
        self._cache.reload()

    def loadSysConf(self, conffile=None):
        if conffile:
            conffile = os.path.expanduser(conffile)
            if not os.path.isfile(conffile):
                raise Error, "configuration file not found: %s" % conffile
            sysconf.load(conffile)
        else:
            conffile = os.path.expanduser(CONFFILE)
            if os.path.isfile(conffile):
                sysconf.load(conffile)
        self._conffile = conffile

    def saveSysConf(self, conffile=None):
        if not conffile:
            conffile = self._conffile
        conffile = os.path.expanduser(conffile)
        sysconf.save(conffile)

    def reloadSysConfRepositories(self):
        for repos in self._sysconfreplst:
            self._replst.remove(repos)
            self._cache.removeLoader(repos.getLoader())
        self._replst = [x for x in self._replst
                              if x not in self._sysconfreplst]
        names = {}
        for data in sysconf.get("repositories", ()):
            if data.get("disabled"):
                continue
            type = data.get("type")
            if not type:
                raise Error, "repository without type in configuration"
            repos = createRepository(type, data)
            name = repos.getName()
            if names.get(name):
                raise Error, "'%s' is not a unique repository name" % name
            else:
                names[name] = True
            self._sysconfreplst.append(repos)
            self._replst.append(repos)

    def fetchRepositories(self, replst=None, caching=ALWAYS):
        if not replst:
            self.reloadSysConfRepositories()
            replst = self._replst
        localdir = os.path.join(sysconf.get("data-dir"), "repositories/")
        if not os.path.isdir(localdir):
            os.makedirs(localdir)
        self._fetcher.setLocalDir(localdir, mangle=True)
        self._fetcher.setCaching(caching)
        self._feedback.fetcherStarting(self._fetcher)
        for repos in replst:
            self._cache.removeLoader(repos.getLoader())
            repos.fetch(self._fetcher)
            self._cache.addLoader(repos.getLoader())
        self._feedback.fetcherFinished(self._fetcher)

    def fetchPackages(self, packages, caching=OPTIONAL):
        fetcher = self._fetcher
        fetcher.reset()
        fetcher.setCaching(caching)
        localdir = os.path.join(sysconf.get("data-dir"), "packages/")
        if not os.path.isdir(localdir):
            os.makedirs(localdir)
        self._fetcher.setLocalDir(localdir, mangle=False)
        pkgurl = {}
        for pkg in packages:
            loader = [x for x in pkg.loaderinfo if not x.getInstalled()][0]
            info = loader.getInfo(pkg)
            url = info.getURL()
            pkgurl[pkg] = url
            fetcher.enqueue(url)
            fetcher.setInfo(url, size=info.getSize(), md5=info.getMD5(),
                            sha=info.getSHA())
        self._feedback.fetcherStarting(fetcher)
        fetcher.run("packages")
        self._feedback.fetcherFinished(fetcher)
        failed = fetcher.getFailedSet()
        if failed:
            raise Error, "failed to download packages:\n" + \
                         "\n".join(["    %s: %s" % (url, failed[url])
                                    for url in failed])
        succeeded = self._fetcher.getSucceededSet()
        pkgpath = {}
        for pkg in packages:
            pkgpath[pkg] = succeeded[pkgurl[pkg]]
        return pkgpath

    def fetchFiles(self, urllst, what, caching=NEVER):
        localdir = os.path.join(sysconf.get("data-dir"), "tmp/")
        if not os.path.isdir(localdir):
            os.makedirs(localdir)
        fetcher = self._fetcher
        fetcher.setLocalDir(localdir, mangle=True)
        fetcher.setCaching(caching)
        for url in urllst:
            fetcher.enqueue(url)
        self._feedback.fetcherStarting(fetcher)
        fetcher.run(what)
        self._feedback.fetcherFinished(fetcher)
        return fetcher.getSucceededSet(), fetcher.getFailedSet()

    def commitTransaction(self, trans, caching=OPTIONAL):
        self.commitChangeSet(trans.getChangeSet(), caching)

    def commitChangeSet(self, changeset, caching=OPTIONAL):
        pkgpath = self.fetchPackages([pkg for pkg in changeset
                                      if changeset[pkg] is INSTALL],
                                     caching)
        pmpkgs = {}
        for pkg in changeset:
            pmclass = pkg.packagemanager
            if pmclass not in pmpkgs:
                pmpkgs[pmclass] = [pkg]
            else:
                pmpkgs[pmclass].append(pkg)
        for pmclass in pmpkgs:
            pm = pmclass()
            self._feedback.packageManagerCreated(pm)
            pminstall = [pkg for pkg in pmpkgs[pmclass]
                         if changeset[pkg] is INSTALL]
            pmremove  = [pkg for pkg in pmpkgs[pmclass]
                         if changeset[pkg] is REMOVE]
            self._feedback.packageManagerStarting(pm)
            pm.commit(pminstall, pmremove, pkgpath)
            self._feedback.packageManagerFinished(pm)

    def commitTransactionStepped(self, trans, caching=OPTIONAL):
        self.commitChangeSetStepped(trans.getChangeSet(), caching)

    def commitChangeSetStepped(self, changeset, caching=OPTIONAL):

        # Order by number of required packages inside the transaction.
        pkglst = []
        for pkg in changeset:
            n = 0
            for req in pkg.requires:
                for prv in req.providedby:
                    for prvpkg in prv.packages:
                        if changeset.get(prvpkg) is INSTALL:
                            n += 1
            pkglst.append((n, pkg))

        pkglst.sort()

        splitter = ChangeSetSplitter(changeset)
        unioncs = ChangeSet()
        for n, pkg in pkglst:
            if pkg in unioncs:
                continue
            cs = ChangeSet(unioncs)
            splitter.include(unioncs, pkg)
            cs = unioncs.difference(cs)
            self.commitChangeSet(cs)

class ControlFeedback:

    def cacheCreated(self, cache):
        pass

    def fetcherCreated(self, fetcher):
        pass

    def fetcherStarting(self, fetcher):
        pass

    def fetcherFinished(self, fetcher):
        pass

    def packageManagerCreated(self, pm):
        pass

    def packageManagerStarting(self, pm):
        pass

    def packageManagerFinished(self, pm):
        pass

# vim:ts=4:sw=4:et
