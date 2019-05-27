#!/usr/bin/env python3.7

from os import system

from Xlib import X, XK
from Xlib.display import Display

display = Display()
root = display.screen().root
colormap = display.screen().default_colormap

# Listen for window changes
root.change_attributes(event_mask=X.PropertyChangeMask)

# Keyboard listener
root.grab_key(X.AnyKey, X.Mod4Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

# Button (Mouse) listeners
root.grab_button(X.AnyButton, X.Mod4Mask, 1,
                 X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask,
                 X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)

start = None


def is_key(key_name):
    return event.type == X.KeyPress and event.detail == display.keysym_to_keycode(XK.string_to_keysym(key_name))


def window_focused():
    return hasattr(event, 'child') and event.child != X.NONE


def update_windows():
    # Only update if the event has relevance (focus/title change)
    # if event.type != X.PropertyNotify:
    #   return

    for child in event.window.query_tree().children:
        if child == X.NONE:
            border_color = colormap.alloc_named_color("#000000").pixel
        else:
            border_color = colormap.alloc_named_color("#ffffff").pixel

        child.configure(border_width=1)
        child.change_attributes(None, border_pixel=border_color)
        display.sync()


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
        display.close()

    elif event.type == X.ButtonRelease:
        start = None

    else:
        update_windows()
