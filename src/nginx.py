import re, os.path
from .core import Core
from .utils import sbin_which, get_prefixed_dir

class Nginx:
    def __init__(self, core: Core):
        self._core = core

        self._exec_name = sbin_which('nginx')
        assert self._exec_name # TODO

        self._system_config_dir = get_prefixed_dir(self._exec_name, './etc/nginx')
        assert self._system_config_dir # TODO

        self._update_config()

    def _update_config(self):
        self._core.config['system_nginx_conf_dir'] = self._system_config_dir

        out_indices = []
        def _update_aux_indices(in_value):
            nonlocal out_indices

            if isinstance(in_value, list):
                out_indices = sorted([ x.strip() for x in in_value ])
            elif isinstance(in_value, str):
                out_indices = [ in_value ]
            else:
                assert False # TODO

        if      'nginx_aux_indices' in self._core.config \
            and 'nginx_aux_index'   in self._core.config:
            # TODO warning
            pass
        elif in_value := self._core.config.get('nginx_aux_indices'):
            _update_aux_indices(in_value)
        elif in_value := self._core.config.get('nginx_aux_index'):
            _update_aux_indices(in_value)

        try:
            del self._core.config['nginx_aux_index']
        except KeyError:
            pass

        self._core.config['nginx_aux_indices'] = out_indices

        for key, value in self._core.config.items():
            if key_match := re.match(r'nginx_(\w+)_aux$', key):
                assert key_match.group(1) in ('server', 'http', 'global')

                nest_level = 0
                out_block = ''
                def _update_block(in_block: str):
                    nonlocal nest_level, out_block
                    pos = 0

                    _r1 = re.compile(r'[^{};]+{\s*')
                    _r2 = re.compile(r'[^{};]+(;|$|(?=}))')
                    _r3 = re.compile(r'\s*}\s*')
                    _r4 = re.compile(r'\s*;\s*')

                    while pos < len(in_block):
                        if m1 := _r1.match(in_block, pos):
                            nest_level += 1
                            out_block += m1.group(0).strip()
                            pos = m1.end()
                        elif m2 := _r2.match(in_block, pos):
                            out_block += m2.group(0).strip()
                            if not out_block.endswith(';'):
                                out_block += ';'
                                # TODO warn
                            pos = m2.end()
                        elif m3 := _r3.match(in_block, pos):
                            out_block += m3.group(0).strip()
                            nest_level -= 1
                            assert nest_level >= 0 # TODO
                            pos = m3.end()
                        elif m4 := _r4.match(in_block, pos):
                            pos = m4.end()
                        else:
                            assert False # TODO

                if isinstance(value, str):
                    _update_block(value)
                else:
                    for block in value:
                        _update_block(block)

                if nest_level > 0:
                    # TODO warn
                    out_block += ('}' * nest_level)
                self._core.config[key] = out_block

        self._core.config.setdefault('nginx_server_aux', '')
        self._core.config.setdefault('nginx_http_aux', '')
        self._core.config.setdefault('nginx_global_aux', '')

    @property
    def config_files(self):
        return { 'nginx_conf': 'nginx.conf.in' }

    @property
    def daemon_command(self):
        return self._exec_name, [ '-c', self._core.config['nginx_conf'] ]

    # @property
    # def system_config_dirs(self):
    #     return { 'system_nginx_conf_dir': './etc/nginx' }

