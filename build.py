import os
import site
from pathlib import Path

import desktop_widgets_core
import PyInstaller.__main__


def add_data(dir_name, from_site_packages=True):
    if from_site_packages:
        for path in site.getsitepackages():
            if Path(path).joinpath(dir_name).exists():
                return "--add-data", f"{Path(path).joinpath(dir_name).absolute()}{os.pathsep}{dir_name}"
        raise FileNotFoundError(f'{dir_name} not found in site-packages ({site.getsitepackages()}')
    else:
        return "--add-data", f"{dir_name}{os.pathsep}{dir_name}"


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
