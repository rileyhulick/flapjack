import asyncio, os, os.path, shutil, sys, tempfile, subprocess
import re, json
import pyexpander.lib as pyexpander
from collections import OrderedDict

in_dir = os.path.dirname(os.path.realpath(__file__))

app_framework_names = dict()
database_names = dict()
httpd_names = dict()

class Core:
    class InitError(Exception): pass
    class BadWorkDirError(InitError): pass
    class BadConfigFileError(InitError): pass
    class ConfigFileTypeError(InitError): pass
    class ConfigFileStackTypeError(ConfigFileTypeError): pass

    class ExecPathNotFound(InitError):
        def __init__(self, exec_name: str, key: str | None = None):
            self._exec_name = exec_name
            self._key = key

        @property
        def exec_name(self):
            return self._exec_name

        @property
        def key(self):
            return self._key

    class NoConfigWarning(Exception):
        def __init__(self, work_dir: str):
            self._work_dir = work_dir

        @property
        def work_dir(self):
            return self._work_dir

    def __init__(
            self
          , args = None
          ):

        self._config_file = None
        self._config = {}

        self._run_dir = None
        self._temp_dir = None
        self._work_dir = None

        # self._processes = []

        self._www_port = None
        self._www_dir  = None
        self._data_port = None
        self._data_dir  = None

        stack = []

        tolerate_no_read_config = False
        write_config_file = None

        if args:
            self._work_dir = args.work_dir
            self._run_dir  = args.run_dir
            self._temp_dir = args.temp_dir

            self._config_file = args.config_file

            if args.stack:
                stack = args.stack

            if args.write_config:
                write_config_file = args.write_config
            elif args.write_config is None:
                write_config_file = './flapjack.json'


            self._www_port  = args.port
            # self._www_dir   = args.www_dir
            self._data_port = args.data_port
            self._data_dir  = args.data_dir

            tolerate_no_read_config = any([
                    args.force,
                    write_config_file,
                    args.stack,
                    args.port,
                    # args.data_port,
                    # args.data_dir,
                ])

        if self._work_dir:
            if not os.path.isdir(self._work_dir):
                raise Core.BadWorkDirError()
        else:
            self._work_dir = os.getcwd()

        if self._config_file:
            if not os.path.isfile(self._config_file):
                raise Core.BadConfigFileError()
        else:
            for name in ['flapjack.json']: # 'flapjack.yaml', 'flapjack.yml'
                maybe_file = os.path.join(self._work_dir, name)
                if not os.path.isfile(maybe_file):
                    continue

                self._config_file = maybe_file
                break

            if not tolerate_no_read_config and not self._config_file:
                raise Core.NoConfigWarning(self._work_dir)

        if self._config_file:
            with open(self._config_file, 'r') as f:
                self._config = json.load(f, object_hook=OrderedDict)

            if not stack and 'stack' in self._config:
                stack = self._config['stack']
                if not isinstance(stack, list):
                    raise Core.ConfigFileStackTypeError

            # specifying work_dir in the config file may not be well-formed,
            # possibly warn about that here?

            if not self._www_dir:
                self._www_dir = self._config.get('www_dir')
            if not self._www_port:
                self._www_port = self._config.get('www_port')

            if not self._data_dir:
                self._data_dir = self._config.get('data_dir')
            if not self._data_port:
                self._data_port = self._config.get('data_port')

                # del self._config['stack']

        # TODO global configuration?

        if not any( n in stack for n in app_framework_names ):
            stack.append('php')

        if not any( n in stack for n in database_names ):
            stack.append('mysql')

        if not any( n in stack for n in httpd_names ):
            stack.append('nginx')

        # TODO get pickier and don't spin up a database (and possibly app
        # framework) if we haven't been told to

        self._stack = OrderedDict()

        self._app_framework = None
        self._database = None
        self._httpd = None

        for stack_entry in stack:
            if isinstance(stack_entry, str):
                name = stack_entry
                pass
            else:
                raise Core.ConfigFileStackTypeError

            with_ = self._config.get('with_' + name, True)
            if not with_:
                continue

            if app_framework := app_framework_names.get(name):
                if self._app_framework:
                    # TODO warning
                    continue

                component = self._app_framework = app_framework(self)
            elif database := database_names.get(name):
                if self._database:
                    # TODO warning
                    continue

                component = self._database = database(self)
            elif httpd := httpd_names.get(name):
                if self._httpd:
                    # TODO warning
                    continue

                component = self._httpd = httpd(self)
            else:
                print(f"[flapjack] unrecognized stack item '{name}'", file=sys.stderr)
                continue

            self._stack[name] = component
            self._config['with_' + name] = True

            exec_path_key = name + '_exec'
            exec_path_prefix = None

            exec_path = self._config.get(exec_path_key)
            if exec_path:
                assert os.path.isabs(exec_path) # TODO
            else:
                if os.path.isabs(component.exec_name):
                    exec_path = component.exec_name
                else:
                    exec_search_paths = [ None, '/sbin', '/usr/sbin' ] # libexec?
                    # try:
                    #     exec_search_paths = component.exec_paths + exec_search_paths
                    # except AttributeError:
                    #     pass

                    for search_path in exec_search_paths:
                        exec_path = shutil.which(component.exec_name, path=search_path)
                        if exec_path:
                            break

                    if not exec_path:
                        raise Core.ExecPathNotFound(component.exec_name, key=exec_path_key)

                    exec_path_prefix = os.path.normpath(os.path.join(os.path.dirname(exec_path), '..'))

                self._config[exec_path_key] = exec_path

            if not os.path.isfile(exec_path):
                if not exec_path:
                    raise Core.ExecPathNotFound(component.exec_name, key=exec_path_key)

            if not exec_path_prefix:
                exec_path_prefix = '/'

            system_config_dirs = []
            try:
                system_config_dirs = component.system_config_dirs.items()
            except AttributeError:
                pass

            for system_config_dir_key, system_config_dir in system_config_dirs:
                if system_config_dir_key in self._config:
                    assert os.path.isabs(self._config[system_config_dir_key]) # TODO
                else:
                    if os.path.isabs(system_config_dir):
                        assert os.path.isdir(system_config_dir) # TODO
                        self._config[system_config_dir_key] = system_config_dir

                    else:
                        found_dir = False
                        for prefix in [ exec_path_prefix, '/' ]:
                            maybe_dir = os.path.normpath(os.path.join(prefix, system_config_dir))
                            if not os.path.isdir(maybe_dir):
                                continue

                            self._config[system_config_dir_key] = maybe_dir
                            found_dir = True
                            break

                        assert found_dir # TODO

        for n in app_framework_names:
            self._config.setdefault('with_' + n, False)
        for n in database_names:
            self._config.setdefault('with_' + n, False)
        for n in httpd_names:
            self._config.setdefault('with_' + n, False)

        if self._httpd:
            # TODO choose random port
            # self._www_port = self._config.get('www_port')
            if not self._www_port:
                self._www_port = 58080
            self._config['www_port'] = self._www_port

            # self._www_dir = self._config.get('www_dir', '.')
            if not self._www_dir:
                self._www_dir = self._work_dir
            elif not os.path.isabs(self._www_dir):
                self._www_dir = os.path.normpath(os.path.join(self._work_dir, self._www_dir))
            self._config['www_dir'] = self._www_dir

        if self._database:
            # TODO support persistent local socket as an alternative to TCP port

            # TODO random port
            # self._data_port = self._config.get('data_port')
            if not self._data_port:
                self._data_port = 53060

            self._config['data_port'] = self._data_port

            # TODO data directory should include at least the database component
            # name as  known to flapjack (i.e., 'mysql'), and possibly additional
            # case-specific identifiers (i.e., 'mysql-innodb'). this could help
            # prevent confusion if multiple database directories are used.

            # self._data_dir = self._config.get('data_dir')
            # if not self._data_dir:
            #     # relative path for now, will be made absolute in _setup_writable_dirs
            #     self._config['data_dir'] = self._data_dir = './data'

        if write_config_file:
            print('[flapjack] writing config file from command line not yet supported', file=sys.stderr)

    def _setup_writable_dirs(self):
        try:
            if self._writable_dirs_ready:
                return
        except AttributeError:
            pass

        assert os.path.isabs(self._work_dir)

        all_in_temp = False

        if self._run_dir:
            if not os.path.isabs(self._run_dir):
                self._run_dir = os.path.normpath(os.path.join(self._work_dir, self._run_dir))
        else:
            if os.access(self._work_dir, os.W_OK):
                self._run_dir = os.path.normpath(os.path.join(self._work_dir, '.flapjack'))
            else:
                all_in_temp = True

        if self._run_dir:
            try:
                os.makedirs(self._run_dir)
            except FileExistsError:
                pass

        if self._temp_dir:
            if not os.path.isabs(self._temp_dir):
                assert not all_in_temp # TODO
                self._temp_dir = os.path.normpath(os.path.join(self._work_dir, self._temp_dir))

            try:
                os.makedirs(self._temp_dir)
            except FileExistsError:
                pass
        else:
            self._temp_dir_ctx = tempfile.TemporaryDirectory(
                    prefix = ('tmp_' if not all_in_temp else 'flapjack_'),
                    dir = (self._run_dir if not all_in_temp else None)
                )
            self._temp_dir = self._temp_dir_ctx.name

            if all_in_temp:
                self._run_dir = self._temp_dir

        assert os.path.isdir(self._run_dir) \
            and os.path.isabs(self._run_dir) \
            and os.access(self._run_dir, os.W_OK) \
            and os.path.isdir(self._temp_dir) \
            and os.path.isabs(self._temp_dir) \
            and os.access(self._temp_dir, os.W_OK)

        self._config['run_dir'] = self._run_dir
        self._config['temp_dir'] = self._temp_dir

        if self._database:
            # self._data_dir = self._config.get('data_dir')
            if not self._data_dir:
                self._data_dir = os.path.normpath(os.path.join(self._run_dir, './data'))
            elif not os.path.isabs(self._data_dir):
                self._data_dir = os.path.normpath(os.path.join(self._work_dir, self._data_dir))

            self._config['data_dir'] = self._data_dir

            try:
                os.makedirs(self._data_dir)
                self._new_data_dir = True
            except FileExistsError:
                pass

        self._writable_dirs_ready = True

    def _cleanup_writable_dirs(self):
        try:
            self._temp_dir_ctx.cleanup()
        except AttributeError:
            # TODO we were given an explicit temporary directory path.
            # delete the files we made but not the directory itself even if
            # we created it
            pass

        if self._run_dir == self._temp_dir:
            self._run_dir = None
            del self._config['run_dir']

        self._temp_dir = None
        del self._config['temp_dir']

    @property
    def config(self):
        return self._config

    @property
    def work_dir(self):
        return self._work_dir

    @property
    def run_dir(self):
        self._setup_writable_dirs()
        return self._run_dir

    @property
    def temp_dir(self):
        self._setup_writable_dirs()
        return self._temp_dir

    def run(self) -> None:
        if not self._stack:
            print('[flapjack] empty stack (quitting)', file=sys.stderr)
            return

        processes = []

        try:
            self._setup_writable_dirs()

            if self._database:
                new_data_dir = False
                try:
                    new_data_dir = self._new_data_dir
                except AttributeError:
                    pass

                install_db_exec_args = None
                try:
                    install_db_exec_args = self._database.install_db_exec_args
                except AttributeError:
                    pass

                if new_data_dir and install_db_exec_args:
                    # TODO /sbin support? custom path?

                    p = subprocess.run(install_db_exec_args)
                    assert p.returncode == 0

            subprocess_config_files = []

            # generate all config filenames before generating any config files
            # so they can reference each other freely
            for component in self._stack.values():
                try:
                    component.validate_config()
                except AttributeError:
                    pass

                config_files = []
                try:
                    config_files = component.config_files.items()
                except AttributeError:
                    pass

                for key, in_file in config_files:
                    in_path = os.path.join(in_dir, in_file)

                    out_path = self._config.get(key)
                    if not out_path:
                        out_file = re.match(r'(.*)(?:\.in)|$', in_file).group(1)
                        out_path = self._config[key] = os.path.normpath(os.path.join(self._temp_dir, out_file))

                    subprocess_config_files.append((in_path, out_path,))

            # now generate the config files
            for in_path, out_path in subprocess_config_files:
                with open(in_path, 'r') as if_:
                    output, inner_globals, deps \
                        = pyexpander.expandToStr(
                            if_.read()
                          , filename=in_path
                          , external_definitions=self._config )
                with open(out_path, 'w') as of:
                    of.write(output)
                del output

            print('[flapjack] starting subprocesses...')

            async def _run_async():
                nonlocal processes

                for key, component in self._stack.items():
                    exec_path = self._config[key + '_exec']

                    env = None
                    try:
                        component.exec_env
                        env = os.environ.copy()
                        env.update(component.exec_env.items())
                    except AttributeError:
                        pass

                    print(f"[flapjack] starting {key} ({list((exec_path,)) + component.exec_args})")
                    processes.append( await asyncio.create_subprocess_exec(exec_path, *component.exec_args, env=env) )

                if self._httpd:
                    httpd_name = ''
                    for n, c in self._stack.items():
                        if c == self._httpd:
                            httpd_name = n
                            break

                    print(f"[flapjack] {httpd_name} listening on http://localhost:{self._www_port}")

                await asyncio.gather(*[ process.wait() for process in processes ])
                # TODO detect unexpected signals and non-zero return codes

            asyncio.run( _run_async() )

        except KeyboardInterrupt:
            print(flush=True)
            print('[flapjack] terminating subprocesses')
            for proc in processes:
                try:
                    proc.terminate()
                except ProcessLookupError: # HACK
                    # if the process has has closed of its own accord
                    # (i.e., due to an error) then we'll get this exception
                    pass

        finally:
            self._cleanup_writable_dirs()
