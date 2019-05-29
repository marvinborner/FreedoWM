#!/usr/bin/env python3.7

from os import system

from Xlib import X, XK
from Xlib.display import Display


class FreedoWM(object):
    def __init__(self):
        self.display = Display()
        self.event = self.display.next_event()
        self.root = self.display.screen().root
        self.colormap = self.display.screen().default_colormap
        self.currently_focused = None
        self.start = None

        self.NET_WM_NAME = self.display.intern_atom('_NET_WM_NAME')
        self.NET_ACTIVE_WINDOW = self.display.intern_atom('_NET_ACTIVE_WINDOW')

    def set_listeners(self):
        # Listen for window changes
        self.root.change_attributes(
            event_mask=X.PropertyChangeMask | X.FocusChangeMask | X.SubstructureNotifyMask | X.PointerMotionMask
        )

        # Keyboard listener
        self.root.grab_key(X.AnyKey, X.Mod4Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

        # Button (Mouse) listeners
        self.root.grab_button(X.AnyButton, X.Mod4Mask, 1,
                              X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask,
                              X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)

    def is_key(self, key_name):
        return self.event.type == X.KeyPress \
               and self.event.detail == self.display.keysym_to_keycode(XK.string_to_keysym(key_name))

    def window_focused(self):
        return hasattr(self.event, "child") and self.event.child != X.NONE or self.root.query_pointer().child != 0

    def set_border(self, child, color):
        if child is not None and child is not X.NONE:
            border_color = self.colormap.alloc_named_color(color).pixel
            child.configure(border_width=1)
            child.change_attributes(None, border_pixel=border_color)

    def update_windows(self):
        # Only update if the self.event has relevance (focus/title change)
        # if self.event.type != X.PropertyNotify:
        #   return
        new_focus = False

        # Set focused window "in focus"
        if self.window_focused():
            if hasattr(self.event, "child") and self.event.child != self.currently_focused:
                new_focus = True
                self.currently_focused = self.event.child
                self.event.child.configure(stack_mode=X.Above)
            elif self.root.query_pointer().child != self.currently_focused:
                new_focus = True
                self.currently_focused = self.root.query_pointer().child
                self.root.query_pointer().child.configure(stack_mode=X.Above)

        # Set all windows to un-focused borders
        if self.event.type == X.FocusOut or new_focus:
            for child in self.root.query_tree().children:
                print("RESET FOCUS")
                self.set_border(child, "#000")

        # Set focused window border
        if self.event.type == X.FocusIn or new_focus:
            child = self.root.query_pointer().child
            self.currently_focused = child
            if child != 0:
                print("FOCUS")
                child.configure(stack_mode=X.Above)
                self.set_border(child, "#fff")

        self.display.sync()

    # Check for actions until exit
    def main_loop(self):
        self.set_listeners()
        while 1:
            self.event = self.display.next_event()
            self.update_windows()

            # Resize window (MOD + right click)
            if self.event.type == X.ButtonPress and self.event.child != X.NONE:
                attribute = self.event.child.get_geometry()
                self.start = self.event

            # Move window (MOD + left click)
            elif self.event.type == X.MotionNotify and self.start:
                x_diff = self.event.root_x - self.start.root_x
                y_diff = self.event.root_y - self.start.root_y
                self.start.child.configure(
                    x=attribute.x + (self.start.detail == 1 and x_diff or 0),
                    y=attribute.y + (self.start.detail == 1 and y_diff or 0),
                    width=max(1, attribute.width + (self.start.detail == 3 and x_diff or 0)),
                    height=max(1, attribute.height + (self.start.detail == 3 and y_diff or 0))
                )

            # Cycle between windows (MOD + Tab) // X11's "tab" keysym is 0, but it's 23
            if self.event.type == X.KeyPress and self.event.detail == 23:
                self.event.child.configure(stack_mode=X.Below)

            # Close window (MOD + Q)
            elif self.is_key("q") and self.window_focused():
                self.event.child.destroy()

            # Open terminal (MOD + Enter) // X11's "enter" keysym is 0, but it's 36
            elif self.event.type == X.KeyPress and self.event.detail == 36:
                system("st &")

            # Open dmenu (MOD + D)
            elif self.is_key("d"):
                system("dmenu_run &")

            # Exit window manager (MOD + C)
            elif self.is_key("c"):
                self.display.close()

            elif self.event.type == X.ButtonRelease:
                self.start = None


FreedoWM = FreedoWM()
FreedoWM.main_loop()
