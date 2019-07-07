from math import sqrt
from pynvim.api.nvim import NvimError
from imfocus.color import (rgb_blend, rgb_decompose, rgb_to_vim_color,
                           term_to_rgb, rgb_to_closest_term)


plugin_name = __name__.partition(".")[0]
hl_group_normal = "Normal"
default_hl_group = plugin_name + "Shadow"
default_lightness = 0.2

# global variable names
g_focus_size = plugin_name + "_size"
g_hl_group = plugin_name + "_hl_group"
g_lightness = plugin_name + "_lightness"
g_soft_shadow = plugin_name + "_soft_shadow"


class RemotePlugin:
    def __init__(self, nvim):
        self.nvim = nvim
        self.hl_src = self.nvim.new_highlight_source()

        # plugin settings
        self.focus_size = max(0, self.nvim.vars.get(g_focus_size, 0))
        # hard shadow by default
        self.has_soft_shadow = self.nvim.vars.get(g_soft_shadow, 0)
        self.lightness = None
        self.set_hl_group()

        # state
        self.window = None
        self.cursor_line = None
        self.match_ids = set()

    def set_hl_group(self):
        self.hl_group = self.nvim.vars.get(g_hl_group, None)
        if self.hl_group is None:
            self.hl_group = default_hl_group
        if not self.nvim.funcs.hlexists(self.hl_group):
            self.highlight()

    def highlight(self):
        rgb_hl = (self.get_option("gui_running", False)
                  or self.get_option("termguicolors", False))
        term_hl = (self.get_option("t_Co") == 256)
        if not rgb_hl and not term_hl:
            self.nvim.err_write("{} is disabled, only rgb or 256 terminal "
                "colors are supported\n".format(plugin_name))
            # this effectively disables plugin
            self.hl_group = None
            return

        # get Normal foreground color and blend into background
        normal_hl_map = self.nvim.api.get_hl_by_name(hl_group_normal, rgb_hl)
        fg = normal_hl_map.get("foreground")
        bg = normal_hl_map.get("background")
        if fg is None or bg is None:
            self.nvim.err_write("{} is disabled, Normal colors undefined\n"
                .format(plugin_name))
            # this effectively disables plugin
            self.hl_group = None
            return

        # blend shadow color
        self.lightness = self.nvim.vars.get(g_lightness, default_lightness)
        if rgb_hl:
            shadow_color = rgb_to_vim_color(rgb_blend(rgb_decompose(bg),
                rgb_decompose(fg), self.lightness))
            self.nvim.funcs.execute("hi {} guifg={}"
                .format(self.hl_group, shadow_color))
        else:
            shadow_color = rgb_to_closest_term(rgb_blend(term_to_rgb(bg),
                term_to_rgb(fg), self.lightness))
            self.nvim.funcs.execute("hi {} ctermfg={}"
                    .format(self.hl_group, shadow_color))

    def ready(self):
        return self.hl_group is not None

    def focus(self):
        # on_insert_enter/leave are asynchronous handlers
        # this can lead to race conditions:
        #     on_insert_leave deletes self.window while at the same time
        #     on_insert_enter already set it;
        #     then on_insert_enter tries to use invalid window
        # how to synchronize?
        #     the simplest solution is sync=True in handlers

        if self.window is None:
            self.window = self.nvim.current.window

        cursor_line = self.window.cursor[0]
        if self.cursor_line != cursor_line:
            self.cursor_line = cursor_line

            # first visible line in window
            top_line = self.nvim.funcs.line("w0")
            # last visible line in window
            bottom_line = self.nvim.funcs.line("w$")

            # first line in focus
            focus_start = max(top_line, cursor_line - self.focus_size)
            # last line in focus
            focus_end = min(bottom_line, cursor_line + self.focus_size)

            self.clear_hl()
            for line in range(top_line, focus_start):
                match_id = self.nvim.funcs.matchaddpos(self.hl_group, [line])
                self.match_ids.add(match_id)
            for line in range(focus_end + 1, bottom_line + 1):
                match_id = self.nvim.funcs.matchaddpos(self.hl_group, [line])
                self.match_ids.add(match_id)

    def unfocus(self):
        self.window = None
        self.cursor_line = None
        self.clear_hl()

    def clear_hl(self):
        for match_id in self.match_ids:
            self.nvim.funcs.matchdelete(match_id)
        self.match_ids.clear()

    def get_option(self, name, default=None):
        try:
            option = self.nvim.api.get_option(name)
        except NvimError:
            option = default
        return option

    def debug(self, msg):
        self.nvim.out_write(msg + "\n")

