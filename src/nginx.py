from .core import Core

class Nginx:
    def __init__(self, core: Core):
        self._core = core

    @property
    def config_files(self):
        return { 'nginx_conf': 'nginx.conf.in' }

    @property
    def exec_name(self):
        return 'nginx'

    @property
    def exec_args(self):
        return [ '-c', self._core.config['nginx_conf'] ]

    @property
    def system_config_dirs(self):
        return { 'system_nginx_conf_dir': './etc/nginx' }
