#!/usr/bin/python
from cpm.option import OptionParser
from cpm import *
import logging
import sys

VERSION = "0.0.1"

HELP = """\
Usage: cpm command [options] [arguments]

Available commands:
    query

Run "cpm command --help" for more information.
"""

def parse_options(argv):
    parser = OptionParser(help=HELP, version=VERSION)
    parser.disable_interspersed_args()
    parser.add_option("-c", dest="conffile", metavar="FILE",
                      help="configuration file (default is "
                           "~/.cpm/config or /etc/cpm.conf)")
    parser.add_option("--log", dest="loglevel", metavar="LEVEL",
                      help="set logging level to LEVEL (debug, info, "
                           "warning, error)", default="warning")
    opts, args = parser.parse_args()
    logger.setLevel(logging.getLevelName(opts.loglevel.upper()))
    if len(args) < 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    opts.command = args[0]
    opts.argv = args[1:]
    return opts

def main(argv):
    opts = parse_options(argv)
    try:
        try:
            cpm_module = __import__("cpm.commands."+opts.command)
            commands_module = getattr(cpm_module, "commands")
            command_module = getattr(commands_module, opts.command)
        except (ImportError, AttributeError):
            if opts.loglevel == "debug":
                import traceback
                traceback.print_exc()
                sys.exit(1)
            raise Error, "invalid command '%s'" % opts.command
        cmdopts = command_module.parse_options(opts.argv)
        opts.__dict__.update(cmdopts.__dict__)
        command_module.main(opts)
    except Error, e:
        if opts.loglevel == "debug":
            import traceback
            traceback.print_exc()
            sys.exit(1)
        sys.stderr.write("error: %s\n" % str(e))
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1:])

# vim:ts=4:sw=4:et