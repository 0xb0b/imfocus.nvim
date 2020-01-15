import os
import sys


# make plugin visible for pytest
# as seen on https://github.com/Shougo/deoplete.nvim

base_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(base_dir, 'rplugin/python3'))

