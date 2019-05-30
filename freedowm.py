#!/usr/bin/env python3.7

import configparser
import os

from Xlib import X, XK
from Xlib.display import Display
from Xlib.ext import randr


class FreedoWM(object):
    def __init__(self):
        """
        Initializes several class-level variables
        """
        self.config = configparser.ConfigParser()
        self.config.read(os.environ['HOME'] + "/.config/freedowm.ini")
        self.general = self.config["GENERAL"]
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
        self.tiling_windows = []
        self.start = None
        self.ignore_actions = False
        self.program_stack = []
        self.program_stack_index = -1
        self.monitors = []
        self.monitor_id = self.zero_coordinate = self.x_center = self.y_center = 0

        self.NET_WM_NAME = self.display.intern_atom('_NET_WM_NAME')
        self.NET_ACTIVE_WINDOW = self.display.intern_atom('_NET_ACTIVE_WINDOW')

        self.get_monitors()

    def set_listeners(self):
        """
        Gets executed at program start - sets the initial listener masks
        :return:
        """

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
        """
        Logging utility - only logs when it's enabled in the config
        :param message: The message being logged
        :return:
        """
        if self.general["DEBUG"] != "0":
            print(message)

    def get_monitors(self):
        """
        Gets/sets your monitor setup using the Xlib xrandr helper functions
        :return:
        """
        window = self.root.create_window(0, 0, 1, 1, 1, self.screen.root_depth)
        res = randr.get_screen_resources(window).outputs

        for i in range(self.display.screen_count() + 1):
            info = randr.get_output_info(window, res[i], 0)
            crtc_info = randr.get_crtc_info(window, info.crtc, 0)
            self.monitors.append({"width": crtc_info.width, "height": crtc_info.height})

        self.log(self.monitors)
        window.destroy()

    def is_key(self, key_name):
        """
        Checks whether a key has been pressed
        :param key_name: The key that should be checked
        :return:
        """
        return self.event.type == X.KeyPress \
               and self.event.detail == self.display.keysym_to_keycode(XK.string_to_keysym(key_name))

    def window_focused(self):
        """
        Checks whether the pointer hovers a window or the event has a child
        :return:
        """
        return hasattr(self.event, "child") and self.event.child != X.NONE or self.root.query_pointer().child != 0

    def set_border(self, child, color):
        """
        Sets a border to the requested window
        :param child: The requested window child
        :param color: The requested color as string (HEX)
        :return:
        """
        if child is not None and child is not X.NONE:
            border_color = self.colormap.alloc_named_color(color).pixel
            child.configure(border_width=int(self.general["BORDER"]))
            child.change_attributes(None, border_pixel=border_color)

    def center_window(self, window):
        if self.root.query_pointer().root_x > self.monitors[0]["width"]:
            self.monitor_id = 1
            self.zero_coordinate = self.monitors[0]["width"]
            self.x_center = round(self.monitors[1]["width"] / 2 + self.monitors[0]["width"])
            self.y_center = round(self.monitors[1]["height"] / 2)
        else:
            self.x_center = round(self.monitors[0]["width"] / 2)
            self.y_center = round(self.monitors[0]["height"] / 2)

        window.configure(
            width=round(self.monitors[self.monitor_id]["width"] / 2),
            height=round(self.monitors[self.monitor_id]["height"] / 2),
        )

        window.configure(
            x=self.x_center - round(window.get_geometry().width / 2),
            y=self.y_center - round(window.get_geometry().height / 2),
        )
        window.configure(stack_mode=X.Above)
        self.root.warp_pointer(self.x_center, self.y_center)

    def update_tiling(self):
        """
        Updated/rearranges the tiling scene
        :return:
        """
        self.log("UPDATE TILING")
        monitor = self.monitors[self.monitor_id]
        count = (len(self.tiling_windows[self.monitor_id]))
        width = 0 if count == 0 else round(monitor["width"] / count)
        for i, child in enumerate(self.root.query_tree().children):
            child.configure(
                stack_mode=X.Above,
                width=width - 2 * int(self.general["BORDER"]),
                height=monitor["height"] - 2 * int(self.general["BORDER"]),
                x=self.zero_coordinate + width * i,
                y=0,
            )
            if child not in self.tiling_windows[self.monitor_id]:
                self.tiling_windows[self.monitor_id].append(child)

    def update_windows(self):
        """
        Handles several window events
        :return:
        """

        # Configure new window
        if self.event.type == X.CreateNotify:
            if not self.ignore_actions:
                self.log("NEW WINDOW")
                window = self.event.window
                self.program_stack.append(window)
                self.program_stack_index = len(self.program_stack) - 1
                if self.tiling_state:
                    self.tiling_windows[self.monitor_id].append(window)
                    self.update_tiling()
                    monitor_width = self.monitors[self.monitor_id]["width"]
                    self.root.warp_pointer(
                        round(self.zero_coordinate + monitor_width -
                              (monitor_width / len(self.tiling_windows[self.monitor_id]) + 1) / 2),
                        self.y_center
                    )
                else:
                    self.center_window(window)
            else:
                self.ignore_actions = False

        # Remove closed window from stack
        if self.event.type == X.DestroyNotify:
            self.log("CLOSE WINDOW")
            self.program_stack.remove(self.event.window)
            if self.tiling_state:
                self.tiling_windows[self.monitor_id].remove(self.event.window)
                self.update_tiling()
            elif len(self.program_stack) > 0:
                focused_window = self.program_stack[0]
                focused_window.configure(stack_mode=X.Above)
                self.root.warp_pointer(
                    round(focused_window.get_geometry().x + focused_window.get_geometry().width / 2),
                    round(focused_window.get_geometry().y + focused_window.get_geometry().height / 2)
                )

        # Set focused window "in focus"
        if self.window_focused() and not self.ignore_actions:
            if hasattr(self.event, "child") and self.event.child != X.NONE \
                    and self.event.child != self.currently_focused:
                if self.currently_focused is not None:
                    self.log("RESET BORDER")
                    self.set_border(self.currently_focused, self.colors["INACTIVE_BORDER"])
                self.log("FOCUS BORDER")
                self.currently_focused = self.event.child
                self.set_border(self.currently_focused, self.colors["ACTIVE_BORDER"])
                self.currently_focused.configure(stack_mode=X.Above)
                self.program_stack_index = self.program_stack.index(self.currently_focused)
            elif self.root.query_pointer().child not in (self.currently_focused, X.NONE):
                if self.currently_focused is not None:
                    self.log("RESET BORDER")
                    self.set_border(self.currently_focused, self.colors["INACTIVE_BORDER"])
                self.log("FOCUS BORDER")
                self.currently_focused = self.root.query_pointer().child
                self.set_border(self.currently_focused, self.colors["ACTIVE_BORDER"])
                self.currently_focused.configure(stack_mode=X.Above)
                self.program_stack_index = self.program_stack.index(self.currently_focused)

        self.display.sync()

    def main_loop(self):
        """
        Loops until the program is closed - handles keyboard, window and mouse events
        :return:
        """
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
                    width=max(1, attribute.width + (self.start.detail == 3 and x_diff or 0)),
                    height=max(1, attribute.height + (self.start.detail == 3 and y_diff or 0)),
                    x=attribute.x + (self.start.detail == 1 and x_diff or 0),
                    y=attribute.y + (self.start.detail == 1 and y_diff or 0)
                )

            # Cycle between windows (MOD + Tab) // X11's "tab" keysym is 0, but it's 23
            if self.event.type == X.KeyPress and self.event.detail == int(self.keys["CYCLE"]) \
                    and len(self.program_stack) > 0:
                if self.program_stack_index + 1 >= len(self.program_stack):
                    self.program_stack_index = 0
                else:
                    self.program_stack_index += 1
                active_window = self.program_stack[self.program_stack_index]
                active_window.configure(stack_mode=X.Above)
                self.root.warp_pointer(
                    round(active_window.get_geometry().x + active_window.get_geometry().width / 2),
                    round(active_window.get_geometry().y + active_window.get_geometry().height / 2)
                )

            # Toggle tiling state (MOD + t)
            elif self.is_key(self.keys["TILE"]):
                if not self.tiling_state:
                    for i in range(self.display.screen_count() + 1):
                        self.tiling_windows.append([])
                    if self.window_focused():
                        self.tiling_windows[self.monitor_id].append(self.event.child)
                        self.update_tiling()
                        self.tiling_state = True
                else:
                    self.tiling_windows = []
                    self.tiling_state = False

            # Toggle maximization (MOD + M)
            elif self.is_key(self.keys["MAX"]):
                if self.window_focused():
                    full_width = self.monitors[self.monitor_id]["width"] - 2 * int(self.general["BORDER"])
                    full_height = self.monitors[self.monitor_id]["height"] - 2 * int(self.general["BORDER"])

                    if self.event.child.get_geometry().width == full_width \
                            and self.event.child.get_geometry().height == full_height \
                            and self.event.child.get_geometry().x == self.zero_coordinate \
                            and self.event.child.get_geometry().y == 0:
                        self.center_window(self.event.child)
                    else:
                        self.event.child.configure(
                            width=full_width,
                            height=full_height,
                            x=self.zero_coordinate,
                            y=0
                        )

            # Close window (MOD + Q)
            elif self.is_key(self.keys["CLOSE"]) and self.window_focused():
                self.event.child.destroy()

            # Open terminal (MOD + Enter) // X11's "enter" keysym is 0, but it's 36
            elif self.event.type == X.KeyPress and self.event.detail == int(self.keys["TERMINAL"]):
                os.system(self.programs["TERMINAL"] + " &")

            # Open dmenu (MOD + D)
            elif self.is_key(self.keys["MENU"]):
                self.ignore_actions = True
                os.system(self.programs["MENU"] + " &")

            # Exit window manager (MOD + C)
            elif self.is_key(self.keys["QUIT"]):
                self.display.close()

            elif self.event.type == X.ButtonRelease:
                self.start = None


FreedoWM = FreedoWM()
FreedoWM.main_loop()
