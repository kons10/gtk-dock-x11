import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf

# X11操作用ライブラリの読み込みを試みる
try:
    from Xlib import display, X
    from Xlib.protocol import event as xevent
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False
    print("Warning: python-xlib not found. Window management features disabled.")

class X11Helper:
    def __init__(self):
        self.enabled = HAS_XLIB
        if self.enabled:
            try:
                self.display = display.Display()
                self.root = self.display.screen().root
                self.atom_client_list = self.display.intern_atom('_NET_CLIENT_LIST')
                self.atom_active_window = self.display.intern_atom('_NET_ACTIVE_WINDOW')
            except Exception as e:
                print(f"X11 init failed: {e}")
                self.enabled = False

    def get_window_list(self):
        """現在開いているウィンドウのIDリストを取得する"""
        if not self.enabled:
            return []
        
        try:
            prop = self.root.get_full_property(self.atom_client_list, X.AnyPropertyType)
            if not prop:
                return []
            return prop.value
        except Exception as e:
            print(f"Error getting window list: {e}")
            return []

    def get_window_class(self, win_id):
        """ウィンドウIDからクラス名(アプリ名)を取得する"""
        if not self.enabled:
            return None
            
        try:
            win = self.display.create_resource_object('window', win_id)
            wm_class = win.get_wm_class()
            if wm_class:
                return wm_class[1].lower()
        except:
            pass
        return None

    def activate_window(self, win_id):
        """指定したウィンドウを最前面に持ってくる"""
        if not self.enabled:
            return

        try:
            win = self.display.create_resource_object('window', win_id)
            data = [2, X.CurrentTime, 0, 0, 0]
            ev = xevent.ClientMessage(
                window=win, 
                client_type=self.atom_active_window, 
                data=(32, data)
            )
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.display.flush()
        except Exception as e:
            print(f"Error activating window: {e}")