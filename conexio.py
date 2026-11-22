#!/usr/bin/env python3
"""Standalone use of the conexio 200 reader outside Home Assistant.

    python conexio.py --url http://192.168.1.50 --password ... --once
    python conexio.py --url http://192.168.1.50 --mqtt-host broker --mqtt-username ...

The code lives in conexio200/conexio (the Home Assistant app); this file only
puts it on the import path. Passwords can also be given via the environment
variables CONEXIO_PASSWORD and MQTT_PASSWORD.

Copyright (c) 2021 Julian Dittrich
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "conexio200"))

from conexio.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
