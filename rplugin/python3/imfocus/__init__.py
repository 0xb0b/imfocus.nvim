import pynvim
from imfocus.rplugin import PlugImpl, focus, unfocus
from imfocus.rplugin import enable as enable_impl
from imfocus.rplugin import disable as disable_impl

# https://pynvim.readthedocs.io/en/latest/usage/remote-plugins.html
# @pynvim.plugin decorator makes a class discoverable as a plugin and provides
# API as nvim;
# nvim object is then passed to the plugin implementation
#
# if a plugin is not a single script file but a python package (a folder with
# several files) then it works only if the plugin class and handlers are in
# __init__.py.
# so the structure in this case is a minimal plugin class with all the handlers
# in __init__.py along a possibly separate implementation and other files of
# the package

@pynvim.plugin
class ImFocus:
    def __init__(self, nvim):
        # do not do anything that has non-trivial side-effects here! seriously.
        # (including the initialization of the plugin implementation)
        # see the note: https://pynvim.readthedocs.io/en/latest/usage/remote-plugins.html
        self.nvim = nvim
        self.impl = None

    # synchronous handlers avoid race conditions, like:
    #     on_insert_leave clears state variable when on_insert_enter has already set it;
    #     then on_insert_enter tries to use invalid variable

    @pynvim.autocmd("InsertEnter", pattern="*", sync=True)
    def on_insert_enter(self):
        if self.impl is None:
            self.impl = PlugImpl(self.nvim)
        focus(self.nvim, self.impl)

    @pynvim.autocmd("CursorMovedI", pattern="*", sync=True)
    def on_cursor_moved(self):
        focus(self.nvim, self.impl)

    @pynvim.autocmd("InsertLeave", pattern="*", sync=True)
    def on_insert_leave(self):
        unfocus(self.nvim, self.impl)

    @pynvim.autocmd("ColorScheme", pattern="*", sync=True)
    def on_colors_changed(self):
        if self.impl is not None:
            disable_impl(self.nvim, self.impl)
            enable_impl(self.nvim, self.impl)

    @pynvim.command("Imfocuson", sync=True)
    def enable(self):
        if self.impl is None:
            self.impl = PlugImpl(self.nvim)
        enable_impl(self.nvim, self.impl)

    @pynvim.command("Imfocusoff", sync=True)
    def disable(self):
        if self.impl is not None:
            disable_impl(self.nvim, self.impl)

