import sys
import datetime
import gi
import threading
import time
import subprocess 

# GTK3を指定
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio

# X11操作用
try:
    from Xlib import display, X
    from Xlib.protocol import event as xevent
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False
    print("Error: python3-xlib is not installed. Please run: sudo apt install python3-xlib")

# アプリケーションID
APP_ID = 'dock.ams.f5.si'

class ModernDock(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_title("Modern Dock")
        
        # 【修正ポイント1】タイプヒントをDOCKに変更
        # OpenboxにおいてNORMALだと自動配置で上に飛ばされるため、DOCKとして宣言する。
        # もしこれで位置が固定されて動かない場合は、UTILITY を試してみてね。
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        
        self.set_default_size(1000, 60)
        self.set_resizable(False)
        self.set_decorated(False) # タイトルバーなし
        
        # 常に最前面に表示
        self.set_keep_above(True)
        
        # すべてのワークスペースに表示（Dockらしい挙動）
        self.stick()
        
        # タスクバーなどに表示させない
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        # --- アイコンテーマの強制設定 ---
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-icon-theme-name", "Papirus")
            settings.set_property("gtk-application-prefer-dark-theme", False)
        
        # 画面のコンポジット（透明化）を有効にする
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual and self.get_screen().is_composited():
            self.set_visual(visual)

        self.load_css()
        
        self.app_info_cache = Gio.AppInfo.get_all()
        
        if HAS_XLIB:
            self.x_display = display.Display()
            self.x_root = self.x_display.screen().root
            self.atom_client_list = self.x_display.intern_atom('_NET_CLIENT_LIST')
            self.atom_active_window = self.x_display.intern_atom('_NET_ACTIVE_WINDOW')
            
        # --- レイアウト構築 (GTK3) ---
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main_box.get_style_context().add_class("dock-container")
        self.add(main_box)
        
        # [左] ランチャーボタン
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left_box.get_style_context().add_class("left-section")
        left_box.set_valign(Gtk.Align.CENTER)
        
        launcher_btn = Gtk.Button()
        launcher_btn.get_style_context().add_class("launcher-button")
        launcher_icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.BUTTON)
        launcher_btn.add(launcher_icon)
        
        # クリックイベント
        launcher_btn.connect("clicked", self.on_launcher_clicked)
        
        left_box.pack_start(launcher_btn, False, False, 0)
        main_box.pack_start(left_box, False, False, 0)
        
        # [中] アプリアイコン
        self.center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.center_box.get_style_context().add_class("center-section")
        self.center_box.set_halign(Gtk.Align.CENTER)
        self.center_box.set_valign(Gtk.Align.CENTER)
        
        main_box.pack_start(self.center_box, True, False, 0)
        
        # [右] ステータスと時計
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        right_box.get_style_context().add_class("right-section")
        right_box.set_valign(Gtk.Align.CENTER)
        
        status_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_container.get_style_context().add_class("status-pill")
        status_container.set_valign(Gtk.Align.CENTER)
        
        for status_icon in ["network-wireless-symbolic", "audio-volume-medium-symbolic"]:
            img = Gtk.Image.new_from_icon_name(status_icon, Gtk.IconSize.MENU)
            img.get_style_context().add_class("status-icon")
            status_container.pack_start(img, False, False, 0)
            
        self.clock_label = Gtk.Label(label="00:00")
        self.clock_label.get_style_context().add_class("clock-label")
        status_container.pack_start(self.clock_label, False, False, 0)
        
        right_box.pack_start(status_container, False, False, 0)
        main_box.pack_start(right_box, False, False, 0)
        
        # --- タイマー処理 ---
        GLib.timeout_add_seconds(1, self.update_clock)
        self.update_clock()
        
        if HAS_XLIB:
            GLib.timeout_add(1000, self.update_window_list)
            self.update_window_list()

        self.show_all()
        
        # 位置合わせのためのイベント接続
        # realizeだけでなく、map（表示完了）時にも位置合わせを行う
        self.connect("realize", self.on_realize)
        self.connect("map-event", self.on_map_event)

    def load_css(self):
        css_provider = Gtk.CssProvider()
        css = """
        window { background-color: transparent; }
        .dock-container {
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 40px;
            margin: 0px;
            padding: 5px 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        .left-section { margin-right: 20px; }
        .launcher-button {
            background-color: transparent;
            border: 2px solid #ccc;
            border-radius: 50%;
            min-width: 40px;
            min-height: 40px;
            padding: 0;
            margin: 5px;
            box-shadow: none;
        }
        .launcher-button:hover { background-color: #f0f0f0; }
        .app-button {
            background-color: transparent;
            border: none;
            box-shadow: none;
            padding: 8px;
            border-radius: 12px;
            transition: all 0.2s;
            margin: 0 2px;
        }
        .app-button:hover {
            background-color: rgba(0, 0, 0, 0.08);
            margin-top: -4px;
            margin-bottom: 4px;
        }
        .right-section { margin-left: 20px; }
        .status-pill {
            background-color: #f0f0f0;
            border-radius: 30px;
            padding: 5px 15px;
            margin: 5px;
        }
        .status-icon { color: #555; }
        .clock-label {
            font-family: 'Noto Sans', sans-serif;
            font-weight: bold;
            color: #555;
            margin-left: 5px;
        }
        """
        css_provider.load_from_data(css.encode('utf-8'))
        
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_realize(self, widget):
        self.align_to_bottom()

    def on_map_event(self, widget, event):
        # ウィンドウが表示されたタイミングでも強制移動
        self.align_to_bottom()
        return False

    def align_to_bottom(self):
        # 【修正】Deprecatedな書き方を新しいAPIに変更
        # 旧: monitor_geo = screen.get_monitor_geometry(monitor_idx)
        
        display = Gdk.Display.get_default()
        monitor = display.get_monitor(0) # 0番目のモニター（プライマリ）を取得
        monitor_geo = monitor.get_geometry()
        
        dock_width = 1000 # ウィンドウ幅と合わせる
        dock_height = 80
        
        # 画面中央下に配置 (下端から20px浮かす)
        x = monitor_geo.x + (monitor_geo.width - dock_width) // 2
        y = monitor_geo.y + monitor_geo.height - dock_height - 20
        
        # GTKでの移動リクエスト
        self.move(x, y)
        self.resize(dock_width, dock_height)

        # 【修正ポイント2】Xlibを使ってOpenboxの配置ルールを無視して強制移動
        if HAS_XLIB:
            try:
                window = self.get_window()
                if window:
                    # GdkWindowからXIDを取得
                    xid = window.get_xid()
                    
                    # Xlibオブジェクトを作成
                    win = self.x_display.create_resource_object('window', xid)
                    
                    # configureリクエストを送信して強制的に座標とサイズを適用
                    # stack_mode=X.Above で最前面も保証
                    win.configure(
                        x=int(x),
                        y=int(y),
                        width=int(dock_width),
                        height=int(dock_height),
                        border_width=0,
                        stack_mode=X.Above
                    )
                    self.x_display.sync()
            except Exception as e:
                print(f"Xlib force move failed: {e}")

        return False

    def on_launcher_clicked(self, button):
        try:
            subprocess.Popen(["io.github.libredeb.lightpad"])
            print("Launched am-start")
        except FileNotFoundError:
            print("Error: am-start command not found.")
        except Exception as e:
            print(f"Error launching am-start: {e}")

    def update_clock(self):
        now = datetime.datetime.now()
        self.clock_label.set_text(now.strftime("%H:%M"))
        return True

    def _get_icon_for_class(self, wm_class_name):
        if not wm_class_name:
            return "application-x-executable"
        wm_class_name = wm_class_name.lower()
        mapping = {
            "gnome-terminal-server": "utilities-terminal",
            "gnome-terminal": "utilities-terminal",
            "nautilus": "system-file-manager",
            "org.gnome.nautilus": "system-file-manager",
            "thunar": "system-file-manager",
            "gedit": "text-editor",
            "org.gnome.gedit": "text-editor",
            "firefox": "firefox",
            "google-chrome": "google-chrome",
            "chromium": "chromium-browser",
            "code": "com.visualstudio.code",
            "spotify": "spotify-client",
            "vlc": "vlc",
            "discord": "discord",
        }
        if wm_class_name in mapping:
            return mapping[wm_class_name]

        for app in self.app_info_cache:
            app_id = app.get_id().lower()
            exe = app.get_executable()
            exe = exe.lower() if exe else ""
            if wm_class_name in app_id or (exe and wm_class_name in exe):
                icon = app.get_icon()
                if icon:
                    if isinstance(icon, Gio.ThemedIcon):
                        names = icon.get_names()
                        if names: return names[0]
        return wm_class_name

    def update_window_list(self):
        if not HAS_XLIB: return True
        try:
            prop = self.x_root.get_full_property(self.atom_client_list, X.AnyPropertyType)
            if not prop: return True
            window_ids = prop.value
        except: return True

        for child in self.center_box.get_children():
            self.center_box.remove(child)

        for win_id in window_ids:
            try:
                win = self.x_display.create_resource_object('window', win_id)
                wm_class = win.get_wm_class()
                if not wm_class: continue
                
                app_name = wm_class[0].lower()
                app_class = wm_class[1].lower()
                
                if "dock.ams.f5.si" in app_name or "modern dock" in app_name: continue
                if app_class in ["desktop_window", "dock", "gnome-shell", "gjs"]: continue

                btn = Gtk.Button()
                btn.get_style_context().add_class("app-button")
                
                icon_name = self._get_icon_for_class(app_class)
                img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
                
                if img.get_storage_type() == Gtk.ImageType.EMPTY:
                     icon_name_retry = self._get_icon_for_class(app_name)
                     img = Gtk.Image.new_from_icon_name(icon_name_retry, Gtk.IconSize.DIALOG)
                     if img.get_storage_type() == Gtk.ImageType.EMPTY:
                          img = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
                
                img.set_pixel_size(48)
                btn.add(img)
                btn.show_all()
                
                btn.connect("clicked", lambda b, wid=win_id: self.activate_window(wid))
                self.center_box.pack_start(btn, False, False, 0)
                
            except: continue
                
        return True

    def activate_window(self, win_id):
        try:
            win = self.x_display.create_resource_object('window', win_id)
            data = [2, X.CurrentTime, 0, 0, 0]
            ev = xevent.ClientMessage(
                window=win,
                client_type=self.atom_active_window,
                data=(32, data)
            )
            self.x_root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.x_display.flush()
        except Exception as e:
            print(f"Failed to activate window: {e}")

class DockApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = ModernDock(self)
        win.show_all()
        # present()は自動配置を誘発することがあるので、明示的な移動後は控えるか最後に呼ぶ
        # win.present() 

if __name__ == '__main__':
    app = DockApp()
    app.run(sys.argv)