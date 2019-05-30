#!/usr/bin/env python3.7

import configparser
import os

from Xlib import X, XK
from Xlib.display import Display
from Xlib.ext import randr


class FreedoWM(object):
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read(os.environ['HOME'] + "/.config/freedowm.ini")
        self.keys = self.config["KEYMAP"]
        self.colors = self.config["COLORS"]
        self.programs = self.config["PROGRAMS"]
        self.mod = X.Mod1Mask if self.keys["MOD"] == "alt" else X.Mod4Mask

        self.display = Display()
        self.screen = self.display.screen()
        self.root = self.screen.root
        self.event = self.display.next_event()
        self.colormap = self.screen.default_colormap
        self.currently_focused = None
        self.tiling_state = False
        self.start = None
        self.monitors = []

        self.NET_WM_NAME = self.display.intern_atom('_NET_WM_NAME')
        self.NET_ACTIVE_WINDOW = self.display.intern_atom('_NET_ACTIVE_WINDOW')

        self.get_monitors()

    def set_listeners(self):
        # Listen for window changes
        self.root.change_attributes(
            event_mask=X.PropertyChangeMask | X.FocusChangeMask | X.StructureNotifyMask | X.SubstructureNotifyMask | X.PointerMotionMask
        )

        # Keyboard listener
        self.root.grab_key(X.AnyKey, self.mod, 1, X.GrabModeAsync, X.GrabModeAsync)

        # Button (Mouse) listeners
        self.root.grab_button(X.AnyButton, self.mod, 1,
                              X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask,
                              X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE)

    def log(self, message):
        if self.config["GENERAL"]["DEBUG"] != "0":
            print(message)

    def get_monitors(self):
        window = self.root.create_window(0, 0, 1, 1, 1, self.screen.root_depth)
        res = randr.get_screen_resources(window).outputs

        for i in range(self.display.screen_count() + 1):
            info = randr.get_output_info(window, res[i], 0)
            crtc_info = randr.get_crtc_info(window, info.crtc, 0)
            self.monitors.append({"width": crtc_info.width, "height": crtc_info.height})

        self.log(self.monitors)
        window.destroy()

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
        new_focus = False

        if self.event.type == X.CreateNotify:
            self.log("NEW WINDOW")
            window = self.event.window
            if self.root.query_pointer().root_x > self.monitors[0]["width"]:
                x_pos = int(self.monitors[1]["width"] / 2 + self.monitors[0]["width"] - window.get_geometry().width / 2)
                y_pos = int(self.monitors[1]["height"] / 2 - window.get_geometry().height / 2)
            else:
                x_pos = int(self.monitors[0]["width"] / 2 - window.get_geometry().width / 2)
                y_pos = int(self.monitors[0]["height"] / 2 - window.get_geometry().height / 2)
            window.configure(
                stack_mode=X.Above,
                x=x_pos,
                y=y_pos
            )

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
                self.log("RESET BORDERS")
                self.set_border(child, self.colors["INACTIVE_BORDER"])

        # Set focused window border
        if self.event.type == X.FocusIn or new_focus:
            child = self.root.query_pointer().child
            self.currently_focused = child
            if child != 0:
                self.log("FOCUS")
                child.configure(stack_mode=X.Above)
                self.set_border(child, self.colors["ACTIVE_BORDER"])

        self.display.sync()

    # Check for actions until exit
    def main_loop(self):
        self.set_listeners()
        while 1:
            self.event = self.display.next_event()
            self.update_windows()

            # Move window (MOD + left click)
            if self.event.type == X.ButtonPress and self.event.child != X.NONE:
                attribute = self.event.child.get_geometry()
                self.start = self.event

            # Resize window (MOD + right click)
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
            if self.event.type == X.KeyPress and self.event.detail == int(self.keys["CYCLE"]):
                self.event.child.configure(stack_mode=X.Below)

            # Close window (MOD + Q)
            elif self.is_key(self.keys["CLOSE"]) and self.window_focused():
                self.event.child.destroy()

            # Open terminal (MOD + Enter) // X11's "enter" keysym is 0, but it's 36
            elif self.event.type == X.KeyPress and self.event.detail == int(self.keys["TERMINAL"]):
                os.system(self.programs["TERMINAL"] + " &")

            # Open dmenu (MOD + D)
            elif self.is_key(self.keys["MENU"]):
                os.system(self.programs["MENU"] + " &")

            # Exit window manager (MOD + C)
            elif self.is_key(self.keys["QUIT"]):
                self.display.close()

            elif self.event.type == X.ButtonRelease:
                self.start = None


FreedoWM = FreedoWM()
FreedoWM.main_loop()
