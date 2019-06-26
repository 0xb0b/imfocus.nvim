import pynvim

@pynvim.plugin
class Wip:

    def __init__(self, nvim_ref):
        self.nvim = nvim_ref
        self.hl_group = None
        self.focus_size = None
        self.hl_src = None
        self.window = None
        self.line_num = None
        self.match_ids = []

    def focus(self):
        # on_insert_enter/leave are asynchronous handlers
        # this can lead to race conditions:
        #     on_insert_leave deletes self.window while at the same time on_insert_enter already set
        #     it; then on_insert_enter tries to use invalid window
        # how to synchronise?
        #     the simplest solution is sync=True in handlers
        if self.window is None:
            self.window = self.nvim.current.window
            #  self.nvim.out_write("#dbg window is {}\n".format(self.window))

        current_line_num = self.window.cursor[0]  # 1-indexed
        if self.line_num != current_line_num:
            self.line_num = current_line_num
            line_count = self.window.buffer.api.line_count()
            row = self.nvim.funcs.winline()
            height = self.window.height

            #  self.nvim.out_write("#dbg line {} (line count {}) row {} (height {})\n".format(
                #  self.line_num, line_count, row, height))

            # first line of the window or first line of the buffer
            start = max(1, current_line_num - row + 1)
            # last line of the window or last line of the buffer
            end = min(line_count, start + height)
            # first line in focus or first line of the buffer
            upper = max(1, current_line_num - self.focus_size)
            # last line in focus or last line of the buffer
            lower = min(line_count, current_line_num + self.focus_size)
            if start < upper:
                self.match_ids.extend([self.nvim.funcs.matchaddpos(self.hl_group, [n])
                                       for n in range(start, upper)])
            if end > lower:
                self.match_ids.extend([self.nvim.funcs.matchaddpos(self.hl_group, [n])
                                       for n in range(lower + 1, end + 1)])

            # optimize to not shadow the whole buffer, just what is on the screen
#              hl_items = []
            #  upper = current_line_num - self.focus_size
            #  # shadow from the start to but not including upper (upper is the first line in focus)
            #  if upper > 0:
                #  hl_items.extend([(self.hl_group, n) for n in range(upper)])
            #  lower = current_line_num + self.focus_size
            #  # shadow from but not including lower to the end (lower is the last line in focus)
            #  if lower < line_count - 1:
                #  hl_items.extend([(self.hl_group, n) for n in range(lower + 1, line_count)])
            #  self.buffer.update_highlights(self.hl_src, hl_items, async_=True)

    @pynvim.autocmd("InsertEnter", pattern="*", sync=True)
    def on_insert_enter(self):
        if self.hl_group is None:
            self.hl_group = self.nvim.vars.get("wip_hl_group", None)
        if self.hl_group is None:
            self.nvim.out_write("#dbg hl_group is None\n")
        else:
            if self.hl_src is None:
                self.hl_src = self.nvim.new_highlight_source()
            if self.focus_size is None:
                self.focus_size = max(0, self.nvim.vars.get("wip_focus_size", 0))
            self.focus()

    @pynvim.autocmd("InsertLeave", pattern="*", sync=True)
    def on_insert_leave(self):
        # clear the shadow highlighting for buffer that was shadowed
        # clear cached line and buf
        self.window = None
        self.line_num = None
        for match_id in self.match_ids:
            self.nvim.funcs.matchdelete(match_id)
        self.match_ids = []

