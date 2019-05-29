#!/usr/bin/env python3.7

from os import system

from Xlib import X, XK
from Xlib.display import Display

display = Display()
root = display.screen().root
colormap = display.screen().default_colormap
currently_focused = None

NET_WM_NAME = display.intern_atom('_NET_WM_NAME')
NET_ACTIVE_WINDOW = display.intern_atom('_NET_ACTIVE_WINDOW')

# Listen for window changes
root.change_attributes(event_mask=
                       X.PropertyChangeMask | X.FocusChangeMask | X.SubstructureNotifyMask | X.PointerMotionMask)

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
    return hasattr(event, "child") and event.child != X.NONE or root.query_pointer().child != 0


def set_border(child, color):
    if child is not None and child is not X.NONE:
        border_color = colormap.alloc_named_color(color).pixel
        child.configure(border_width=1)
        child.change_attributes(None, border_pixel=border_color)


def update_windows():
    # Only update if the event has relevance (focus/title change)
    # if event.type != X.PropertyNotify:
    #   return
    global currently_focused  # TODO: Convert to class-scheme
    new_focus = False

    # Set focused window "in focus"
    if window_focused():
        if hasattr(event, "child") and event.child != currently_focused:
            new_focus = True
            currently_focused = event.child
            event.child.configure(stack_mode=X.Above)
        elif root.query_pointer().child != currently_focused:
            new_focus = True
            currently_focused = root.query_pointer().child
            root.query_pointer().child.configure(stack_mode=X.Above)

    # Set all windows to un-focused borders
    if event.type == X.FocusOut or new_focus:
        for child in root.query_tree().children:
            print("RESET FOCUS")
            set_border(child, "#000")

    # Set focused window border
    if event.type == X.FocusIn or new_focus:
        child = root.query_pointer().child
        currently_focused = child
        if child != 0:
            print("FOCUS")
            child.configure(stack_mode=X.Above)
            set_border(child, "#fff")

    display.sync()


# Check for actions until exit
while 1:
    event = display.next_event()
    update_windows()

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

    # Switch between windows (MOD + Tab)
    if is_key("tab") and window_focused():
        event.child.configure(stack_mode=X.Below)

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
