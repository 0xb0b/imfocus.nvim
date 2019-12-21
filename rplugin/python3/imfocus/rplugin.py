from math import sqrt
from pynvim.api.nvim import NvimError
from imfocus.color import (rgb_blend, rgb_decompose, rgb_to_vim_color,
                           term_to_rgb, rgb_to_closest_term)


plugin_name = __name__.partition(".")[0]
hl_group_normal = "Normal"
default_hl_group = plugin_name + "Shadow"
default_min_lightness = 0.2
shades_num = 8

# global variable names
g_focus_size = plugin_name + "_size"
g_soft_shadow_size = plugin_name + "_soft_shadow_size"
g_hl_group = plugin_name + "_hl_group"
g_min_lightness = plugin_name + "_min_lightness"


class Settings:
    def __init__(self, nvim):
        self.hl_src = nvim.new_highlight_source()

        # number of lines in focus is (2 * focus_size + 1)
        self.focus_size = max(0, nvim.vars.get(g_focus_size, 0))

        # soft shadow size is the number of the lines with lighter shades
        # then the complete shadow on each side of the lines in focus
        # hard shadow by default
        self.soft_shadow_size = max(0, nvim.vars.get(g_soft_shadow_size, 0))

        # set up highlight groups for the shadow
        # multiple groups are needed for the soft shadow
        # 0th element is the complete shadow group and the others correspond to
        # the lighter shades
        self.hl_groups = [None] * shades_num
        self.hl_groups[0] = nvim.vars.get(g_hl_group, None)
        if self.hl_groups[0] is None:
            self.hl_groups[0] = default_hl_group
        for i in range(1, shades_num):
            self.hl_groups[i] = self.hl_groups[0] + str(i)

        # precalculate soft shadow highlights
        # TODO linear for now
        self.soft_shadow_hl_groups = [None] * self.soft_shadow_size
        for i in range(self.soft_shadow_size):
            self.soft_shadow_hl_groups[i] = self.hl_groups[
                round((shades_num - 1) * (self.soft_shadow_size - i)
                    / (self.soft_shadow_size + 1))]

        if not highlight(nvim, self):
            self.hl_groups = []


class ScreenState:
    def __init__(self):
        self.enabled = False
        self.cursor_line = None
        self.match_ids = set()


class PlugImpl:
    def __init__(self, nvim):
        self.state = ScreenState()
        reset(nvim, self)


def highlight(nvim, settings):
    is_term_hl = (get_option(nvim, "t_Co") == 256)
    is_rgb_hl = (get_option(nvim, "gui_running", False)
                 or get_option(nvim, "termguicolors", False))
    if not (is_term_hl or is_rgb_hl):
        nvim.err_write(f"{plugin_name} is disabled, only rgb or 256 terminal "
            "colors are supported\n")
        return False

    # get Normal foreground color and blend into background to get the shadow
    # color
    normal_hl_map = nvim.api.get_hl_by_name(hl_group_normal, is_rgb_hl)
    fg = normal_hl_map.get("foreground")
    bg = normal_hl_map.get("background")
    if fg is None or bg is None:
        nvim.err_write(f"{plugin_name} is disabled, Normal colors undefined\n")
        return False
    fg_rgb = rgb_decompose(fg) if is_rgb_hl else term_to_rgb(fg)
    bg_rgb = rgb_decompose(bg) if is_rgb_hl else term_to_rgb(bg)

    min_lightness = nvim.vars.get(g_min_lightness, default_min_lightness)
    for i in range(shades_num):
        if nvim.funcs.hlexists(settings.hl_groups[i]):
            nvim.funcs.execute(f"highlight clear {settings.hl_groups[i]}")
        shadow_rgb = rgb_blend(bg_rgb, fg_rgb,
            min_lightness + (1.0 - min_lightness) * i / shades_num)
        if is_rgb_hl:
            nvim.funcs.execute(
                f"highlight {settings.hl_groups[i]} guifg={rgb_to_vim_color(shadow_rgb)}")
        else:
            nvim.funcs.execute(
                f"highlight {settings.hl_groups[i]} ctermfg={rgb_to_closest_term(shadow_rgb)}")
    return True


def get_option(nvim, name, default=None):
    try:
        option = nvim.api.get_option(name)
    except NvimError:
        option = default
    return option


def reset(nvim, plugin):
    plugin.settings = Settings(nvim)
    if plugin.settings.hl_groups:
        plugin.state.enabled = True


def is_enabled(plugin):
    return plugin.state.enabled


def enable(nvim, plugin):
    if not is_enabled(plugin):
        reset(nvim, plugin)


def disable(nvim, plugin):
    if is_enabled(plugin):
        unfocus(nvim, plugin.state)
        for hl_group in plugin.settings.hl_groups:
            nvim.funcs.execute(f"highlight clear {hl_group}")
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

        # soft shadow counting up from the lines in focus
        top_soft_shadow_start = cursor_line - plugin.settings.focus_size - 1
        top_soft_shadow_end = max(top_line,
            top_soft_shadow_start - plugin.settings.soft_shadow_size + 1)

        # soft shadow counting down from the lines in focus
        bottom_soft_shadow_start = cursor_line + plugin.settings.focus_size + 1
        bottom_soft_shadow_end = min(bottom_line,
            bottom_soft_shadow_start + plugin.settings.soft_shadow_size - 1)

        clear_highlight(nvim, plugin.state)

        # shadow from the top line to the top part of the soft shadow
        for line in range(top_line, top_soft_shadow_end):
            match_id = nvim.funcs.matchaddpos(plugin.settings.hl_groups[0], [line])
            plugin.state.match_ids.add(match_id)

        # TODO join top and bottom part of the soft shadow
        # top part of the soft shadow
        index = 0
        for line in range(top_soft_shadow_start, top_soft_shadow_end - 1, -1):
            match_id = nvim.funcs.matchaddpos(
                plugin.settings.soft_shadow_hl_groups[index], [line])
            plugin.state.match_ids.add(match_id)
            index += 1

        # bottom part of the soft shadow
        index = 0
        for line in range(bottom_soft_shadow_start, bottom_soft_shadow_end + 1):
            match_id = nvim.funcs.matchaddpos(
                plugin.settings.soft_shadow_hl_groups[index], [line])
            plugin.state.match_ids.add(match_id)
            index += 1

        # shadow from the bottom part of the soft shadow to the bottom line
        for line in range(bottom_soft_shadow_end + 1, bottom_line + 1):
            match_id = nvim.funcs.matchaddpos(plugin.settings.hl_groups[0], [line])
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
    nvim.out_write(msg + '\n')

