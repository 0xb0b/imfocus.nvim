import pynvim
from imfocus.rplugin import RemotePlugin


@pynvim.plugin
class ImFocus:
    def __init__(self, nvim):
        # do not do anything that has non-trivial side-effects here! seriously.
        self.nvim = nvim
        self._plugin = None

    @pynvim.autocmd("InsertEnter", pattern="*", sync=True)
    def on_insert_enter(self):
        if self._plugin is None:
            self._plugin = RemotePlugin(self.nvim)
        self._plugin.focus()

    @pynvim.autocmd("InsertLeave", pattern="*", sync=True)
    def on_insert_leave(self):
        self._plugin.unfocus()

    @pynvim.autocmd("CursorMovedI", pattern="*", sync=True)
    def on_cursor_moved(self):
        self._plugin.focus()

