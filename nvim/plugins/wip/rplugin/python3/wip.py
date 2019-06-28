import pynvim

@pynvim.plugin
class Wip:

    def __init__(self, nvim_ref):
        self.nvim = nvim_ref
        self.hl_group = None
        self.focus_size = None
        self.hl_src = None
        self.window = None
        self.cursor_line = None
        self.match_ids = set()

    def focus(self):
        # on_insert_enter/leave are asynchronous handlers
        # this can lead to race conditions:
        #     on_insert_leave deletes self.window while at the same time on_insert_enter already set
        #     it; then on_insert_enter tries to use invalid window
        # how to synchronize?
        #     the simplest solution is sync=True in handlers

        if self.window is None:
            self.window = self.nvim.current.window

        # lines are 1-indexed
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

            for match_id in self.match_ids:
                self.nvim.funcs.matchdelete(match_id)
            self.match_ids.clear()

            for line in range(top_line, focus_start):
                match_id = self.nvim.funcs.matchaddpos(self.hl_group, [line])
                self.match_ids.add(match_id)
            for line in range(focus_end + 1, bottom_line + 1):
                match_id = self.nvim.funcs.matchaddpos(self.hl_group, [line])
                self.match_ids.add(match_id)

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
        self.window = None
        self.cursor_line = None
        for match_id in self.match_ids:
            self.nvim.funcs.matchdelete(match_id)
        self.match_ids.clear()

    @pynvim.autocmd("CursorMovedI", pattern="*", sync=True)
    def on_cursor_moved(self):
        self.focus()

