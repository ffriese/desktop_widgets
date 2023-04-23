import atexit
import os
import shutil
import sys
from pathlib import Path


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
PathManager.get_storage_path = lambda filename=None: PathManager.join_path('test_storage', filename=filename)
print('SET PATH: ', PathManager.__BASE_PATH__)


def cleanup():
    print('SESSION STOPPED')
    shutil.rmtree(Path(PathManager.join_path('test_storage')))


atexit.register(cleanup)