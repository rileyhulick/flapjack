#!/usr/bin/env python3

import argparse, sys, os, asyncio
from .core import Core

if os.getuid() == 0:
    print('Flapjack should not be run as root/sudo!', file=sys.stderr)
    sys.exit(-1)

def run() -> int:
    argp = argparse.ArgumentParser(
            prog='flapjack',
            description='No-fuss web stack for localhost development on Linux'
        )

    argp.add_argument('work_dir', nargs='?')

    argp.add_argument('--work-dir')
    argp.add_argument('--run-dir')
    argp.add_argument('--temp-dir')

    g1 = argp.add_mutually_exclusive_group()
    g1.add_argument('-f', '--force', action='store_true')
    g1.add_argument('-c', '--config-file')
    # g1.add_argument('--write-config', nargs='?', default=False)

    argp.add_argument('--stack', nargs='+')
    argp.add_argument('-P', '--port', '--http-port', type=int)

    argp.add_argument('--data-dir')
    argp.add_argument('--data-port', type=int)

    g2 = argp.add_mutually_exclusive_group()
    g2.add_argument('-d', '--daemonize', action='store_true')
    # g2.add_argument('--restart-daemon', action='store_true')
    g2.add_argument('--stop-daemon', action='store_true')
    g2.add_argument('--run', nargs='+')

    try:
        core = Core(args=argp.parse_args())
    except Core.NoConfigWarning as w:
        print(f"[flapjack] Given work directory {w.work_dir} has no flapjack configuration file. (use -c to specify a config file or -f -P or --stack to use this directory anyway)")
        return -1

    except Core.InitError as e:
        print(f"Init error {e.__class__}")
        return -1

    try:
        core.run()
    except KeyboardInterrupt:
        print(flush=True)
        core.stop()

    return 0

if __name__ == '__main__':
    sys.exit(run())
