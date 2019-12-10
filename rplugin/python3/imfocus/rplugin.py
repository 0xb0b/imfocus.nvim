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


class Settings:
    def __init__(self, nvim):
        self.hl_src = nvim.new_highlight_source()
        self.focus_size = max(0, nvim.vars.get(g_focus_size, 0))

        # hard shadow by default
        self.has_soft_shadow = nvim.vars.get(g_soft_shadow, 0)

        self.lightness = None

        # set up highlight group
        self.hl_group = nvim.vars.get(g_hl_group, None)
        if self.hl_group is None:
            self.hl_group = default_hl_group
        if not nvim.funcs.hlexists(self.hl_group):
            highlight(nvim, self)


class ScreenState:
    def __init__(self):
        self.cursor_line = None
        self.match_ids = set()


class PlugImpl:
    def __init__(self, nvim):
        self.enabled = False
        self.state = ScreenState()
        reset(nvim, self)


def highlight(nvim, settings):
    rgb_hl = (get_option(nvim, "gui_running", False)
              or get_option(nvim, "termguicolors", False))
    term_hl = (get_option(nvim, "t_Co") == 256)
    if not rgb_hl and not term_hl:
        nvim.err_write("{} is disabled, only rgb or 256 terminal "
            "colors are supported\n".format(plugin_name))
        settings = None
        return

    # get Normal foreground color and blend into background to get shadow color
    normal_hl_map = nvim.api.get_hl_by_name(hl_group_normal, rgb_hl)
    fg = normal_hl_map.get("foreground")
    bg = normal_hl_map.get("background")
    if fg is None or bg is None:
        nvim.err_write("{} is disabled, Normal colors undefined\n"
            .format(plugin_name))
        settings = None
        return
    settings.lightness = nvim.vars.get(g_lightness, default_lightness)
    if rgb_hl:
        shadow_color = rgb_to_vim_color(rgb_blend(rgb_decompose(bg),
            rgb_decompose(fg), settings.lightness))
        nvim.funcs.execute("highlight {} guifg={}"
            .format(settings.hl_group, shadow_color))
    else:
        shadow_color = rgb_to_closest_term(rgb_blend(term_to_rgb(bg),
            term_to_rgb(fg), settings.lightness))
        nvim.funcs.execute("highlight {} ctermfg={}"
            .format(settings.hl_group, shadow_color))


def get_option(nvim, name, default=None):
    try:
        option = nvim.api.get_option(name)
    except NvimError:
        option = default
    return option


def reset(nvim, plugin):
    plugin.settings = Settings(nvim)
    if plugin.settings is not None:
        plugin.state.enabled = True


def is_enabled(plugin):
    return plugin.state.enabled


def enable(nvim, plugin):
    if not is_enabled(plugin):
        reset(nvim, plugin)


def disable(nvim, plugin):
    if is_enabled(plugin):
        unfocus(nvim, plugin.state)
        nvim.funcs.execute("highlight clear {}".format(plugin.settings.hl_group))
        plugin.state.enabled = False
        plugin.settings = None


def focus(nvim, plugin):
    if not is_enabled(plugin):
        return
    cursor_line = nvim.current.window.cursor[0]
    if plugin.state.cursor_line != cursor_line:
        plugin.state.cursor_line = cursor_line

        # first visible line in window
        top_line = nvim.funcs.line("w0")
        # last visible line in window
        bottom_line = nvim.funcs.line("w$")

        # first line in focus
        focus_start = max(top_line, cursor_line - plugin.settings.focus_size)
        # last line in focus
        focus_end = min(bottom_line, cursor_line + plugin.settings.focus_size)

        clear_highlight(nvim, plugin.state)
        for line in range(top_line, focus_start):
            match_id = nvim.funcs.matchaddpos(plugin.settings.hl_group, [line])
            plugin.state.match_ids.add(match_id)
        for line in range(focus_end + 1, bottom_line + 1):
            match_id = nvim.funcs.matchaddpos(plugin.settings.hl_group, [line])
            plugin.state.match_ids.add(match_id)


def unfocus(nvim, plugin):
    if not is_enabled(plugin):
        return
    plugin.state.cursor_line = None
    clear_highlight(nvim, plugin.state)


def clear_highlight(nvim, state):
    for match_id in state.match_ids:
        nvim.funcs.matchdelete(match_id)
    state.match_ids.clear()


def debug(nvim, msg):
    nvim.out_write(msg + "\n")

