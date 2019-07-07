import pynvim
from imfocus.rplugin import RemotePlugin


@pynvim.plugin
class ImFocus:
    def __init__(self, nvim):
        # do not do anything that has non-trivial side-effects here! seriously.
        self.nvim = nvim
        self._plugin = None
        self._enable()

    @pynvim.autocmd("InsertEnter", pattern="*", sync=True)
    def on_insert_enter(self):
        self._on_insert_enter()

    @pynvim.autocmd("CursorMovedI", pattern="*", sync=True)
    def on_cursor_moved(self):
        self._on_cursor_moved()

    @pynvim.autocmd("InsertLeave", pattern="*", sync=True)
    def on_insert_leave(self):
        self._on_insert_leave()

    @pynvim.command("Imfocuson", sync=True)
    def enable(self):
        self._enable()

    @pynvim.command("Imfocusoff", sync=True)
    def disable(self):
        self._disable()

    def _enable(self):
        self._on_insert_enter = self.handle_on_insert_enter
        self._on_cursor_moved = self.handle_on_cursor_moved
        self._on_insert_leave = self.handle_on_insert_leave

    def _disable(self):
        if self._plugin is not None:
            self._plugin.unfocus()
            self._plugin = None
        self._on_insert_enter = do_nothing
        self._on_cursor_moved = do_nothing
        self._on_insert_leave = do_nothing

    def handle_on_insert_enter(self):
        if self._plugin is None:
            self._plugin = RemotePlugin(self.nvim)
            if not self._plugin.ready():
                self._plugin = None
                self._disable()
                return
        self._plugin.focus()

    def handle_on_cursor_moved(self):
        self._plugin.focus()

    def handle_on_insert_leave(self):
        self._plugin.unfocus()


def do_nothing(*args, **kwargs):
    pass

