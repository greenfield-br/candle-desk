#!/usr/bin/env python3
"""Print the daily crontab line for this installation and interpreter."""
import json,shlex,sys
from pathlib import Path
root=Path(__file__).resolve().parent
cfg=json.loads((root/'update_settings.json').read_text())
hour=int(cfg['daily_cron_hour']);minute=int(cfg['daily_cron_minute'])
if not (0<=hour<24 and 0<=minute<60):raise ValueError('Invalid cron hour/minute')
(root/'logs').mkdir(exist_ok=True)
quote=lambda p:shlex.quote(str(p))
print(f"{minute} {hour} * * * {quote(sys.executable)} {quote(root/'update.py')} >> {quote(root/'logs'/'cron.log')} 2>&1")
