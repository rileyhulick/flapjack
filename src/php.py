import os, os.path, glob
from .core import Core

# TODO currently PHP is supported via fpm/fcgi but we could reasonably support
# other pathways such as cgi or PHP's built-in web server

# TODO PHP distributions are highly version-oriented as well. we should support
# configuration options to fine-tune behavior when multiple versions are
# available

class Php:
    def __init__(self, core: Core):
        self._core = core

    @property
    def config_files(self):
        return {
                'php_conf': 'php.ini.in',
                'php_fpm_conf': 'php-fpm.conf.in'
            }

    @property
    def exec_name(self):
        try:
            return self._exec_name
        except AttributeError:
            searchpaths = os.getenv('PATH', os.defpath).split(os.pathsep) + ['/sbin', '/usr/sbin']
            for searchpath in searchpaths:
                for path in glob.iglob(os.path.join(searchpath, 'php-fpm*')):
                    self._exec_name = path
                    return self._exec_name

    @property
    def exec_args(self):
        return [
                '-c', self._core.config['php_conf'],
                '--fpm-config', self._core.config['php_fpm_conf']
            ]

    @property
    def exec_env(self):
        return {
                'PHP_INI_SCAN_DIR': 'Off'
            }

    # @property
    # def system_config_dirs(self):
    #     return { 'system_php_fpm_conf_dir': './etc/php/8.3/fpm' }
