import argparse
import os
import shutil
import site
from pathlib import Path

import desktop_widgets_core
import PyInstaller.__main__


class Builder:

    @staticmethod
    def add_data(dir_name, from_site_packages=True):
        if from_site_packages:
            for path in site.getsitepackages():
                if Path(path).joinpath(dir_name).exists():
                    return "--add-data", f"{Path(path).joinpath(dir_name).absolute()}{os.pathsep}{dir_name}"
            raise FileNotFoundError(f'{dir_name} not found in site-packages ({site.getsitepackages()}')
        else:
            return "--add-data", f"{dir_name}{os.pathsep}{dir_name}"

    @staticmethod
    def copy_tree(src, dst, symlinks=False, ignore=None):
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, symlinks, ignore, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    def deploy_locally(self, src, dst):

        if not os.path.exists(dst):
            print(f'{dst} does not exist!')
            os.makedirs(dst, exist_ok=True)

        source_dir = Path('dist').joinpath(desktop_widgets_core.__name__)
        print(f'deploying {source_dir.absolute()} to {Path(dst).absolute()}')
        self.copy_tree(source_dir, dst)
        import credentials
        for file in ['default.ini',
                     *[f'{c.__name__}.pickle' for c in credentials.Credentials.__subclasses__()]]:
            if Path(file).exists():
                print(f'deploying {file} to {dst}')
                shutil.copy2(Path(src).joinpath(file), Path(dst).joinpath(file))

    # noinspection SpellCheckingInspection
    def build(self):
        PyInstaller.__main__.run([
            desktop_widgets_core.__file__,
            "-D",
            "--noconfirm",
            "--noconsole",
            "--uac-admin",
            *self.add_data('qrainbowstyle'),
            *self.add_data("resources", from_site_packages=False),
        ])
        return self


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Script to build or deploy a project.')
    parser.add_argument('--deploy', nargs=2, metavar=('SRC', 'DEST'), help='Deploy the project')

    args = parser.parse_args()

    print('building ...')
    dist = Builder().build()
    if args.deploy:
        dist.deploy_locally(*args.deploy)
