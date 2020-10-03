from math import sqrt
from pynvim.api.nvim import NvimError
from isee.color import (blend_rgb, decompose_rgb,
                        rgb_to_vim_color, vim_color_to_rgb,
                        term_to_rgb, rgb_to_closest_term)

# dbg
from time import sleep


plugin_name = __name__.partition('.')[0]
normal_hl_group = 'Normal'
default_min_lightness = 0.2

# global variable names
g_focus_size = plugin_name + '_size' # TODO change to focus_size?
g_soft_shadow_size = plugin_name + '_soft_shadow_size'
g_shadow_color = plugin_name + '_shadow_color'
g_min_lightness = plugin_name + '_min_lightness'


# TODO with the light color scheme this looks more like fog than shadow
# get a better name?
class Settings:
    def __init__(self, nvim):
        self.hl_groups = None

        # special color names 'fg' and 'bg' mean normal highligh colors
        normal_fg_rgb = decompose_rgb(nvim.api.get_color_by_name('fg'))
        normal_bg_rgb = decompose_rgb(nvim.api.get_color_by_name('bg'))
        if normal_fg_rgb is None or normal_bg_rgb is None:
            # normal colors are needed because they are used as fallback if
            # shadow color is not defined explicitly;
            # normal background is used as shadow background;
            nvim.err_write(f'{plugin_name} is disabled, '
                            'normal colors undefined\n')
            return

        # focus size parameter is the number of lines in focus and has to be
        # equal to (2 * k + 1)
        # in Settings focus_size is k
        self.focus_size = (max(1, nvim.vars.get(g_focus_size, 1)) - 1) // 2

        # soft shadow size is the number of lines which are lighter
        # then the complete shadow on each side of the lines in focus;
        # by default the shadow is hard (soft shadow size is 0)
        self.soft_shadow_size = nvim.vars.get(g_soft_shadow_size, 0)

        self.is_rgb_hl = (get_option(nvim, 'gui_running', False)
                          or get_option(nvim, 'termguicolors', False))

        shadow_fg = nvim.vars.get(g_shadow_color, None)
        shadow_fg_rgb = None if shadow_fg is None else decompose_rgb(shadow_fg)
        # fallback to Normal colors if shadow color is undefined
        if shadow_fg_rgb is None:
            min_lightness = nvim.vars.get(g_min_lightness,
                                          default_min_lightness)
            shadow_fg_rgb = blend_rgb(
                normal_bg_rgb, normal_fg_rgb, min_lightness)

        # precalculate soft shadow highlight groups and make a lookup table
        # distance -> highlight group
        # the 0th element is the highlight group of the full shadow
        self.hl_groups = [None] * (self.soft_shadow_size + 1)
        shadow_hl_group = make_hl_group_name(shadow_fg_rgb, normal_bg_rgb)
        activate_hl_group(nvim, self.is_rgb_hl, shadow_hl_group,
                          shadow_fg_rgb, normal_bg_rgb)
        self.hl_groups[0] = shadow_hl_group
        # cache highlighting groups of the soft shadow colors
        # lookup by distance
        self.lightness_profile = [1.0] * (self.soft_shadow_size + 1)
        for distance in range(1, self.soft_shadow_size + 1):
            # quadratic lightness fall-off with distance
            lightness = 2.0 / (1 + distance)**2
            self.lightness_profile[distance] = lightness
            fg_rgb = blend_rgb(shadow_fg_rgb, normal_fg_rgb, lightness)
            hl_group = make_hl_group_name(fg_rgb, normal_bg_rgb)
            activate_hl_group(nvim, self.is_rgb_hl, hl_group,
                              fg_rgb, normal_bg_rgb)
            self.hl_groups[distance] = hl_group


class ScreenState:
    def __init__(self):
        self.enabled = False
        self.highlight_rows = set()
        self.row_to_hl_id = {}


class PlugImpl:
    def __init__(self, nvim):
        self.state = ScreenState()
        reset(nvim, self)


def make_hl_group_name(fg_rgb, bg_rgb):
    # shadow highlight group name:
    #   const name + vim fg color string + vim bg color string
    #   + distance to focus in the interval [1, soft_shadow_size]
    #     or None for complete shadow
    return f'{plugin_name}{rgb_to_vim_color(fg_rgb)}{rgb_to_vim_color(bg_rgb)}'


def activate_hl_group(nvim, is_rgb_hl, hl_group, fg_rgb=None, bg_rgb=None):
    command = f'highlight {hl_group}'
    if fg_rgb is not None:
        fgtype = 'guifg' if is_rgb_hl else 'ctermfg'
        color = (rgb_to_vim_color(fg_rgb) if is_rgb_hl
                 else rgb_to_closest_term(fg_rgb))
        command += f' {fgtype}={color}'
    if bg_rgb is not None:
        bgtype = 'guibg' if is_rgb_hl else 'ctermbg'
        color = (rgb_to_vim_color(bg_rgb) if is_rgb_hl
                 else rgb_to_closest_term(bg_rgb))
        command += f' {bgtype}={color}'
    nvim.funcs.execute(command)


def get_hl_group(nvim, settings, distance_to_cursor):
    distance = distance_to_cursor - settings.focus_size
    if distance < 1:
        # the line is in focus
        return
    if distance > settings.soft_shadow_size:
        return settings.hl_groups[0]
    return settings.hl_groups[distance]


def get_option(nvim, name, default=None):
    try:
        option = nvim.api.get_option(name)
    except NvimError:
        option = default
    return option


def reset(nvim, plugin):
    plugin.settings = Settings(nvim)
    if plugin.settings.hl_groups is not None:
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
            nvim.funcs.execute(f'highlight clear {hl_group}')
        plugin.state = ScreenState()
        plugin.settings = None


# dbg very long line with tabs and strange symbol
#	ℤxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx	xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxx0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

def focus(nvim, plugin):
    # normal mode commands can not be executed in insert mode
    # mappings exit insert mode, execute command, enter insert mode
    # Ctrl-o exits insert mode, executes command, enters insert mode
    # this means that while in insert mode the only thing that can change the
    # screen width is the change of the number width
    if not is_enabled(plugin):
        return

    top_line_num = nvim.funcs.line('w0')
    bottom_line_num = nvim.funcs.line('w$')
    if bottom_line_num < top_line_num:
        # no lines are visible in a window
        return

    # TODO buggy and bad side effects
    # add one additional line at the bottom because bottom line number is the
    # number of the last fully visible line in a window
    # it may happen that the last line is wrapped and falls off the bottom
    # screen edge so it is partially visible
    # bottom_line_num += 1

    window = nvim.current.window
    # cursor position is given as
    #   (text line number, byte offset from the start of the text line)
    cursor_position = window.api.get_cursor()
    cursor_line_num = cursor_position[0]

    # virtual edit has to be turned off!
    # is the line wrapped by the line number?
    #   if the line display length is greater then the screen width then the
    #   line is wrapped
    # is the cursor positioned not on the first screen row of the wrapped line?
    #   position cursor at the beginning of the screen row - norm! g0
    #   if byte offset is not zero than the cursor is on the wrapped line
    #   and not on the first screen row
    # is the cursor positioned not on the last screen row of the wrapped line?
    #   position cursor at the end of the screen row - norm! g$
    #   if byte offset is less than the line length then the cursor is on the
    #   wrapped line and not on the last screen row

    # determine the width of the screen row
    showbreak_width = nvim.funcs.strdisplaywidth(
        nvim.api.get_option('showbreak'))
    virtualedit_option = nvim.api.get_option('virtualedit')
    nvim.api.set_option('virtualedit', 'all')
    nvim.api.command('norm! g0')
    screen_width = window.width - nvim.funcs.wincol() + 1
    nvim.api.set_option('virtualedit', virtualedit_option)
    _, row_start_offset = window.api.get_cursor()
    if row_start_offset > 0:
        screen_width += showbreak_width

    # indexing for get_lines is 0-based end-exclusive
    lines = nvim.current.buffer.api.get_lines(
        top_line_num - 1, bottom_line_num + 1, False)
    is_wrap_on = window.api.get_option('wrap')
    highlight_rows = set()

    # scan lines from the cursor row up to the top line or until number of
    # rows scanned becomes equal to the window height (it can happen that the
    # whole window and beyond is occupied by the giant text line so that it
    # may take e.g. thousands of rows to get to the beginning of this line)
    distance = 0  # distance in rows from the cursor row
    cursor_row = nvim.funcs.winline()
    #  debug(nvim, f'#dbg window height {window.height} window row {cursor_row} window width {window.width} wincol {nvim.funcs.wincol()} screen width {screen_width} cursor {window.api.get_cursor()}')
    max_distance = cursor_row - 1
    for line_num in range(cursor_line_num, top_line_num - 1, -1):
        line = lines[line_num - top_line_num]
        if not line or line.isspace():
            # empty line takes one row and does not need to be highlighted
            distance += 1
            continue
        is_line_wrapped = (is_wrap_on
                           and nvim.funcs.strdisplaywidth(line) > screen_width)
        if is_line_wrapped:
            if distance == 0:
                # cursor starting position is at the start of the cursor row
                # go up to the end of the preceding row
                # cursor row is not highlighted
                nvim.api.command('norm! h')
                distance += 1
            else:
                # scan the wrapped line up from end to start
                window.api.set_cursor((line_num, nvim.funcs.col([line_num, '$'])))
            _, cursor_offset = window.api.get_cursor()
            while cursor_offset > 0:
                nvim.api.command('norm! g0')
                _, row_start_offset = window.api.get_cursor()
                if distance > plugin.settings.focus_size:
                    # highlight only rows out of focus
                    highlight_rows.add((line_num, row_start_offset,
                        cursor_offset - row_start_offset, distance))
                distance += 1
                if distance > max_distance:
                    # reached top of the screen
                    # cursor may be in the middle of the very long wrapped line
                    # that occupies the whole window and stretches far beyond
                    # the window edge
                    break
                if row_start_offset > 0:
                    # go up to the end of the preceding row
                    nvim.api.command('norm! h')
                    _, cursor_offset = window.api.get_cursor()
                else:
                    # cursor is at the start of the line
                    cursor_offset = 0
        else:
            if distance > plugin.settings.focus_size:
                # highlight only lines out of focus
                highlight_rows.add((line_num, None, None, distance))
            distance += 1
        if distance > max_distance:
            break

    window.api.set_cursor(cursor_position)

    # scan lines from the cursor row down to the bottom line or until number of
    # rows scanned becomes equal to the window height (it can happen that the
    # whole window and beyond is occupied by the giant text line so that it
    # may take e.g. thousands of rows to get to the end of this line)
    distance = 0
    max_distance = window.height - cursor_row
    for line_num in range(cursor_line_num, bottom_line_num + 1):
        line = lines[line_num - top_line_num]
        if not line or line.isspace():
            distance += 1
            continue
        is_line_wrapped = (is_wrap_on
                           and nvim.funcs.strdisplaywidth(line) > screen_width)
        if is_line_wrapped:
            if distance == 0:
                # go down to the start of the next row
                # cursor row is not highlighted
                nvim.api.command('norm! g$l')
                distance += 1
            else:
                # scan the wrapped line down from start to end
                window.api.set_cursor((line_num, 0))
            line_end_offset = nvim.funcs.col([line_num, '$'])
            _, cursor_offset = window.api.get_cursor()
            while cursor_offset < line_end_offset:
                nvim.api.command('norm! g$')
                _, row_end_offset = window.api.get_cursor()
                if distance > plugin.settings.focus_size:
                    highlight_rows.add((line_num, cursor_offset,
                        row_end_offset - cursor_offset, distance))
                distance += 1
                if distance > max_distance:
                    # reached bottom of the screen
                    # the last line may be wrapped and fall off the screen edge
                    break
                if row_end_offset < line_end_offset:
                    # go down to the start of the next row
                    nvim.api.command('norm! l')
                    _, cursor_offset = window.api.get_cursor()
                else:
                    # cursor is at the end of the line
                    cursor_offset = line_end_offset
        else:
            if distance > plugin.settings.focus_size:
                highlight_rows.add((line_num, None, None, distance))
            distance += 1
        if distance > max_distance:
            break

    window.api.set_cursor(cursor_position)
    # if the last line is partially visible then it jumps up and becomes fully
    # visible after the cursor touches it
    # adjust viewport by moving it down
    view_shift = cursor_row - nvim.funcs.winline()
#      if view_shift > 0:
        #  nvim.command(f'norm! {view_shift}\<C-y>')

    # update highlighting using the difference with the previous set of
    # highlighted rows
    prev_highlight_rows = plugin.state.highlight_rows
    rows_to_delete = prev_highlight_rows - highlight_rows
    for item in rows_to_delete:
        hl_id = plugin.state.row_to_hl_id[item]
        del plugin.state.row_to_hl_id[item]
        nvim.funcs.matchdelete(hl_id)
    rows_to_add = highlight_rows - prev_highlight_rows
    for item in rows_to_add:
        line_num, col, length, distance = item
        hl_group = get_hl_group(nvim, plugin.settings, distance)
        if col is None:
            hl_id = nvim.funcs.matchaddpos(hl_group, [line_num])
        else:
            hl_id = nvim.funcs.matchaddpos(hl_group, [[line_num, col, length]])
        plugin.state.row_to_hl_id[item] = hl_id
    plugin.state.highlight_rows = highlight_rows



#      plugin.state.min_number_width = window.api.get_option('numberwidth')
    #  last_line_num = nvim.funcs.line('$')
    #  plugin.state.number_width = max(plugin.state.min_number_width,
#                                      len(str(last_line_num)))

#      # first visible line in a window
    #  top_line_num = nvim.funcs.line('w0')
    #  # last fully visible line in a window
    #  bottom_line_num = nvim.funcs.line('w$')
    #  # if there are any wrapped lines on the screen then line numbers difference
    #  # is less than the screen height
    #  has_wrapped_lines = (top_line_num - bottom_line_num + 1 < window.height)

    # determine the screen row width
#      nvim.api.win_set_cursor(0, (cursor_line_num, byte_offset))
    #  plugin.state.screen_width = screen_width
#
    #  # determine screen row of the cursor
    #  screen_cells_to_cursor = nvim.funcs.virtcol('.') - 1
    #  plugin.state.cursor_relative_row = screen_cells_to_cursor // screen_width
    #  plugin.state.cursor_line_num = cursor_line_num


    '''# nvim_buf_get_lines() uses 0-based indexing, line() uses 1-based indexing
    # so have to subtract 1 from top line number.
    #
    # if the last line is too long and is wrapped into several screen lines
    # then some of those screen lines may fall off the bottom edge of the
    # window.
    # in this case line('w$') returns the number of the next to last
    # (penultimate) line;
    # so more precisely the return value of line('w$') is the number of the
    # last fully visible line in a window.
    # because also nvim_buf_get_lines end parameter is exclusive one has to
    # add 1 to the bottom line number to take into account the last line
    # that could be partially visible
    visible_text = nvim.api.buf_get_lines(
        0, top_line_num - 1, bottom_line_num + 1, False)

    # TODO optimize to use previous state?
    clear_highlight(nvim, plugin.state)

    full_shadow_top_range = None
    full_shadow_bottom_range = None
    cursor_line_index = cursor_line_num - top_line_num
    line_index = cursor_line_index
    # start from the cursor row and go up the screen
    distance_to_cursor = 0
    while line_index >= 0:
        line = visible_text[line_index]
        if not line or line.isspace():
            distance_to_cursor += 1
            line_index -= 1
            continue
        line_screen_length = nvim.funcs.strdisplaywidth(line)
        if line_index == cursor_line_index:
            relative_row = plugin.state.cursor_relative_row
        else:
            if distance_to_cursor > (plugin.settings.focus_size
                                     + plugin.settings.soft_shadow_size):
                line_num = top_line_num + line_index
                full_shadow_top_range = (line_num, top_line_num)
                break
            relative_row = line_screen_length // screen_width
            if line_screen_length > relative_row * screen_width:
                relative_row += 1
        while relative_row >= 0:

        line_num -= 1



    line_num = top_line_num
    screen_row = 0
    highlight_rows = []
    cursor_row = 0
    for line in lines:
        if line_num = plugin.state.cursor_line_num:
            cursor_row = screen_row + plugin.state.cursor_relative_row
        if not line or line.isspace():
            line_num += 1
            screen_row += 1
            # do not highlight empty lines
            continue
        line_screen_length = nvim.funcs.strdisplaywidth(line)
        if line_screen_length <= screen_width:
            # line is not wrapped so highlight the whole line
            highlight_rows.append((screen_row, line_num, None, None))
        else:
            # line occupies several screen rows, find the ranges for each row
            start_offset = 0
            length = screen_width
            line_tail_length = line_screen_length
            while line_tail_length > screen_width:
                line_chunk = nvim.funcs.strpart(line, start_offset, length)
                chunk_screen_length = nvim.funcs.strdisplaywidth(line_chunk)
                increment = 1 if chunk_screen_length < screen_width else -1
                while chunk_screen_length != screen_width:
                    length += increment
                    line_chunk = nvim.funcs.strpart(line, start_offset, length)
                    chunk_screen_length = nvim.funcs.strdisplaywidth(line_chunk)
                highlight_rows.append(
                    (screen_row, line_num, start_offset, length))
                start_offset += length
                line_tail_length -= screen_width
                screen_row += 1
            if line_tail_length > 0:
                # the last chunk of the wrapped line
                highlight_rows.append((screen_row, line_num, start_offset,
                                       strlen(line) - start_offset))
                screen_row += 1


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
        byte_one_past_end = nvim.funcs.col([line_num, '$'])
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
            # [line_num, col, length] with single brackets has the same
            # effect as [line_num] alone
            hl_id = nvim.funcs.matchaddpos( hl_group,
                                            [[line_num, col, length]])
            plugin.state.hl_ids.add(hl_id)'''


def focus_update(nvim, plugin):
    pass


def unfocus(nvim, plugin):
    if not is_enabled(plugin):
        return
    clear_highlight(nvim, plugin.state)


def clear_highlight(nvim, state):
    state.highlight_rows.clear()
    for hl_id in state.row_to_hl_id.values():
        nvim.funcs.matchdelete(hl_id)
    state.row_to_hl_id.clear()


def debug(nvim, msg):
    nvim.out_write(msg + '\n')

