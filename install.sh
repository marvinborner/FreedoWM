#!/bin/sh
cp freedowm.desktop /usr/share/xsessions/
cp freedowm-session /usr/bin/
chmod a+x /usr/bin/freedowm-session
# cp -n example.ini /home/$(logname)/.config/freedowm.ini
cp example.ini /home/$(logname)/.config/freedowm.ini
python3.7 setup.py install