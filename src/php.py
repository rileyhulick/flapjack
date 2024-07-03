import os, os.path, glob, re
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

    def validate_config(self):
        # probably a better way to do this would be to locate the native PHP
        # config directory and parse its contents

        # CAUTION the order of extensions makes a difference.

        possible_extensions = [
                'calendar.so',
                'ctype.so',
                'curl.so',
                'dom.so',
                'exif.so',
                'ffi.so',
                'fileinfo.so',
                'ftp.so',
                'gd.so',
                'gettext.so',
                'gmp.so',
                'iconv.so',
                'intl.so',
                'mbstring.so',
                'mysqlnd.so',
                'mysqli.so',
                'pdo.so',
                'pdo_mysql.so',
                'phar.so',
                'posix.so',
                'readline.so',
                'shmop.so',
                'simplexml.so',
                'sockets.so',
                'sysvmsg.so',
                'sysvsem.so',
                'sysvshm.so',
                'tokenizer.so',
                'xml.so',
                'xmlreader.so',
                'xmlwriter.so',
                'xsl.so',
            ]

        extensions = []
        lib_path = os.path.join(os.path.dirname(self.exec_name), '../lib/php')
        if os.path.isdir(lib_path):
            found_extensions = set([ os.path.basename(file_) for file_ in glob.iglob(os.path.join(lib_path, '**/*.so'), recursive=True) ])
            assert 'mysqlnd.so' in found_extensions # TODO

            extensions = [ ext for ext in possible_extensions if ext in found_extensions ]

        self._core.config['php_extensions'] = extensions


    # @property
    # def system_config_dirs(self):
    #     return { 'system_php_fpm_conf_dir': './etc/php/8.3/fpm' }
