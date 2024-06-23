Flapjack

No-fuss web stack for localhost development on Linux.

The idea is:

 $ cd /my/web/project
 $ flapjack . --stack nginx/php-fpm --database mysql
>>> [flapjack] Started mysqld on port 53060
>>> [flapjack] Setting up database in ./.srv/data
>>> [flapjack] Started nginx/php-fpm http://localhost:58080
>>> [flapjack] Listening for XDebug client on :9003

Then SIGINT (ctrl+c) to gracefully shut the stack down.

The point is to minimize the steps between "git clone" and "start debugging".
Everything is done in the current user account using project-scoped data, random
IP ports, and a simple all-in-one config file called flapjack.json. At no point
is the user required to touch sudo or systemctl or even chown.

Note that it's not a good idea to use Flapjack in a production setting, or to
expose ports used by Flapjack through a firewall.

Flapjack is still a work-in-progress, so using it now looks more like:

 $ cd /path/to/flapjack/
 $ python3 -m venv .venv && source .venv/bin/activate
 $ pip install -r requirements.txt
<<< write a flapjack.json file with www_dir set to the web project
<<< use mysql_install_db to set up the database directory
 $ ./run.py
<<< use mysql to set up the project database

The currently supported stack is nginx/mysql/php-fpm. Even at this early stage,
I find it much more convenient than using global configurations and systemd
services for debugging.

Other proposed features include:

 - Support for other stacks e.g., Apache, Postgres, Django, Rails, etc.
    - Perhaps an API for third-party extensions
 - Automatically set up a database and db user from flapjack.json
 - Emulate systemd timers / cron
 - D-Bus interface and IDE integration
 - Support for Windows / MacOS ?
