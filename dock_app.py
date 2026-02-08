import sys
import datetime
import os
import gi
import subprocess 

# GTK3を指定
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf

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
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_default_size(1000, 60)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.stick()
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual and self.get_screen().is_composited():
            self.set_visual(visual)

        self.load_css()
        
        # アイコンテーマの取得（LightPadのロジック用）
        self.icon_theme = Gtk.IconTheme.get_default()
        
        # キャッシュ構築
        self.icon_cache = {}
        self.build_icon_cache()
        
        if HAS_XLIB:
            self.x_display = display.Display()
            self.x_root = self.x_display.screen().root
            self.atom_client_list = self.x_display.intern_atom('_NET_CLIENT_LIST')
            self.atom_active_window = self.x_display.intern_atom('_NET_ACTIVE_WINDOW')
            
        # --- レイアウト ---
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main_box.get_style_context().add_class("dock-container")
        self.add(main_box)
        
        # [左] ランチャー
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left_box.get_style_context().add_class("left-section")
        left_box.set_valign(Gtk.Align.CENTER)
        
        launcher_btn = Gtk.Button()
        launcher_btn.get_style_context().add_class("launcher-button")
        launcher_icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.BUTTON)
        launcher_btn.add(launcher_icon)
        launcher_btn.connect("clicked", self.on_launcher_clicked)
        
        left_box.pack_start(launcher_btn, False, False, 0)
        main_box.pack_start(left_box, False, False, 0)
        
        # [中] アプリアイコン
        self.center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.center_box.get_style_context().add_class("center-section")
        self.center_box.set_halign(Gtk.Align.CENTER)
        self.center_box.set_valign(Gtk.Align.CENTER)
        
        main_box.pack_start(self.center_box, True, False, 0)
        
        # [右] ステータス
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
        
        # --- タイマー ---
        GLib.timeout_add_seconds(1, self.update_clock)
        self.update_clock()
        
        if HAS_XLIB:
            GLib.timeout_add(1000, self.update_window_list)
            self.update_window_list()

        self.show_all()
        self.connect("realize", self.on_realize)
        self.connect("map-event", self.on_map_event)

    def build_icon_cache(self):
        """
        LightPadのロジックを参考に、全アプリのアイコン情報をキャッシュする。
        Gio.FileIcon (パス指定) も Gio.ThemedIcon (テーマ名) も全て文字列化して保存する。
        """
        print("Building LightPad-style icon cache...")
        apps = Gio.AppInfo.get_all()
        for app in apps:
            icon = app.get_icon()
            if not icon: continue
            
            # 【LightPad再現】 アイコンを文字列化して取得
            # これにより "firefox" のような名前も、"/usr/share/pixmaps/foo.png" のようなパスも両方取れる
            icon_string = icon.to_string()
            if not icon_string: continue

            # 辞書への登録 (キーは小文字化)
            
            # 1. Desktop ID
            app_id = app.get_id()
            if app_id:
                clean_id = app_id.lower().replace(".desktop", "")
                self.icon_cache[clean_id] = icon_string
            
            # 2. 実行ファイル名
            executable = app.get_executable()
            if executable:
                try:
                    exe_name = os.path.basename(executable).lower().split()[0]
                    self.icon_cache[exe_name] = icon_string
                except: pass

            # 3. StartupWMClass
            if isinstance(app, Gio.DesktopAppInfo):
                startup_wm_class = app.get_startup_wm_class()
                if startup_wm_class:
                    self.icon_cache[startup_wm_class.lower()] = icon_string

            # 4. 表示名
            display_name = app.get_name()
            if display_name:
                self.icon_cache[display_name.lower()] = icon_string

        print(f"Icon cache built: {len(self.icon_cache)} entries.")

    def load_icon_pixbuf(self, icon_string, size):
        """
        LightPadの DesktopEntries.vala のロジックをPythonで再現。
        アイコン名、絶対パス、/usr/share/pixmaps 内のファイルを順に探して Pixbuf を返す。
        """
        if not icon_string:
            return None

        # 1. テーマアイコンとして検索 (LightPad: icon_theme.has_icon)
        if self.icon_theme.has_icon(icon_string):
            try:
                # scale_simple相当のことはGTKが内部でやるが、load_iconで取得
                return self.icon_theme.load_icon(icon_string, size, Gtk.IconLookupFlags.FORCE_SIZE)
            except Exception:
                pass

        # 2. 絶対パスとして存在チェック (LightPad: GLib.File.new_for_path(...).query_exists())
        if os.path.exists(icon_string):
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_string, size, size, True)
            except Exception:
                pass

        # 3. /usr/share/pixmaps/ 内の検索 (LightPad: Resources.PIXMAPS_DIR + name + ext)
        # LightPadは .png, .svg, .xpm の順で探している
        pixmaps_dir = "/usr/share/pixmaps/"
        extensions = [".png", ".svg", ".xpm"]
        
        for ext in extensions:
            path = os.path.join(pixmaps_dir, icon_string + ext)
            if os.path.exists(path):
                try:
                    return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
                except Exception:
                    pass

        # 4. それでもダメなら汎用アイコン
        try:
            return self.icon_theme.load_icon("application-default-icon", size, 0)
        except:
            return None

    def load_css(self):
        css_provider = Gtk.CssProvider()
        # LightPadのCSSを参考にしつつ、Dock用に調整
        css = """
        window { background-color: transparent; }
        .dock-container {
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 40px;
            margin: 0px;
            padding: 5px 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        .app-button {
            background-color: transparent;
            border: none;
            box-shadow: none;
            padding: 4px;
            border-radius: 12px;
            margin: 0 2px;
        }
        .app-button:hover {
            background-color: rgba(0, 0, 0, 0.1);
        }
        .clock-label {
            font-family: 'Noto Sans', sans-serif;
            font-weight: bold;
            color: #555;
            margin-left: 5px;
        }
        .status-pill {
            background-color: #f0f0f0;
            border-radius: 30px;
            padding: 5px 15px;
            margin: 5px;
        }
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
        """
        css_provider.load_from_data(css.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_realize(self, widget):
        self.align_to_bottom()

    def on_map_event(self, widget, event):
        self.align_to_bottom()
        return False

    def align_to_bottom(self):
        display = Gdk.Display.get_default()
        monitor = display.get_monitor(0)
        monitor_geo = monitor.get_geometry()
        dock_width = 1000
        dock_height = 80
        x = monitor_geo.x + (monitor_geo.width - dock_width) // 2
        y = monitor_geo.y + monitor_geo.height - dock_height - 20
        self.move(x, y)
        self.resize(dock_width, dock_height)

        if HAS_XLIB:
            try:
                window = self.get_window()
                if window:
                    xid = window.get_xid()
                    win = self.x_display.create_resource_object('window', xid)
                    win.configure(
                        x=int(x), y=int(y), width=int(dock_width), height=int(dock_height),
                        border_width=0, stack_mode=X.Above
                    )
                    self.x_display.sync()
            except Exception as e:
                print(f"Xlib force move failed: {e}")
        return False

    def on_launcher_clicked(self, button):
        try:
            subprocess.Popen(["io.github.libredeb.lightpad"])
        except Exception as e:
            print(f"Error: {e}")

    def update_clock(self):
        now = datetime.datetime.now()
        self.clock_label.set_text(now.strftime("%H:%M"))
        return True

    def _get_icon_string_for_class(self, wm_class_name):
        """WM_CLASS から キャッシュされたアイコン文字列（名前またはパス）を取得"""
        if not wm_class_name: return None
        wm_class_name = wm_class_name.lower()
        
        # 手動マッピング（必要なら）
        manual_mapping = {
            "gnome-terminal-server": "utilities-terminal",
            "pavucontrol": "multimedia-volume-control",
        }
        if wm_class_name in manual_mapping:
            return manual_mapping[wm_class_name]

        # キャッシュ検索
        if wm_class_name in self.icon_cache:
            return self.icon_cache[wm_class_name]
            
        # 部分一致検索
        for key, icon in self.icon_cache.items():
            if len(key) > 2 and (key in wm_class_name or wm_class_name in key):
                return icon

        # 見つからない場合はクラス名そのものを返す（テーマにあるかもしれない）
        return wm_class_name

    def update_window_list(self):
        if not HAS_XLIB: return True
        try:
            prop = self.x_root.get_full_property(self.atom_client_list, X.AnyPropertyType)
            if not prop: return True
            window_ids = prop.value
        except: return True

        # 子ウィジェットをクリア
        for child in self.center_box.get_children():
            self.center_box.remove(child)

        for win_id in window_ids:
            try:
                win = self.x_display.create_resource_object('window', win_id)
                wm_class = win.get_wm_class()
                if not wm_class: continue
                
                app_name = wm_class[0].lower()
                app_class = wm_class[1].lower()
                
                # 自分自身やDock類は除外
                if "dock.ams.f5.si" in app_name or "modern dock" in app_name: continue
                if app_class in ["desktop_window", "dock", "gnome-shell", "xfce4-panel", "plank"]: continue

                # アイコン文字列（名前またはパス）の解決
                icon_string = self._get_icon_string_for_class(app_class)
                if not icon_string:
                    icon_string = self._get_icon_string_for_class(app_name)
                
                # ★LightPad方式でPixbufをロード★
                pixbuf = self.load_icon_pixbuf(icon_string, 48)
                
                # 失敗したら汎用アイコン
                if not pixbuf:
                    pixbuf = self.load_icon_pixbuf("application-x-executable", 48)

                # ボタン作成
                btn = Gtk.Button()
                btn.get_style_context().add_class("app-button")
                
                img = Gtk.Image()
                if pixbuf:
                    img.set_from_pixbuf(pixbuf)
                
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
            print(f"Failed to activate: {e}")

class DockApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
    def do_activate(self):
        win = ModernDock(self)
        win.show_all()

if __name__ == '__main__':
    app = DockApp()
    app.run(sys.argv)
