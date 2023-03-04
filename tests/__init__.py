import os
import sys

from helpers.tools import PathManager

EXTENSIVE_TESTING = True
# define project base path
if getattr(sys, 'frozen', False):
    # frozen
    dir_ = os.path.dirname(sys.executable)
else:
    # unfrozen
    dir_ = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
PathManager.__BASE_PATH__ = dir_
print('SET PATH: ', PathManager.__BASE_PATH__)