import pynvim
from math import sqrt

plugin_name = "imfocus"
hl_group_normal = "Normal"
default_hl_group = plugin_name + "Shadow"
default_lightness = 0.2


# global variable names
g_focus_size = plugin_name + "_size"
g_hl_group = plugin_name + "_hl_group"
g_lightness = plugin_name + "_lightness"
g_soft_shadow = plugin_name + "_soft_shadow"


def rgb_channels(color):
    color = int(color)
    r = (color >> 16) & 0xff
    g = (color >> 8) & 0xff
    b = color & 0xff
    return [r, g, b]


def blend(color_a, color_b, coeff):
    # blending coefficient 0 results in pure color_a, coefficient 1 results in pure color_b
    #  return [round(sqrt((1 - coeff) * channel_a**2 + coeff * channel_b**2))
            #  for channel_a, channel_b in zip(color_a, color_b)]
    return [round((1 - coeff) * channel_a + coeff * channel_b)
            for channel_a, channel_b in zip(color_a, color_b)]


def rgb_pack(channels):
    r, g, b = channels
    color = (((r << 8) | g) << 8) | b
    return "#{:x}".format(color)


@pynvim.plugin
class Wip:
    def __init__(self, nvim_ref):
        # do not do anything with non-trivial side-effects here! seriously.
        self.nvim = nvim_ref
        self.hl_src = None
        # plugin settings
        self.focus_size = None
        self.hl_group = None
        self.lightness = None
        self.has_soft_shadow = None
        # state
        self.window = None
        self.cursor_line = None
        self.match_ids = set()

    @pynvim.autocmd("InsertEnter", pattern="*", sync=True)
    def on_insert_enter(self):
        if self.focus_size is None:
            self.init()
        self.focus()

    @pynvim.autocmd("InsertLeave", pattern="*", sync=True)
    def on_insert_leave(self):
        self.window = None
        self.cursor_line = None
        self.clear_hl()

    @pynvim.autocmd("CursorMovedI", pattern="*", sync=True)
    def on_cursor_moved(self):
        self.focus()

    def init(self):
        # this function is needed because there should not be any nvim interaction in __init__()
        self.focus_size = max(0, self.nvim.vars.get(g_focus_size, 0))
        self.set_hl_group()
        # hard shadow by default
        self.has_soft_shadow = self.nvim.vars.get(g_soft_shadow, 0)
        self.hl_src = self.nvim.new_highlight_source()

    def set_hl_group(self):
        self.hl_group = self.nvim.vars.get(g_hl_group, None)
        if self.hl_group is None:
            self.hl_group = default_hl_group
        if not self.nvim.funcs.hlexists(self.hl_group):
            self.highlight()

    def highlight(self):
        # get Normal foreground color and blend into background
        rgb_hl = self.get_option("gui_running", False) or self.get_option("termguicolors", False)
        term_hl = (self.get_option("t_Co") == 256)
        if not rgb_hl and not term_hl:
            self.nvim.err_write("<plugin_name> is disabled, only rgb or 256 colors are supported\n")
            # TODO disable plugin
            return

        normal_hl_map = self.nvim.api.get_hl_by_name(hl_group_normal, rgb_hl)
        fg = normal_hl_map.get("foreground")
        bg = normal_hl_map.get("background")
        if fg is None or bg is None:
            self.nvim.err_write("<plugin_name> is disabled, Normal colors undefined\n")
            # TODO disable plugin
            return

        # blend shadow color
        self.lightness = self.nvim.vars.get(g_lightness, default_lightness)
        if rgb_hl:
            shadow_color = rgb_pack(blend(rgb_channels(bg), rgb_channels(fg), self.lightness))
        else:
            # TODO cterm case, steal from junegunn/limelight.vim
            shadow_color = "#444444"
        self.nvim.funcs.execute("hi {} guifg={}".format(self.hl_group, shadow_color))

    def clear_hl(self):
        for match_id in self.match_ids:
            self.nvim.funcs.matchdelete(match_id)
        self.match_ids.clear()

    def focus(self):
        # on_insert_enter/leave are asynchronous handlers
        # this can lead to race conditions:
        #     on_insert_leave deletes self.window while at the same time on_insert_enter already set
        #     it; then on_insert_enter tries to use invalid window
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

    def get_option(self, name, default=None):
        try:
            option = self.nvim.api.get_option(name)
        except pynvim.api.nvim.NvimError:
            option = default
        return option

