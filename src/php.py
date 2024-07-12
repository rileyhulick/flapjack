import os, os.path, glob
import re
import shutil, subprocess
from collections import defaultdict, OrderedDict
from .core import Core
from .utils import sbin_which, get_prefixed_dir

# TODO currently PHP is supported via fpm/fcgi but we could reasonably support
# other pathways such as cgi or PHP's built-in web server

def parse_ver(ver: str | None) -> tuple:
    if not ver:
        return None

    r = re.compile(r'^(?:php\s*)?(\d+)(?:\.(\d+)(?:\.(\d+))?)?', re.I)
    m = r.match(ver)
    if not m:
        return None

    vmin = 0
    vrev = 0
    try:
        vmaj = int(m.group(1))
        vmin = int(m.group(2))
        vrev = int(m.group(3))
    except IndexError:
        pass
    except ValueError:
        return None

    return (vmaj, vmin, vrev,)

class Php:
    def __init__(self, core: Core):
        self._core = core

        # Look for all distinct PHP interpreters on PATH

        breadcrumbs = set()
        php_execs = []
        for path in os.getenv('PATH', os.defpath).split(os.pathsep):
            for maybe_exec in glob.iglob(os.path.join(path, './php*')):
                if not re.match(r'php(?:\d+(?:\.\d+)?)?$', os.path.basename(maybe_exec)):
                    continue
                if not os.access(maybe_exec, os.X_OK):
                    continue
                exec_r = os.path.realpath(maybe_exec)
                if exec_r in breadcrumbs:
                    continue
                breadcrumbs.add(exec_r)

                v_proc = subprocess.run([ maybe_exec, '-v' ], encoding='utf-8', capture_output=True)
                exec_version = parse_ver(v_proc.stdout)
                if not exec_version:
                    continue

                php_execs.append((maybe_exec, exec_version,))

        del breadcrumbs

        # Identify the one which reports the highest version that meets our
        # requirements

        php_execs.sort(key=lambda x: x[1], reverse=True)
        for maybe_exec, exec_version in php_execs:
            try:
                if exec_version < parse_ver(self._core.config.get('php_min_version')):
                    continue
            except TypeError:
                pass
            try:
                if exec_version > parse_ver(self._core.config.get('php_max_version')):
                    continue
            except TypeError:
                pass

            self._php_exec_name = maybe_exec
            self._php_version = exec_version

        try:
            self._php_exec_name
            self._php_version
        except AttributeError:
            assert False # TODO

        # Locate its corresponding fpm binary

        self._php_fpm_exec_name = sbin_which(f"php-fpm{self._php_version[0]}.{self._php_version[1]}")
        assert self._php_fpm_exec_name

        # and INI directory

        self._ini_dir = get_prefixed_dir(self._php_exec_name, f"./etc/php/{self._php_version[0]}.{self._php_version[1]}")
        assert self._ini_dir # TODO

        self._update_config()

    def _update_config(self):

        if 'php_mods_enabled' not in self._core.config:
            # If flapjack hasn't been configured to use a particular set of PHP
            # mods then use all mods available from the system installation

            mods_available = defaultdict(list)
            for ini in glob.iglob(os.path.join(self._ini_dir, './mods-available/*.ini')):
                priority = -1
                extensions = []

                with open(ini, 'r') as f:
                    for line in f:
                        try:
                            s = re.search(r'^(?:zend_)?extension=(\w+)(?:\.so|\.dll)?', line, re.M)
                            extensions.append(( s.group(1), s.group(0), ))
                            continue
                        except AttributeError:
                            pass

                        try:
                            priority = int(re.search(r'^;\s*priority=(\d+)', line, re.M).group(1))
                            continue
                        except AttributeError:
                            pass
                        except ValueError:
                            pass

                if not extensions:
                    continue

                mods_available[priority].extend(extensions)

            self._core.config['php_mods_enabled'] = OrderedDict()
            for priority in sorted(mods_available.keys()):
                for mod, line, in sorted(mods_available[priority]):
                    if self._core.config.get('php_no_mod_' + mod, False):
                        continue
                    self._core.config['php_mods_enabled'][mod] = line

        else:
            # FIXME
            pass

    @property
    def config_files(self):
        return {
                'php_conf': 'php.ini.in',
                'php_fpm_conf': 'php-fpm.conf.in'
            }

    @property
    def daemon_command(self):
        return self._php_fpm_exec_name, [ '-c', self._core.config['php_conf'], '--fpm-config', self._core.config['php_fpm_conf'] ]

    @property
    def client_commands(self):
        return {
            'php': (self._php_exec_name, [ '-c', self._core.config['php_conf'] ],)
        }

    @property
    def exec_env(self):
        return {
                'PHP_INI_SCAN_DIR': 'Off'
            }

    # @property
    # def system_config_dirs(self):
    #     return { 'system_php_fpm_conf_dir': './etc/php/8.3/fpm' }
