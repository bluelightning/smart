from cpm.option import OptionParser
from cpm.control import Control
from cpm.cmdline import initCmdLine
from cpm.const import NEVER
from cpm import *
import string
import re

USAGE="cpm update [options]"

def parse_options(argv):
    parser = OptionParser(usage=USAGE)
    opts, args = parser.parse_args(argv)
    opts.args = args
    return opts

def main(opts):
    ctrl = Control(opts)
    initCmdLine(ctrl)
    ctrl.update()
    ctrl.standardFinalize()

# vim:ts=4:sw=4:et