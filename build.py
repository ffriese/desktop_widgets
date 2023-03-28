
import sys
from pathlib import Path

import desktop_widgets_core
import PyInstaller.__main__

executable = Path(sys.executable).resolve()
site_packages = executable.parent.parent.joinpath('Lib', 'site-packages')


def add_data(dir_name, from_site_packages=True):
    return "--add-data", f"{site_packages}\\{dir_name};{dir_name}" if from_site_packages else f"{dir_name};{dir_name}"


if __name__ == '__main__':

    PyInstaller.__main__.run([
        desktop_widgets_core.__file__,
        "-D",
        "--noconfirm",
        "--noconsole",
        "--uac-admin",
        *add_data('qrainbowstyle'),
        *add_data("resources", from_site_packages=False),
    ])
