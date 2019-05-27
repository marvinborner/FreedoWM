#!/bin/sh
cp freedowm.desktop /usr/share/xsessions/
cp freedowm-session /usr/bin/
chmod a+x /usr/bin/freedowm-session
python3.7 setup.py install