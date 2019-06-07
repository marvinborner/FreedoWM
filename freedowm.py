#!/usr/bin/env python3.7

import configparser
import os
import sys

from Xlib import X, XK
from Xlib import error
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
        self.shift_mask = False

        self.display = Display()
        self.screen = self.display.screen()
        self.root = self.screen.root
        self.event = self.display.next_event()
        self.colormap = self.screen.default_colormap
        self.currently_focused = None
        self.tiling_state = False
        self.tiling_windows = []
        self.start = None
        self.ignore_actions = self.new_bar = False
        self.startup = True
        self.program_stack = []
        self.program_stack_index = self.bar = -1
        self.current_tag = 1
        self.monitors = []
        self.monitor_id = self.zero_coordinate = self.x_center = self.y_center = 0

        # Set cursor
        font = self.display.open_font('cursor')
        cursor = font.create_glyph_cursor(font, int(self.general["CURSOR"]), int(self.general["CURSOR"]) + 1,
                                          (65535, 65535, 65535), (0, 0, 0))
        self.root.change_attributes(cursor=cursor)

        self.get_monitors()
        self.set_listeners()
        self.root.warp_pointer(0, 0)

    def set_listeners(self):
        """
        Gets executed at program start - sets the initial listener masks
        :return:
        """

        # Listen for window changes
        self.root.change_attributes(
            event_mask=X.PropertyChangeMask |
                       X.FocusChangeMask |
                       X.StructureNotifyMask |
                       X.SubstructureNotifyMask |
                       X.PointerMotionMask
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

    def to_key(self, key_name):
        """
        Returns the keycode of the requested key
        :param key_name: The key as string (e.g. "T")
        :return:
        """
        return self.display.keysym_to_keycode(XK.string_to_keysym(key_name))

    def is_key(self, key_name):
        """
        Checks whether a key has been pressed
        :param key_name: The key that should be checked
        :return:
        """
        return self.event.type == X.KeyPress and self.event.detail == self.to_key(key_name)

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

    def toggle_bar(self):
        """
        Toggles the status bar on the current monitor
        :return:
        """
        if self.bar == -1:
            self.new_bar = True
            self.bar = self.root.create_window(
                self.zero_coordinate,  # x
                0,  # y
                self.monitors[self.monitor_id]["width"],  # width
                15,  # height
                0,  # border
                X.CopyFromParent, X.RetainPermanent, X.CopyFromParent,
                background_pixel=self.screen.black_pixel
            )
            self.bar.change_attributes(override_redirect=True)
            self.bar.map()
        else:
            self.bar.destroy()
            self.bar = -1

    def center_window(self, window):
        try:
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
        except Exception:
            self.log("GPU OVERFLOW!?")

    def update_tiling(self):
        """
        Updated/rearranges the tiling scene
        :return:
        """
        self.log("UPDATE TILING")
        monitor = self.monitors[self.monitor_id]
        count = len(self.tiling_windows[self.monitor_id])
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

    def update_tags(self):
        """
        Updates the appearance of different tags/desktops
        :return:
        """
        for program in self.program_stack:
            if program["tag"] == self.current_tag:
                self.log("SHOW WINDOW")
                program["window"].map()
            else:
                self.log("HIDE WINDOW")
                program["window"].unmap()

    def update_windows(self):
        """
        Handles several window events
        :return:
        """

        # Configure new window
        if self.event.type == X.CreateNotify:
            try:
                if not self.ignore_actions and not self.new_bar:
                    self.log("NEW WINDOW")
                    window = self.event.window
                    self.program_stack.append({"window": window, "tag": self.current_tag})
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
                elif self.new_bar:
                    self.new_bar = False
            except (error.BadWindow, error.BadDrawable):
                self.log("BAD WINDOW OR DRAWABLE!")

        # Remove closed window from stack
        if self.event.type == X.DestroyNotify:
            try:
                if not self.ignore_actions \
                        and {"window": self.event.window, "tag": self.current_tag} in self.program_stack:
                    self.log("CLOSE WINDOW")
                    if {"window": self.event.window, "tag": self.current_tag} in self.program_stack:
                        self.program_stack.remove({"window": self.event.window, "tag": self.current_tag})
                    if self.tiling_state:
                        self.tiling_windows[self.monitor_id].remove(self.event.window)
                        self.update_tiling()
                    elif len(self.program_stack) > 0:
                        focused_window = self.program_stack[0]["window"]
                        focused_window.configure(stack_mode=X.Above)
                        self.root.warp_pointer(
                            round(focused_window.get_geometry().x + focused_window.get_geometry().width / 2),
                            round(focused_window.get_geometry().y + focused_window.get_geometry().height / 2)
                        )
                elif self.ignore_actions:
                    self.ignore_actions = False
            except (error.BadWindow, error.BadDrawable):
                self.log("BAD WINDOW OR DRAWABLE!")

        # Set focused window "in focus"
        if self.window_focused() and not self.ignore_actions:
            if hasattr(self.event, "child") and self.event.child != X.NONE \
                    and self.event.child != self.currently_focused \
                    and {"window": self.event.child, "tag": self.current_tag} in self.program_stack:
                if self.currently_focused is not None:
                    self.log("RESET BORDER")
                    self.set_border(self.currently_focused, self.colors["INACTIVE_BORDER"])
                self.log("FOCUS BORDER")
                self.currently_focused = self.event.child
                self.set_border(self.currently_focused, self.colors["ACTIVE_BORDER"])
                self.currently_focused.configure(stack_mode=X.Above)
                self.program_stack_index = self.program_stack.index(
                    {"window": self.currently_focused, "tag": self.current_tag}
                )
            elif self.root.query_pointer().child not in (self.currently_focused, X.NONE) \
                    and {"window": self.root.query_pointer().child, "tag": self.current_tag} in self.program_stack:
                if self.currently_focused is not None:
                    self.log("RESET BORDER")
                    self.set_border(self.currently_focused, self.colors["INACTIVE_BORDER"])
                self.log("FOCUS BORDER")
                self.currently_focused = self.root.query_pointer().child
                self.set_border(self.currently_focused, self.colors["ACTIVE_BORDER"])
                self.currently_focused.configure(stack_mode=X.Above)
                self.program_stack_index = self.program_stack.index(
                    {"window": self.currently_focused, "tag": self.current_tag}
                )

        # Update current monitor
        if self.event.type == X.NotifyPointerRoot or self.startup:
            self.startup = False
            previous = self.monitor_id
            if self.root.query_pointer().root_x > self.monitors[0]["width"]:
                self.monitor_id = 1
                self.zero_coordinate = self.monitors[0]["width"]
                self.x_center = round(self.monitors[1]["width"] / 2 + self.monitors[0]["width"])
                self.y_center = round(self.monitors[1]["height"] / 2)
            else:
                self.monitor_id = 0
                self.x_center = round(self.monitors[0]["width"] / 2)
                self.y_center = round(self.monitors[0]["height"] / 2)
            if previous != self.monitor_id:
                self.log("UPDATE MONITOR ID: " + str(self.monitor_id))

        self.display.sync()

    def main_loop(self):
        """
        Loops until the program is closed - handles keyboard, window and mouse events
        :return:
        """
        while 1:
            self.event = self.display.next_event()
            self.update_windows()

            # Move window (MOD + left click)
            if self.event.type == X.ButtonPress and self.event.child != X.NONE \
                    and {"window": self.event.child, "tag": self.current_tag} in self.program_stack:
                attribute = self.event.child.get_geometry()
                self.start = self.event

            # Resize window (MOD + right click)
            elif self.event.type == X.MotionNotify and self.start \
                    and {"window": self.event.child, "tag": self.current_tag} in self.program_stack:
                x_diff = self.event.root_x - self.start.root_x
                y_diff = self.event.root_y - self.start.root_y
                self.start.child.configure(
                    width=max(1, attribute.width + (self.start.detail == 3 and x_diff or 0)),
                    height=max(1, attribute.height + (self.start.detail == 3 and y_diff or 0)),
                    x=attribute.x + (self.start.detail == 1 and x_diff or 0),
                    y=attribute.y + (self.start.detail == 1 and y_diff or 0)
                )

            # Toggle the shift mask identifier
            elif (self.event.type == X.KeyPress or self.event.type == X.KeyRelease) and self.event.detail == 50:
                self.shift_mask = not self.shift_mask

            # Cycle between windows (MOD + Tab) // X11's "tab" keysym is 0, but it's 23
            elif self.event.type == X.KeyPress and self.event.detail == int(self.keys["CYCLE"]) \
                    and len(self.program_stack) > 0:
                if self.program_stack_index + 1 >= len(self.program_stack):
                    self.program_stack_index = 0
                else:
                    self.program_stack_index += 1
                self.current_tag = self.program_stack[self.program_stack_index]["tag"]
                self.update_tags()
                active_window = self.program_stack[self.program_stack_index]["window"]
                active_window.configure(stack_mode=X.Above)
                self.root.warp_pointer(
                    round(active_window.get_geometry().x + active_window.get_geometry().width / 2),
                    round(active_window.get_geometry().y + active_window.get_geometry().height / 2)
                )

            # Toggle tiling state (MOD + T)
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

            # Center window (MOD + C)
            elif self.is_key(self.keys["CENTER"]) and self.window_focused():
                self.center_window(self.event.child)

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

            # Toggle status bar (MOD + B)
            elif self.is_key(self.keys["BAR"]):
                self.toggle_bar()

            # Exit window manager (MOD + P)
            elif self.is_key(self.keys["QUIT"]):
                self.display.close()
                sys.exit()

            # Display tag or move window to tag with shift mask
            elif self.event.type == X.KeyPress and self.event.detail in \
                    [self.to_key(self.keys["TAG0"]), self.to_key(self.keys["TAG1"]), self.to_key(self.keys["TAG2"]),
                     self.to_key(self.keys["TAG3"]), self.to_key(self.keys["TAG4"]), self.to_key(self.keys["TAG5"]),
                     self.to_key(self.keys["TAG6"]), self.to_key(self.keys["TAG7"]), self.to_key(self.keys["TAG8"])]:
                new_tag = int(XK.keysym_to_string(self.display.keycode_to_keysym(self.event.detail, 0)))
                if not self.shift_mask:
                    self.log("SHIFT TAG TO " + str(self.current_tag))
                    self.current_tag = new_tag
                    self.update_tags()
                elif self.window_focused():
                    self.log("MODIFY WINDOW TAG " + str(self.current_tag))
                    self.program_stack[self.program_stack_index]["tag"] = new_tag
                    self.update_tags()

            elif self.event.type == X.ButtonRelease:
                self.start = None


FreedoWM = FreedoWM()
FreedoWM.main_loop()
