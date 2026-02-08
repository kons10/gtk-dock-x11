import sys
import datetime
import os
import gi

# GTK3を指定
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf

# X11操作用 (ライブラリとして本プロセス内で動作)
try:
    from Xlib import display, X
    from Xlib.protocol import event as xevent
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False
    print("Error: python3-xlib is not installed. Please run: sudo apt install python3-xlib")

# アプリケーションID (4文字の識別子を使用した指定の形式)
APP_ID = 'dock.ams.f5.si'

class ModernDock(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_title("Modern Dock")
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        
        # 画面の横幅を取得して初期サイズに設定
        gdk_display = Gdk.Display.get_default()
        monitor = gdk_display.get_primary_monitor() or gdk_display.get_monitor(0)
        rect = monitor.get_geometry()
        self.set_default_size(rect.width, 60)

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

        # --- CSSプロバイダの初期化 ---
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), 
            self.css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # テーマ監視の設定
        self.settings = Gtk.Settings.get_default()
        self.settings.connect("notify::gtk-theme-name", self.on_theme_changed)
        self.settings.connect("notify::gtk-application-prefer-dark-theme", self.on_theme_changed)
        
        self.update_css()
        
        self.icon_theme = Gtk.IconTheme.get_default()
        self.icon_cache = {}
        self.build_icon_cache()
        
        if HAS_XLIB:
            self.x_display = display.Display()
            self.x_root = self.x_display.screen().root
            self.atom_client_list = self.x_display.intern_atom('_NET_CLIENT_LIST')
            self.atom_active_window = self.x_display.intern_atom('_NET_ACTIVE_WINDOW')
            
        # --- レイアウト構築 ---
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main_box.get_style_context().add_class("dock-container")
        self.add(main_box)
        
        # [左] ランチャーセクション
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left_box.get_style_context().add_class("left-section")
        left_box.set_valign(Gtk.Align.CENTER)
        
        launcher_btn = Gtk.Button()
        launcher_btn.get_style_context().add_class("launcher-button")
        launcher_icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.BUTTON)
        launcher_btn.add(launcher_icon)
        # クリックイベントの接続
        launcher_btn.connect("clicked", self.on_launcher_clicked)
        
        left_box.pack_start(launcher_btn, False, False, 0)
        main_box.pack_start(left_box, False, False, 0)
        
        # [中] タスクバーセクション
        self.center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.center_box.get_style_context().add_class("center-section")
        self.center_box.set_halign(Gtk.Align.CENTER)
        self.center_box.set_valign(Gtk.Align.CENTER)
        
        main_box.pack_start(self.center_box, True, False, 0)
        
        # [右] ステータスセクション
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
        
        # タイマー設定
        GLib.timeout_add_seconds(1, self.update_clock)
        self.update_clock()
        
        if HAS_XLIB:
            GLib.timeout_add(1000, self.update_window_list)
            self.update_window_list()

        self.show_all()
        self.connect("realize", self.on_realize)
        self.connect("map-event", self.on_map_event)

    def build_icon_cache(self):
        """Gioを使用してインストール済みのアプリ情報を本プロセス内でキャッシュする"""
        apps = Gio.AppInfo.get_all()
        for app in apps:
            icon = app.get_icon()
            if not icon: continue
            
            icon_string = icon.to_string()
            if not icon_string: continue

            # 複数のキーでアイコンを引けるように登録
            app_id = app.get_id()
            if app_id:
                self.icon_cache[app_id.lower().replace(".desktop", "")] = icon_string
            
            executable = app.get_executable()
            if executable:
                try:
                    exe_name = os.path.basename(executable).lower().split()[0]
                    self.icon_cache[exe_name] = icon_string
                except: pass

            if isinstance(app, Gio.DesktopAppInfo):
                startup_wm_class = app.get_startup_wm_class()
                if startup_wm_class:
                    self.icon_cache[startup_wm_class.lower()] = icon_string

            display_name = app.get_name()
            if display_name:
                self.icon_cache[display_name.lower()] = icon_string

    def load_icon_pixbuf(self, icon_string, size):
        if not icon_string: return None
        if self.icon_theme.has_icon(icon_string):
            try:
                return self.icon_theme.load_icon(icon_string, size, Gtk.IconLookupFlags.FORCE_SIZE)
            except: pass
        if os.path.exists(icon_string):
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_string, size, size, True)
            except: pass
        try:
            return self.icon_theme.load_icon("application-default-icon", size, 0)
        except:
            return None

    def _is_dark_theme(self):
        try:
            theme_name = self.settings.get_property("gtk-theme-name")
            prefer_dark = self.settings.get_property("gtk-application-prefer-dark-theme")
            return prefer_dark or (theme_name and "dark" in theme_name.lower())
        except: return False

    def update_css(self):
        is_dark = self._is_dark_theme()
        bg = "rgba(30, 30, 30, 0.90)" if is_dark else "rgba(255, 255, 255, 0.95)"
        border = "#444444" if is_dark else "#cccccc"
        text = "#eeeeee" if is_dark else "#555555"
        pill = "rgba(255, 255, 255, 0.1)" if is_dark else "#f0f0f0"
        hover = "rgba(255, 255, 255, 0.15)" if is_dark else "rgba(0, 0, 0, 0.1)"
        shadow = "rgba(0, 0, 0, 0.5)" if is_dark else "rgba(0, 0, 0, 0.2)"

        css = f"""
        window {{ background-color: transparent; }}
        .dock-container {{
            background-color: {bg};
            border-radius: 0px; 
            margin: 0px;
            padding: 5px 15px;
            box-shadow: 0 4px 15px {shadow};
        }}
        .app-button {{
            background-color: transparent;
            border: none;
            padding: 4px;
            border-radius: 12px;
            margin: 0 2px;
        }}
        .app-button:hover {{ background-color: {hover}; }}
        .clock-label {{
            font-family: 'Roboto', sans-serif;
            font-weight: bold;
            color: {text};
            margin-left: 5px;
        }}
        .status-pill {{
            background-color: {pill};
            border-radius: 30px;
            padding: 5px 15px;
            margin: 5px;
        }}
        .status-icon {{ color: {text}; }}
        .launcher-button {{
            background-color: transparent;
            border: 2px solid {border};
            border-radius: 50%;
            min-width: 40px;
            min-height: 40px;
            color: {text};
        }}
        .launcher-button:hover {{ background-color: {hover}; }}
        """
        self.css_provider.load_from_data(css.encode('utf-8'))

    def on_theme_changed(self, settings, pspec):
        self.update_css()

    def on_realize(self, widget):
        self.align_to_bottom()

    def on_map_event(self, widget, event):
        self.align_to_bottom()
        return False

    def align_to_bottom(self):
        gdk_display = Gdk.Display.get_default()
        monitor = gdk_display.get_primary_monitor() or gdk_display.get_monitor(0)
        geo = monitor.get_geometry()
        
        w, h = geo.width, 60
        x, y = geo.x, geo.y + geo.height - h
        
        self.move(x, y)
        self.resize(w, h)

        if HAS_XLIB:
            try:
                window = self.get_window()
                if window:
                    win = self.x_display.create_resource_object('window', window.get_xid())
                    win.configure(x=int(x), y=int(y), width=int(w), height=int(h), stack_mode=X.Above)
                    self.x_display.sync()
            except: pass
        return False

    def on_launcher_clicked(self, button):
        """
        [重要] サブプロセスを使わずにGio経由でアプリを起動する。
        DesktopAppInfoを使うことで、OSのデスクトップ機能の一部として
        統合された形でアプリケーションが立ち上がるよ。
        """
        app_id = "io.github.libredeb.lightpad.desktop"
        # 1. デスクトップファイルIDから情報を取得
        app_info = Gio.DesktopAppInfo.new(app_id)
        
        if not app_info:
            # 2. IDで見つからない場合は実行コマンド名から検索
            app_info = Gio.AppInfo.create_from_commandline(
                "io.github.libredeb.lightpad", 
                "Lightpad", 
                Gio.AppInfoCreateFlags.NONE
            )

        if app_info:
            # アプリを起動 (サブプロセス管理はGIOに任せる)
            try:
                # コンテキストを使用して起動（必要に応じて画面指定なども可能）
                context = Gdk.AppLaunchContext()
                app_info.launch([], context)
            except Exception as e:
                print(f"Launch error: {e}")

    def update_clock(self):
        self.clock_label.set_text(datetime.datetime.now().strftime("%H:%M"))
        return True

    def _get_icon_string_for_class(self, wm_class_name):
        if not wm_class_name: return None
        name = wm_class_name.lower()
        mapping = {"gnome-terminal-server": "utilities-terminal", "pavucontrol": "multimedia-volume-control", "code": "vscode"}
        if name in mapping: return mapping[name]
        if name in self.icon_cache: return self.icon_cache[name]
        for k, v in self.icon_cache.items():
            if len(k) > 2 and (k in name or name in k): return v
        return name

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
                
                app_name, app_class = wm_class[0].lower(), wm_class[1].lower()
                if APP_ID in app_name or "modern dock" in app_name: continue
                if app_class in ["desktop_window", "dock", "gnome-shell", "xfce4-panel", "plank"]: continue

                icon_str = self._get_icon_string_for_class(app_class) or self._get_icon_string_for_class(app_name)
                pixbuf = self.load_icon_pixbuf(icon_str, 48) or self.load_icon_pixbuf("application-x-executable", 48)

                btn = Gtk.Button()
                btn.get_style_context().add_class("app-button")
                img = Gtk.Image()
                if pixbuf: img.set_from_pixbuf(pixbuf)
                btn.add(img)
                btn.show_all()
                btn.connect("clicked", lambda b, wid=win_id: self.activate_window(wid))
                self.center_box.pack_start(btn, False, False, 0)
            except: continue
        return True

    def activate_window(self, win_id):
        """Xlibライブラリの機能を用いて本プロセス内からウィンドウ操作を行う"""
        try:
            win = self.x_display.create_resource_object('window', win_id)
            data = [2, X.CurrentTime, 0, 0, 0]
            ev = xevent.ClientMessage(window=win, client_type=self.atom_active_window, data=(32, data))
            self.x_root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.x_display.flush()
        except Exception as e:
            print(f"Activation failed: {e}")

class DockApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
    def do_activate(self):
        win = ModernDock(self)
        win.show_all()

if __name__ == '__main__':
    app = DockApp()
    app.run(sys.argv)