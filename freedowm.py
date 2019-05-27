#!/usr/bin/env python3.7

import sys
from os import system

from Xlib import X, XK
from Xlib.display import Display

display = Display()
num = display.get_display_name()

# Keyboard listener
display.screen().root.grab_key(X.AnyKey, X.Mod4Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

# Button (Mouse) listeners
display.screen().root.grab_button(X.AnyButton, X.Mod4Mask, 1,
                                  X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask,
                                  X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)

start = None


def is_key(key_name):
    return event.type == X.KeyPress and event.detail == display.keysym_to_keycode(XK.string_to_keysym(key_name))


def window_focused():
    return event.child != X.NONE


# Check for actions until exit
while 1:
    event = display.next_event()

    # Resize window (MOD + right click)
    if event.type == X.ButtonPress and event.child != X.NONE:
        attribute = event.child.get_geometry()
        start = event

    # Move window (MOD + left click)
    elif event.type == X.MotionNotify and start:
        xDiff = event.root_x - start.root_x
        yDiff = event.root_y - start.root_y
        start.child.configure(
            x=attribute.x + (start.detail == 1 and xDiff or 0),
            y=attribute.y + (start.detail == 1 and yDiff or 0),
            width=max(1, attribute.width + (start.detail == 3 and xDiff or 0)),
            height=max(1, attribute.height + (start.detail == 3 and yDiff or 0))
        )

    # Raise window under cursor (MOD + K)
    if is_key("k") and window_focused():
        event.child.configure(stack_mode=X.Above)

    # Close window (MOD + Q)
    elif is_key("q") and window_focused():
        event.child.destroy()

    # Open terminal (MOD + Enter) // X11's "enter" keysym is 0, but it's 36
    elif event.type == X.KeyPress and event.detail == 36:
        system("st &")

    # Open dmenu (MOD + D)
    elif is_key("d"):
        system("dmenu_run &")

    # Exit window manager (MOD + C)
    elif is_key("c"):
        sys.exit()

    elif event.type == X.ButtonRelease:
        start = None
