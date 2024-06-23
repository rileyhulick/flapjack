#!/usr/bin/env python3

import sys, os, os.path, json, re, subprocess, shutil, tempfile
import pyexpander.lib as pyexpander

assert __name__ == '__main__'

indir = os.path.dirname(__file__) # HACK

try:
    with open(os.path.join(indir, 'flapjack.json'), 'r') as f:
        conf_globals = json.load(f)
        assert isinstance(conf_globals, dict)
except FileNotFoundError:
    conf_globals = {}

stack = conf_globals.get('stack', None)
if not stack or stack == 'default':
    stack = ['nginx', 'mysql', 'php']

try:
    if isinstance(stack, str):
        raise TypeError
    for stack_entry in stack:
        if isinstance(stack_entry, str):
            conf_globals.setdefault('with_' + stack_entry, True)
        else:
            raise TypeError
except TypeError:
    # TODO error
    exit(-1)

conf_globals.setdefault('www_port', 8080)
conf_globals.setdefault('www_dir', './.srv/www')

conf_globals.setdefault('with_nginx', False)
if conf_globals['with_nginx']:
    conf_globals.setdefault('system_nginx_conf_dir', '/etc/nginx')

conf_globals.setdefault('with_mysql', False)
if conf_globals['with_mysql']:
    conf_globals.setdefault('mysql_port', 3060)
    conf_globals.setdefault('mysql_data_dir', './.srv/data')
    conf_globals.setdefault('system_mysql_conf_dir', '/etc/mysql')

conf_globals.setdefault('with_php', False)
if conf_globals['with_php']:
    conf_globals.setdefault('system_php_conf_dir', '/etc/php')

for key, value in conf_globals.items():
    if key.endswith('_dir') and not value.startswith('/'): # HACK-ish
        conf_globals[key] = os.path.abspath(os.path.join(indir, value))

with tempfile.TemporaryDirectory(prefix='flapjack_') as outdir:
    print(f"[flapjack] Writing temporary files to {outdir}")

    for subdir in [
            'nginx',
            'mysql',
            'php',
        ]:
        if not conf_globals['with_' + subdir]:
            continue

        outsubdir = conf_globals.get(subdir + '_dir')
        if not outsubdir:
            outsubdir = conf_globals[subdir + '_dir'] = os.path.join(outdir, subdir)
            os.makedirs(outsubdir, exist_ok=True)

    for key, relpath in [
            ('nginx_conf',   'nginx/nginx.conf'),
            ('mysql_conf',   'mysql/mysql.conf'),
            ('php_conf',     'php/php.ini'     ),
            ('php_fpm_conf', 'php/php-fpm.conf'),
        ]:
        subdir, basename = os.path.split(relpath)

        if not conf_globals['with_' + subdir]:
            continue

        inpath = conf_globals.get(key + '_in')
        if not inpath:
            inpath = conf_globals[key + '_in'] = os.path.join(indir, 'conf.d', relpath + '.in')

        outpath = conf_globals.get(key)
        if not outpath:
            outpath = conf_globals[key] = os.path.join(conf_globals[subdir + '_dir'], basename)

        with open(inpath, 'r') as if_:
            output, inner_globals, deps = pyexpander.expandToStr(
                    if_.read()
                  , filename=inpath
                  , external_definitions=conf_globals
                )

        with open(outpath, 'w') as of:
            of.write(output)
        del output

    www_dir = conf_globals.get('www_dir')
    os.makedirs(conf_globals['www_dir'], exist_ok=True)
    os.makedirs(conf_globals['mysql_data_dir'], exist_ok=True)

    processes = []

    if conf_globals['with_mysql']:
        processes.append(subprocess.Popen([
                '/usr/sbin/mysqld', # TODO config/search for default
                "--defaults-file={mysql_conf}".format(**conf_globals),
                '--datadir', conf_globals['mysql_data_dir'],
                '--socket', conf_globals['mysql_dir'] + '/mysql.sock'
                '-P', str(conf_globals['mysql_port']),
            ]))
        print("[flapjack] Started mysqld on port {mysql_port}".format(**conf_globals))

    if conf_globals['with_php']:
        os.putenv('PHP_INI_SCAN_DIR', 'Off')
        processes.append(subprocess.Popen([
                '/usr/sbin/php-fpm8.2', # TODO config/search for default
                '-c', conf_globals['php_conf'],
                '--fpm-config', conf_globals['php_fpm_conf'],
            ]))
        print('[flapjack] Started php-fpm')

    if conf_globals['with_nginx']:
        processes.append(subprocess.Popen([
                '/sbin/nginx', # TODO config/search for default
                '-c', conf_globals['nginx_conf'],
            ]))
        print("[flapjack] Started nginx on port http://localhost:{www_port}".format(**conf_globals))

    try:
        # TODO asyncio
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        print('[flapjack] Terminating subprocesses')
        for proc in processes:
            proc.terminate()
