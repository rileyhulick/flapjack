# Flapjack

No-fuss web stack for localhost development on Linux.

Flapjack aims to minimize the steps between
<span style="color:'#009999';font-style:italic">**"git clone"**</span> and
<span style="color:'#ff0066';font-style:italic">**"start debugging"**</span> for
web applications. Simply navigate to your project's directory and run:

```sh
flapjack --port 58080
```

Then open a web browser to http://localhost:58080 and start an XDebug session
on port 9003 using your IDE of choice. One command and your app is running
within a proper web stack (Nginx / MySQL / PHP-FPM). It's as easy as pancakes!

The more conventional approach to running a web stack involves use of a
system-wide unit manager like systemd or Docker. These tools provide many
advantages for production servers where applications are expected to operate
reliably and securely while unattended. However, the needs are quite different
on a development machine running an app for local debugging.

And that's where Flapjack comes in:

 - Simple one-size-fits-all configuration of any stack either through the
   command-line or "flapjack.json". Debug your code, not your config
 - All of a project's runtime data is scoped to that project, and each project
   is run on-demand. This makes it trivial to keep any number of projects on
   the same machine, in any location, for as long or short a time as needed.
 - The stack runs entirely in the developer's user account. This not only means
   that elevated privileges are not necessary, but it also simplifies many
   common problems related to file ownership and permissions.

Note that it is not a good idea to expose any ports created by Flapjack through
a firewall.

Flapjack is still a work-in-progress so there are some caveats:

 - Stack components (Nginx, MySQL, and PHP) must be installed separately, i.e.,
   through your system package manager.
 - Only Nginx / MySQL / PHP-FPM is currently supported. More stacks and
   configurations will be supported in the future!
 - Startup errors and crashes are not robustly detected (yet). Keep an eye on
   your .flapjack/*.log files if you're having trouble.
 - Flapjack will initialize a MySQL data directory, but will not (yet) populate
   it with a project-specific database or credentials. You will have to set
   this part up yourself e.g., with something like:

```sh
flapjack &
mysql --socket='./.flapjack/mysql.sock'
```
```sql
CREATE DATABASE wordpress;
CREATE USER 'wordpress'@'localhost' IDENTIFIED BY "wordpresspass";
GRANT ALL PRIVILEGES ON wordpress.* TO 'wordpress'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

These caveats notwithstanding, I still find it much more convenient than systemd
for debugging. I hope you find it useful too!
