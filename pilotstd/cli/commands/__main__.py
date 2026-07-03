# pilotstd/cli/commands/__main__.py
# 允许 python -m pilotstd.cli.commands 方式启动
import sys

from pilotstd.cli.commands import main

sys.exit(main())
