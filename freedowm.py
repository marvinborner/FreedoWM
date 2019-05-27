#!/usr/bin/env python3.7

import sys
from os import system
from Xlib.display import Display
from Xlib import X, XK

display = Display()
num = display.get_display_name()

# Window raiser listener
display.screen().root.grab_key(display.keysym_to_keycode(XK.string_to_keysym("k")),
                               X.Mod4Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

# Terminal listener
display.screen().root.grab_key(display.keysym_to_keycode(XK.string_to_keysym("enter")),
                               X.Mod4Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

# Dmenu listener
display.screen().root.grab_key(display.keysym_to_keycode(XK.string_to_keysym("d")),
                               X.Mod4Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

# Exit listener
display.screen().root.grab_key(display.keysym_to_keycode(XK.string_to_keysym("c")),
                               X.Mod4Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

# Window move listener
display.screen().root.grab_button(1, X.Mod4Mask, 1,
                                  X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask,
                                  X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)

# Window resize listener
display.screen().root.grab_button(3, X.Mod4Mask, 1,
                                  X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask,
                                  X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)

start = None

# Check for actions until exit
while 1:
    event = display.next_event()

    # Raise window under cursor (MOD + K)
    if event.type == X.KeyPress and event.child != X.NONE and event.detail == 45:
        event.child.configure(stack_mode=X.Above)

    # Resize window (MOD + right click)
    elif event.type == X.ButtonPress and event.child != X.NONE:
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
            height=max(1, attribute.height + (start.detail == 3 and yDiff or 0)))

    # Close program (MOD + Q)
    elif event.type == X.KeyPress and event.child != X.NONE and event.detail == 24:
        event.child.destroy()

    # Open terminal (MOD + Enter)
    elif event.type == X.KeyPress and event.detail == 36:
        system("st &")

    # Open dmenu (MOD + D)
    elif event.type == X.KeyPress and event.detail == 40:
        system("dmenu_run &")

    # Exit window manager (MOD + C)
    elif event.type == X.KeyPress and event.detail == 54:
        sys.exit()

    elif event.type == X.ButtonRelease:
        start = None
