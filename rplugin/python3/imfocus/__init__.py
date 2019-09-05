import pynvim
from imfocus.rplugin import RemotePlugin


@pynvim.plugin
class ImFocus:
    def __init__(self, nvim):
        # do not do anything that has non-trivial side-effects here! seriously.
        # see note on this page: https://pynvim.readthedocs.io/en/latest/usage/remote-plugins.html
        self.nvim = nvim
        self._plugin = None
        self._enable()

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

    # if on_insert_enter/leave and others are asynchronous handlers
    # then this can lead to race conditions:
    #     on_insert_leave clears state variable while at the same time
    #     on_insert_enter already set it;
    #     then on_insert_enter tries to use invalid variable
    # how to synchronize?
    #     the simplest solution is sync=True in handlers

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

