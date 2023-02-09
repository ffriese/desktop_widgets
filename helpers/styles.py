import qrainbowstyle

STYLES = {}


def get_style(style_name):
    global STYLES
    if STYLES is None:
        STYLES = {}
    if style_name not in STYLES.keys():
        STYLES[style_name] = qrainbowstyle.load_stylesheet_pyqt5(style_name)
    return STYLES[style_name]
