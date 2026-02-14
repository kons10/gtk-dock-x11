import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

# 設定とウィンドウクラスをインポート
import config
from dock_window import ModernDock

class DockApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=config.APP_ID)

    def do_activate(self):
        # すでにウィンドウがあれば再利用、なければ作成
        win = self.props.active_window
        if not win:
            win = ModernDock(self)
        win.present()

if __name__ == '__main__':
    app = DockApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)