from math import sqrt
from pynvim.api.nvim import NvimError
from imfocus.color import (rgb_blend, rgb_decompose,
                           rgb_to_vim_color, vim_color_to_rgb,
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
        self.normal_bg = None

        # number of lines in focus is (2 * focus_size + 1)
        self.focus_size = max(0, nvim.vars.get(g_focus_size, 0))

        # soft shadow size is the number of the lines with lighter shades
        # then the complete shadow on each side of the lines in focus
        # by default it is hard shadow
        self.soft_shadow_size = max(0, nvim.vars.get(g_soft_shadow_size, 0))

        is_term_hl = (get_option(nvim, "t_Co") == 256)
        is_rgb_hl = (get_option(nvim, "gui_running", False)
                     or get_option(nvim, "termguicolors", False))
        if not (is_term_hl or is_rgb_hl):
            nvim.err_write(f"{plugin_name} is disabled, only rgb or 256 terminal "
                "colors are supported\n")
            return

        self.is_rgb_hl = is_rgb_hl

        # get Normal base colors
        normal_hl_map = nvim.api.get_hl_by_name(hl_group_normal, is_rgb_hl)
        fg = int(normal_hl_map.get("foreground"))
        bg = int(normal_hl_map.get("background"))
        if fg is None or bg is None:
            nvim.err_write(f"{plugin_name} is disabled, Normal colors undefined\n")
            return
        self.normal_fg = rgb_decompose(fg) if is_rgb_hl else term_to_rgb(fg)
        self.normal_bg = rgb_decompose(bg) if is_rgb_hl else term_to_rgb(bg)

        self.min_lightness = nvim.vars.get(g_min_lightness, default_min_lightness)

        self.hl_groups = set()


class ScreenState:
    def __init__(self):
        self.enabled = False
        self.cursor_line = None
        self.highlight_ids = set()


class PlugImpl:
    def __init__(self, nvim):
        self.state = ScreenState()
        reset(nvim, self)


def highlight(nvim, settings, hl_group, fg_rgb=None, bg_rgb=None):
    if hl_group in settings.hl_groups:
        return
    command = f"highlight {hl_group}"
    if fg_rgb is not None:
        fgtype = "guifg" if settings.is_rgb_hl else "ctermfg"
        color = (rgb_to_vim_color(fg_rgb) if settings.is_rgb_hl
                 else rgb_to_closest_term(fg_rgb))
        command += f" {fgtype}={color}"
    if bg_rgb is not None:
        bgtype = "guibg" if settings.is_rgb_hl else "ctermbg"
        color = (rgb_to_vim_color(bg_rgb) if settings.is_rgb_hl
                 else rgb_to_closest_term(bg_rgb))
        command += f"{bgtype}={color}"
    nvim.funcs.execute(command)
    settings.hl_groups.add(hl_group)


def get_hl_group(nvim, settings, distance, syntax_id):
    # TODO temp
    fg_rgb = settings.normal_fg
    if syntax_id:
        syntax_id = nvim.funcs.synIDtrans(syntax_id)
        fg_vim = nvim.funcs.synIDattr(syntax_id, "fg#")
        if fg_vim:
            fg_rgb = vim_color_to_rgb(fg_vim)
    fg_rgb = rgb_blend(settings.normal_bg, fg_rgb, settings.min_lightness)
    fg_vim = rgb_to_vim_color(fg_rgb)
    hl_group = "Imfocus" + fg_vim.strip("#")
    highlight(nvim, settings, hl_group, fg_rgb)
    return hl_group


def get_option(nvim, name, default=None):
    try:
        option = nvim.api.get_option(name)
    except NvimError:
        option = default
    return option


def reset(nvim, plugin):
    plugin.settings = Settings(nvim)
    if plugin.settings.normal_bg is not None:
        plugin.state.enabled = True


def is_enabled(plugin):
    return plugin.state.enabled


def enable(nvim, plugin):
    if not is_enabled(plugin):
        reset(nvim, plugin)


def disable(nvim, plugin):
    if is_enabled(plugin):
        unfocus(nvim, plugin)
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

        # first visible line in a window (1-based line numbers)
        top_line_num = nvim.funcs.line("w0")
        # last visible line in a window
        bottom_line_num = nvim.funcs.line("w$")

        # first line in focus
        focus_start = max(top_line_num, cursor_line - plugin.settings.focus_size)
        # last line in focus
        focus_end = min(bottom_line_num, cursor_line + plugin.settings.focus_size)

        # nvim_buf_get_lines() uses 0-based indexing
        lines = nvim.current.buffer.api.get_lines(top_line_num - 1,
                                                  bottom_line_num, False)

        clear_highlight(nvim, plugin.state)
        line_num = top_line_num - 1
        for line in lines:
            line_num += 1
            if not line or (line_num >= focus_start and line_num <= focus_end):
                continue
            distance_to_focus = (focus_start - line_num if focus_start > line_num
                else line_num - focus_end)
            current_syntax_id = None
            # highlighted chunk of text: (start column, length, syntax id)
            syntax_ranges = []
            start_col = 1
            syntax_id = None
            byte_one_past_end = nvim.funcs.col([line_num, "$"])
            for col in range(1, byte_one_past_end):
                current_id = nvim.funcs.synID(line_num, col, 1)
                if current_id != syntax_id:
                    if syntax_id is not None:
                        syntax_ranges.append((start_col, col - start_col, syntax_id))
                    # start the new syntax range
                    start_col = col
                    syntax_id = current_id
            syntax_ranges.append((start_col, byte_one_past_end - start_col,
                                  syntax_id))
            for col, length, syntax_id in syntax_ranges:
                hl_group = get_hl_group(nvim, plugin.settings,
                                        distance_to_focus, syntax_id)
                hl_id = nvim.funcs.matchaddpos(
                    hl_group, [[line_num, col, length]])
                plugin.state.highlight_ids.add(hl_id)


def unfocus(nvim, plugin):
    if not is_enabled(plugin):
        return
    plugin.state.cursor_line = None
    clear_highlight(nvim, plugin.state)


def clear_highlight(nvim, state):
    for match_id in state.highlight_ids:
        nvim.funcs.matchdelete(match_id)
    state.highlight_ids.clear()


def debug(nvim, msg):
    nvim.out_write(msg + '\n')

