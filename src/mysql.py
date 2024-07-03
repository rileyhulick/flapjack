import os.path
from .core import Core

# TODO manually disambiguate mysql and mariadb in case the convenient aliases
# are not available or incompatible options are desired?

class Mysql:
    def __init__(self, core: Core):
        self._core = core

    @property
    def config_files(self):
        return { 'mysql_conf': 'mysql.conf.in' }

    @property
    def exec_name(self):
        return 'mysqld'

    @property
    def exec_args(self):
        return [
                '--defaults-file=' + self._core.config['mysql_conf'],
                '--datadir', self._core.config['data_dir'],
                '--socket', os.path.join(self._core.run_dir, 'mysql.sock'),
                '-P', str(self._core.config['data_port']),
            ]

    @property
    def install_db_exec_args(self):
        return [ 'mysql_install_db', '--datadir=' + self._core.config['data_dir'] ]
