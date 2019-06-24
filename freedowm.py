#!/usr/bin/env python3.7

import configparser
import os
import sys

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
        self.shift_mask = False

        self.display = Display()
        self.screen = self.display.screen()
        self.root = self.screen.root
        self.event = self.display.next_event()
        self.colormap = self.screen.default_colormap
        self.currently_focused = None
        self.tiling_state = False
        self.start = None
        self.ignore_actions = False
        self.startup = True
        self.program_stack = []
        self.program_stack_index = -1
        self.current_tag = 1
        self.previous_tag = 1
        self.monitors = self.windows_on_monitor = []
        self.current_monitor = self.zero_coordinate = self.x_center = self.y_center = 0
        self.monitor_count = 1

        self.screen.override_redirect = True
        self.set_cursor()
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
            override_redirect=True,
            event_mask=X.PropertyChangeMask |
                       X.FocusChangeMask |
                       X.StructureNotifyMask |
                       X.SubstructureNotifyMask |
                       X.SubstructureRedirectMask |
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

    def set_cursor(self):
        """
        Sets the cursor according to the config
        :return:
        """
        if int(self.general["CURSOR"]) != -1:
            font = self.display.open_font('cursor')
            cursor = font.create_glyph_cursor(font, int(self.general["CURSOR"]), int(self.general["CURSOR"]) + 1, (65535, 65535, 65535), (0, 0, 0))
            self.root.change_attributes(cursor=cursor)
        else:
            os.system("xsetroot -cursor_name left_ptr")

    def get_monitors(self):
        """
        Gets/sets your monitor setup using the Xlib xrandr helper functions
        :return:
        """
        window = self.root.create_window(0, 0, 1, 1, 1, self.screen.root_depth)
        res = randr.get_screen_resources(window).outputs
        self.monitor_count = len(res)
        for i in range(self.monitor_count):
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

    def focus_window(self, window):
        self.set_border(self.currently_focused, self.colors["INACTIVE_BORDER"])
        self.currently_focused = window
        self.set_border(self.currently_focused, self.colors["ACTIVE_BORDER"])
        self.currently_focused.configure(stack_mode=X.Above)

    def center_window(self, window):
        window.configure(
            width=round(self.monitors[self.current_monitor]["width"] / 2),
            height=round(self.monitors[self.current_monitor]["height"] / 2),
        )

        window.configure(
            x=self.x_center - round(window.get_geometry().width / 2),
            y=self.y_center - round(window.get_geometry().height / 2),
        )
        window.configure(stack_mode=X.Above)
        window.map()
        self.root.warp_pointer(self.x_center, self.y_center)

    def update_tiling(self):
        """
        Updates/rearranges the tiling scene
        :return:
        """
        self.windows_on_monitor = [x for x in self.program_stack if x["monitor"] == self.current_monitor and x["tag"] == self.current_tag]
        self.log("UPDATE TILING")
        monitor = self.monitors[self.current_monitor]
        count = len(self.windows_on_monitor)
        width = 0 if count == 0 else round(monitor["width"] / count)
        for i, child in enumerate(self.windows_on_monitor):
            child["window"].configure(
                stack_mode=X.Above,
                width=width - 2 * int(self.general["BORDER"]),
                height=monitor["height"] - 2 * int(self.general["BORDER"]),
                x=self.zero_coordinate + width * i,
                y=0,
            )

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
        if self.event.type == X.MapRequest:
            if not self.ignore_actions:
                self.log("NEW WINDOW")
                window = self.event.window
                self.program_stack.append({"window": window, "tag": self.current_tag, "monitor": self.current_monitor})
                self.program_stack_index = len(self.program_stack) - 1
                if self.tiling_state:
                    self.update_tiling()
                    monitor_width = self.monitors[self.current_monitor]["width"]
                    self.root.warp_pointer(
                        round(self.zero_coordinate + monitor_width - (monitor_width / len(self.windows_on_monitor) + 1) / 2),
                        self.y_center
                    )
                else:
                    self.center_window(window)
                self.focus_window(window)
                window.map()

        # Remove closed window from stack
        if self.event.type == X.DestroyNotify:
            if not self.ignore_actions and {"window": self.event.window, "tag": self.current_tag, "monitor": self.current_monitor} \
                    in self.program_stack:
                self.log("CLOSE WINDOW")
                if {"window": self.event.window, "tag": self.current_tag, "monitor": self.current_monitor} in self.program_stack:
                    self.program_stack.remove({"window": self.event.window, "tag": self.current_tag, "monitor": self.current_monitor})
                if self.tiling_state:
                    self.update_tiling()
                elif len(self.program_stack) > 0:
                    focused_window = self.program_stack[-1]["window"]
                    self.focus_window(focused_window)
                    self.root.warp_pointer(
                        round(focused_window.get_geometry().x + focused_window.get_geometry().width / 2),
                        round(focused_window.get_geometry().y + focused_window.get_geometry().height / 2)
                    )
            elif self.ignore_actions:
                self.ignore_actions = False

        # Set focused window "in focus"
        if self.window_focused() and not self.ignore_actions:
            # self.log(self.root.query_pointer().__dict__)  # TODO: Fix hover-focusing of GTK/QT applications
            if hasattr(self.event, "child") and self.event.child != X.NONE and self.event.child != self.currently_focused \
                    and {"window": self.event.child, "tag": self.current_tag, "monitor": self.current_monitor} in self.program_stack:
                if self.currently_focused is not None:
                    self.log("RESET BORDER")
                    self.set_border(self.currently_focused, self.colors["INACTIVE_BORDER"])
                self.log("FOCUS BORDER")
                self.focus_window(self.event.child)
                self.program_stack_index = self.program_stack.index(
                    {"window": self.currently_focused, "tag": self.current_tag, "monitor": self.current_monitor}
                )
            elif self.root.query_pointer().child not in (self.currently_focused, X.NONE) \
                    and {"window": self.root.query_pointer().child, "tag": self.current_tag, "monitor": self.current_monitor} in self.program_stack:
                if self.currently_focused is not None:
                    self.log("RESET BORDER")
                    self.set_border(self.currently_focused, self.colors["INACTIVE_BORDER"])
                self.log("FOCUS BORDER")
                self.focus_window(self.root.query_pointer().child)
                self.program_stack_index = self.program_stack.index(
                    {"window": self.currently_focused, "tag": self.current_tag, "monitor": self.current_monitor}
                )
            self.display.set_input_focus(self.currently_focused, X.RevertToPointerRoot, 0)

        # Update current monitor
        if self.event.type == X.NotifyPointerRoot or self.startup:
            self.startup = False
            previous = self.current_monitor
            if self.root.query_pointer().root_x > self.monitors[0]["width"]:
                self.current_monitor = 1
                self.zero_coordinate = self.monitors[0]["width"]
                self.x_center = round(self.monitors[1]["width"] / 2 + self.monitors[0]["width"])
                self.y_center = round(self.monitors[1]["height"] / 2)
            else:
                self.current_monitor = 0
                self.x_center = round(self.monitors[0]["width"] / 2)
                self.y_center = round(self.monitors[0]["height"] / 2)
            if previous != self.current_monitor:
                self.log("UPDATE MONITOR ID: " + str(self.current_monitor))

    def main_loop(self):
        """
        Loops until the program is closed - handles keyboard, window and mouse events
        :return:
        """
        while 1:
            self.event = self.display.next_event()
            self.update_windows()

            # Move window (MOD + left click)
            # TODO: Update monitor index after move to different monitor
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

            # Toggle the shift mask identifier
            elif (self.event.type == X.KeyPress or self.event.type == X.KeyRelease) and self.event.detail == 50:
                self.shift_mask = not self.shift_mask

            # Cycle between windows (MOD + J/K)
            elif (self.is_key(self.keys["CYCLEUP"]) or self.is_key(self.keys["CYCLEDOWN"])) and len(self.program_stack) > 0:
                if self.program_stack_index + 1 >= len(self.program_stack) and self.is_key(self.keys["CYCLEUP"]):
                    self.program_stack_index = 0
                elif self.is_key(self.keys["CYCLEUP"]):
                    self.program_stack_index += 1
                elif self.is_key(self.keys["CYCLEDOWN"]):
                    self.program_stack_index -= 1
                self.current_tag = self.program_stack[self.program_stack_index]["tag"]
                self.current_monitor = self.program_stack[self.program_stack_index]["monitor"]
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
                    if self.window_focused():
                        self.update_tiling()
                        self.tiling_state = True
                else:
                    self.tiling_state = False

            # Toggle maximization (MOD + M)
            elif self.is_key(self.keys["MAX"]):
                if self.window_focused():
                    full_width = self.monitors[self.current_monitor]["width"] - 2 * int(self.general["BORDER"])
                    full_height = self.monitors[self.current_monitor]["height"] - 2 * int(self.general["BORDER"])

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
            elif self.is_key(self.keys["CLOSE"]) and self.window_focused() and self.event.child != X.NONE:
                self.event.child.destroy_sub_windows()
                self.event.child.destroy()

            # Open terminal (MOD + Enter) // X11's "enter" keysym is 0, but it's 36
            elif self.event.type == X.KeyPress and self.event.detail == int(self.keys["TERMINAL"]):
                os.system(self.programs["TERMINAL"] + " &")

            # Switch to last used tag/desktop (MOD + Tab) // X11's "tab" keysym is 0, but it's 23
            elif self.event.type == X.KeyPress and self.event.detail == int(self.keys["TAGSWAP"]):
                previous = self.previous_tag
                self.previous_tag = self.current_tag
                self.current_tag = previous
                self.update_tags()

            # Open dmenu (MOD + D)
            elif self.is_key(self.keys["MENU"]):
                self.ignore_actions = True
                os.system(self.programs["MENU"] + " &")

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
if FreedoWM.general["DEBUG"] == "1":
    FreedoWM.main_loop()
else:
    try:
        FreedoWM.main_loop()
    except Exception:
        pass
