from math import sqrt
from pynvim.api.nvim import NvimError
from imfocus.color import (blend_rgb, decompose_rgb,
                           rgb_to_vim_color, vim_color_to_rgb,
                           term_to_rgb, rgb_to_closest_term)


plugin_name = __name__.partition(".")[0]
normal_hl_group = "Normal"
default_min_lightness = 0.2

# global variable names
g_focus_size = plugin_name + "_size"
g_soft_shadow_size = plugin_name + "_soft_shadow_size"
g_shadow_hl_group = plugin_name + "_shadow_hl_group"
g_min_lightness = plugin_name + "_min_lightness"


class Settings:
    def __init__(self, nvim):
        self.shadow_hl_group = None
        self.shadow_fg_rgb = None
        # TODO remove shadow rgb and use only foreground color?
        self.shadow_bg_rgb = None

        # number of lines in focus is (2 * k + 1)
        # focus_size parameter is k
        self.focus_size = (max(1, nvim.vars.get(g_focus_size, 1)) - 1) // 2

        # soft shadow size is the number of lines which are lighter
        # then the complete shadow on each side of the lines in focus;
        # by default the shadow is hard
        self.soft_shadow_size = max(0, nvim.vars.get(g_soft_shadow_size, 0))

        self.is_rgb_hl = (get_option(nvim, "gui_running", False)
                          or get_option(nvim, "termguicolors", False))

        shadow_hl_group = nvim.vars.get(g_shadow_hl_group, None)
        if shadow_hl_group is not None and nvim.funcs.hlexists(shadow_hl_group):
            self.shadow_fg_rgb, self.shadow_bg_rgb = get_colors_by_hl_name(
                nvim, shadow_hl_group)

        self.normal_fg_rgb, self.normal_bg_rgb = get_colors_by_hl_name(
            nvim, normal_hl_group)
        if self.normal_fg_rgb is None or self.normal_bg_rgb is None:
            # normal colors are needed because they are used as fallback if
            # shadow colors are not defined explicitly;
            # normal colors are also assumed when syntax id is returned as zero
            nvim.err_write(f"{plugin_name} is disabled, "
                            "normal colors undefined\n")
            return

        # fallback to Normal colors if shadow colors are undefined
        if self.shadow_bg_rgb is None:
            self.shadow_bg_rgb = self.normal_bg_rgb
        if self.shadow_fg_rgb is None:
            min_lightness = nvim.vars.get(g_min_lightness,
                                          default_min_lightness)
            self.shadow_fg_rgb = blend_rgb(
                self.shadow_bg_rgb, self.normal_fg_rgb, min_lightness)

        self.shadow_hl_group = make_hl_group_name(
            nvim, self.shadow_fg_rgb, self.shadow_bg_rgb)
        highlight(nvim, self.is_rgb_hl, self.shadow_hl_group,
                  self.shadow_fg_rgb, self.shadow_bg_rgb)

        # if highlight is 256 colors terminal then rgb colors are calculated
        # approximately;
        # get rgb values of terminal colors that were approximated from the
        # original color values
        if not self.is_rgb_hl:
            self.shadow_fg_rgb, self.shadow_bg_rgb = get_colors_by_hl_name(
                nvim, self.shadow_hl_group)

        # cache highlight groups of the soft shadow colors
        self.hl_groups = set()

        self.lightness_profile = [1.0] * (self.soft_shadow_size + 1)
        # quadratic lightness fall-off with distance
        for distance in range(1, self.soft_shadow_size + 1):
            self.lightness_profile[distance] = 2.0 / (1 + distance)**2


class ScreenState:
    def __init__(self):
        self.enabled = False
        self.cursor_line = None
        self.hl_ids = set()


class PlugImpl:
    def __init__(self, nvim):
        self.state = ScreenState()
        reset(nvim, self)


def get_colors_by_hl_name(nvim, hl_group):
    fg_rgb = None
    bg_rgb = None

    ctermfg = None
    ctermbg = None
    guifg = None
    guibg = None

    try:
        hl_string = nvim.funcs.execute(f"hi {hl_group}")
    except NvimError:
        hl_string = ''
    # Normal         xxx ctermfg=223 ctermbg=235 guifg=#ebdbb2 guibg=#282828
    # TODO add handling of color names and special names (see :help guifg)
    terms = hl_string.split()
    for term in terms:
        if "=" not in term:
            continue
        key, value = term.split("=")
        if key == "ctermfg":
            ctermfg = value
        if key == "ctermbg":
            ctermbg = value
        if key == "guifg":
            guifg = value
        if key == "guibg":
            guibg = value

    if guifg is not None:
        fg_rgb = vim_color_to_rgb(guifg)
    elif ctermfg is not None:
        fg_rgb = term_to_rgb(int(ctermfg))

    if guibg is not None:
        bg_rgb = vim_color_to_rgb(guibg)
    elif ctermbg is not None:
        bg_rgb = term_to_rgb(int(ctermbg))

    return fg_rgb, bg_rgb


def make_hl_group_name(nvim, fg_rgb, bg_rgb, distance=None):
    # shadow highlight group name:
    #   const name + vim fg color string + vim bg color string
    #   + distance to focus in the interval [1, soft_shadow_size] or None
    return (plugin_name + rgb_to_vim_color(fg_rgb)
            + rgb_to_vim_color(bg_rgb) + str(distance))


def highlight(nvim, is_rgb_hl, hl_group, fg_rgb=None, bg_rgb=None):
    command = f"highlight {hl_group}"
    if fg_rgb is not None:
        fgtype = "guifg" if is_rgb_hl else "ctermfg"
        color = (rgb_to_vim_color(fg_rgb) if is_rgb_hl
                 else rgb_to_closest_term(fg_rgb))
        command += f" {fgtype}={color}"
    if bg_rgb is not None:
        bgtype = "guibg" if is_rgb_hl else "ctermbg"
        color = (rgb_to_vim_color(bg_rgb) if is_rgb_hl
                 else rgb_to_closest_term(bg_rgb))
        command += f" {bgtype}={color}"
    nvim.funcs.execute(command)


def get_hl_group(nvim, settings, distance, syntax_id):
    if distance > settings.soft_shadow_size:
        return settings.shadow_hl_group
    if distance < 1:
        return None

    fg_rgb = None
    bg_rgb = None
    # if syntax id is 0 this means non highlighted text
    # Normal highlighting is used for this
    if syntax_id:
        syntax_id = nvim.funcs.synIDtrans(syntax_id)
        #  hl_group = nvim.funcs.synIDattr(syntax_id, "name")
        #  fg_rgb, bg_rgb = get_colors_by_hl_name(nvim, hl_group)
        fg = nvim.funcs.synIDattr(syntax_id, "fg#")
        if fg:
            fg_rgb = (vim_color_to_rgb(fg) if settings.is_rgb_hl
                      else term_to_rgb(int(fg)))
        bg = nvim.funcs.synIDattr(syntax_id, "bg#")
        if bg:
            bg_rgb = (vim_color_to_rgb(bg) if settings.is_rgb_hl
                      else term_to_rgb(int(bg)))

    if fg_rgb is None:
        fg_rgb = settings.normal_fg_rgb
    if bg_rgb is None:
        bg_rgb = settings.normal_bg_rgb

    hl_group = make_hl_group_name(nvim, fg_rgb, bg_rgb, distance)
    if not hl_group in settings.hl_groups:
        lightness = settings.lightness_profile[distance]
        fg_rgb = blend_rgb(settings.shadow_fg_rgb, fg_rgb, lightness)
        bg_rgb = blend_rgb(settings.shadow_bg_rgb, bg_rgb, lightness)
        highlight(nvim, settings.is_rgb_hl, hl_group, fg_rgb, bg_rgb)
        settings.hl_groups.add(hl_group)

    return hl_group


def get_option(nvim, name, default=None):
    try:
        option = nvim.api.get_option(name)
    except NvimError:
        option = default
    return option


def reset(nvim, plugin):
    plugin.settings = Settings(nvim)
    if plugin.settings.shadow_hl_group is not None:
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

        # last or one past last line in a window.
        # if the last line is too long and is wrapped into several screen lines
        # then some of those screen lines may fall off the bottom edge of the
        # window.
        # in this case line() function returns the number of the next to last
        # (penultimate) line;
        # so more precisely the return value of line() is the number of the
        # last fully visible line in a window
        bottom_line_num = nvim.funcs.line("w$") + 1

        # first line in focus
        focus_start = max(top_line_num,
                          cursor_line - plugin.settings.focus_size)
        # last line in focus
        focus_end = min(bottom_line_num,
                        cursor_line + plugin.settings.focus_size)

        # nvim_buf_get_lines() uses 0-based indexing
        lines = nvim.current.buffer.api.get_lines(top_line_num - 1,
                                                  bottom_line_num, False)

        # TODO optimize to use previous state?
        clear_highlight(nvim, plugin.state)
        line_num = top_line_num - 1
        for line in lines:
            line_num += 1
            if line_num >= focus_start and line_num <= focus_end:
                continue

            distance_to_focus = (focus_start - line_num
                                 if focus_start > line_num
                                 else line_num - focus_end)
            if distance_to_focus > plugin.settings.soft_shadow_size:
                hl_id = nvim.funcs.matchaddpos(plugin.settings.shadow_hl_group,
                                               [line_num])
                plugin.state.hl_ids.add(hl_id)
                continue

            current_syntax_id = None

            # highlighted chunk of text - syntax range:
            #   (start column, length, syntax id)
            syntax_ranges = []
            start_col = 1
            syntax_id = None

            # col() returns byte position
            byte_one_past_end = nvim.funcs.col([line_num, "$"])
            for col in range(1, byte_one_past_end):
                current_id = nvim.funcs.synID(line_num, col, 1)
                if current_id != syntax_id:
                    if syntax_id is not None:
                        syntax_ranges.append((start_col, col - start_col,
                                              syntax_id))
                    # start the new syntax range
                    start_col = col
                    syntax_id = current_id
            # add the last range
            syntax_ranges.append((start_col, byte_one_past_end - start_col,
                                  syntax_id))

            for col, length, syntax_id in syntax_ranges:
                hl_group = get_hl_group(nvim, plugin.settings,
                                        distance_to_focus, syntax_id)
                # matchaddpos is weird
                # highlight range needs double square brackets to work
                # [line_num, col, length] have the same effect as
                # [line_num] alone
                hl_id = nvim.funcs.matchaddpos( hl_group,
                                                [[line_num, col, length]])
                plugin.state.hl_ids.add(hl_id)


def unfocus(nvim, plugin):
    if not is_enabled(plugin):
        return
    plugin.state.cursor_line = None
    clear_highlight(nvim, plugin.state)


def clear_highlight(nvim, state):
    for match_id in state.hl_ids:
        nvim.funcs.matchdelete(match_id)
    state.hl_ids.clear()


def debug(nvim, msg):
    nvim.out_write(msg + '\n')

