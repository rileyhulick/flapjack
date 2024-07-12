import json, os
from time import sleep

class Session:
    class LockError(Exception): pass

    def __init__(self, lockfile_name : str | None):
        self._lockfile_name = lockfile_name
        self._lockfile = None

        # self._config_file = None
        # self._work_dir = None
        # self._run_dir  = None
        # self._temp_dir = None
        self._pid  = None
        self._is_new = False
        # self._port = None

    def __enter__(self):
        self._in_context = True

    def __exit__(self, exc_type, exc_value, traceback):
        del self._in_context
        if self._lockfile:
            self._lockfile.close()

            if self._is_new:
                os.remove(self._lockfile_name)

    def lock_new(self):
        assert self._in_context

        if not self._lockfile_name:
            return

        self._is_new = True
        try:
            self._lockfile = open(self._lockfile_name, 'x')
        except FileExistsError:
            # TODO try to diagnose stale lock?

            self._is_new = False
            raise Session.LockError

    def lock_existing(self):
        assert self._in_context

        if not self._lockfile_name:
            return

        self._is_new = False
        try:
            self._lockfile = open(self._lockfile_name, 'r')
        except FileNotFoundError:
            raise Session.LockError

    def soft_unlock(self):
        assert self._in_context

        if not self._lockfile_name or not self._lockfile:
            return

        self._lockfile.close()
        self._lockfile = None

    @property
    def lockfile_name(self):
        return self._lockfile_name

    @property
    def pid(self):
        if self._is_new:
            return os.getpid()

        if not self._pid:
            self._read()
        return self._pid

    def _read(self):
        assert not self._is_new
        assert self._lockfile_name

        retry = 5
        found = False
        while retry > 0:
            try:
                self._lockfile = open(self._lockfile_name, 'r')
                j = json.load(self._lockfile)
                found = True
            except FileNotFoundError:
                pass
            except json.JSONDecodeError:
                pass

            sleep(0.100)
            retry -= 1

        if not found:
            raise Session.LockError

        # self._config_file = j.get('config_file')
        # self._work_dir = j.get('work_dir')
        # self._run_dir  = j.get('run_dir')
        # self._temp_dir = j.get('temp_dir')
        self._pid  = j.get('pid')
        # self._port = j.get('port')

    def write(self):
        assert self._is_new

        if not self._pid:
            self._pid = os.getpid()

        j = { 'pid': self._pid }
        json.dump(j, self._lockfile)
        self._lockfile.flush()



