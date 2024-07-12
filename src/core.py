import asyncio, os, os.path, shutil, sys, tempfile, subprocess
import re, json
import pyexpander.lib as pyexpander
from collections import OrderedDict

from .session import Session
from .utils import sbin_which

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

        self._processes = []

        self._www_port = None
        self._www_dir  = None
        self._data_port = None
        self._data_dir  = None

        stack = []

        tolerate_no_read_config = False
        # write_config_file = None

        self._daemonize = False
        self._is_stop_daemon = False

        if args:
            self._work_dir = args.work_dir
            self._run_dir  = args.run_dir
            self._temp_dir = args.temp_dir

            self._config_file = args.config_file

            if args.stack:
                stack = args.stack

            # if args.write_config:
            #     write_config_file = args.write_config
            # elif args.write_config is None:
            #     write_config_file = './flapjack.json'


            self._www_port  = args.port
            # self._www_dir   = args.www_dir
            self._data_port = args.data_port
            self._data_dir  = args.data_dir

            tolerate_no_read_config = any([
                    args.force,
                    # write_config_file,
                    args.stack,
                    args.port,
                    # args.data_port,
                    # args.data_dir,
                ])

            self._daemonize = args.daemonize
            self._is_stop_daemon = args.stop_daemon


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

        # if write_config_file:
        #     print('[flapjack] writing config file from command line not yet supported', file=sys.stderr)

        assert os.path.isabs(self._work_dir)

        self._all_in_temp = False

        if self._run_dir:
            if not os.path.isabs(self._run_dir):
                self._run_dir = os.path.normpath(os.path.join(self._work_dir, self._run_dir))
        else:
            if os.access(self._work_dir, os.W_OK):
                self._run_dir = os.path.normpath(os.path.join(self._work_dir, '.flapjack'))
            else:
                self._all_in_temp = True

        if self._temp_dir and not os.path.isabs(self._temp_dir):
            assert not self._all_in_temp # TODO
            self._temp_dir = os.path.normpath(os.path.join(self._work_dir, self._temp_dir))

        self._lockfile = None
        if not self._all_in_temp:
            self._lockfile = os.path.join(self._run_dir, 'flapjack.lock')
        self._session = Session(self._lockfile)



    def _setup_writable_dirs(self):
        try:
            if self._writable_dirs_ready:
                return
        except AttributeError:
            pass

        try:
            os.makedirs(self._run_dir)
        except FileExistsError:
            pass

        if self._temp_dir:
            try:
                os.makedirs(self._temp_dir)
            except FileExistsError:
                pass
        else:
            self._temp_dir_ctx = tempfile.TemporaryDirectory(
                    prefix = ('tmp_' if not self._all_in_temp else 'flapjack_'),
                    dir = (self._run_dir if not self._all_in_temp else None)
                )
            self._temp_dir = self._temp_dir_ctx.name

            if self._all_in_temp:
                self._run_dir = self._temp_dir

        assert all([
            os.path.isdir(self._run_dir),  os.path.isabs(self._run_dir),  os.access(self._run_dir, os.W_OK),
            os.path.isdir(self._temp_dir), os.path.isabs(self._temp_dir), os.access(self._temp_dir, os.W_OK),
            ])

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

    def _lock_new_session(self):
        attempts = 2
        while attempts > 0:
            attempts -= 1
            try:
                self._session.lock_new()
                break
            except FileNotFoundError:
                if not self._all_in_temp \
                    and os.path.samefile(os.path.dirname(self._session.lockfile_name), self._run_dir):
                    os.path.makedirs(self._run_dir)
                    continue
                raise

    def _stop_daemon(self):
        import signal

        self._session.lock_existing()
        os.kill(self._session.pid, signal.SIGINT)

    def _run_stack(self):
        if not self._stack:
            print('[flapjack] empty stack (quitting)', file=sys.stderr)
            return

        self._lock_new_session()

        if self._daemonize:
            if os.fork() == 0:
                print(f"pid: {os.getpid()}")
            else:
                self._session.soft_unlock()
                return

        self._session.write()
        self._setup_writable_dirs()

        # this could probably use some polish
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

        async def _async_main():
            print('[flapjack] starting subprocesses...')

            for key, component in self._stack.items():
                exec_name, args = component.daemon_command
                exec_key = key + '_exec'
                if exec_key in self._config:
                    exec_name = self._config[exec_key]
                    assert os.path.isabs(exec_name)
                else:
                    if not os.path.isabs(exec_name):
                        exec_name = sbin_which(exec_name)
                    assert exec_name
                    self._config[exec_key] = exec_name

                env = None
                try:
                    component.exec_env
                    env = os.environ.copy()
                    env.update(component.exec_env.items())
                except AttributeError:
                    pass

                print(f"[flapjack] starting {key}: {exec_name, args}")
                process = await asyncio.create_subprocess_exec(exec_name, *args, env=env)

                self._processes.append(process)

            if self._httpd:
                httpd_name = ''
                for n, c in self._stack.items():
                    if c == self._httpd:
                        httpd_name = n
                        break

                print(f"[flapjack] {httpd_name} listening on http://localhost:{self._www_port}")

            try:
                await asyncio.gather(*[ process.wait() for process in self._processes ])
            finally:
                self._cleanup_writable_dirs()

        asyncio.run(_async_main())

    def run(self) -> None:
        with self._session:
            if self._is_stop_daemon:
                self._stop_daemon()
                return

            self._run_stack()

    def stop(self):
        if self._processes:
            print('[flapjack] terminating subprocesses')
            for process in self._processes:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
