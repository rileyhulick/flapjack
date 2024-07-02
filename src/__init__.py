from .core import *

from .nginx import Nginx
from .php import Php
from .mysql import Mysql

httpd_names.update([
        ('nginx', Nginx),
    ])

database_names.update([
        ('mysql', Mysql),
    ])

app_framework_names.update([
        ('php', Php),
    ])
