#!/usr/bin/env python3

import sys
from .core import Core

def run() -> int:
    # args
    try:
        core = Core()
    except Core.InitError as e:
        print(f"Init error {e.__class__}")
        return -1

    core.run()
    return 0

if __name__ == '__main__':
    sys.exit(run())
