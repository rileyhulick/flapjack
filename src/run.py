#!/usr/bin/env python3

import argparse, sys, os
from .core import Core

def run() -> int:
    if os.getuid() == 0:
        print('Flapjack should not be run as root/sudo!', file=sys.stderr)
        sys.exit(-1)

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
    g1.add_argument('--write-config', nargs='?', default=False)

    argp.add_argument('--stack', nargs='+')
    argp.add_argument('-P', '--port', '--http-port', type=int)

    argp.add_argument('--data-dir')
    argp.add_argument('--data-port', type=int)

    args = argp.parse_args()
    while True:
        try:
            core = Core(args=args)
            break
        except Core.NoConfigWarning as w:
            print(f"[flapjack] Given work directory {w.work_dir} has no flapjack configuration file.")
            ans = False

            try:
                ans = input('[flapjack] Do you wish to run Flapjack here? [y/n]').lower().startswith('y')
            except KeyboardInterrupt:
                print(flush=True)
                pass

            if ans:
                args.force = True
                continue
            else:
                return -2

        except Core.InitError as e:
            print(f"Init error {e.__class__}")
            return -1

    core.run()
    return 0

if __name__ == '__main__':
    sys.exit(run())
