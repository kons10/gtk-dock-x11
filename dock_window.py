import os
import datetime
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf

# 分割したファイルをインポート
import config
from x11_helper import X11Helper

class ModernDock(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_title("Modern Dock")
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        
        # X11ヘルパーの初期化
        self.x11 = X11Helper()
        
        # 初期サイズ設定
        self.dock_w = 0 # update_geometryで設定される
        self.update_geometry()

        # ウィンドウ設定
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.stick()
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        # 透過設定
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual and self.get_screen().is_composited():
            self.set_visual(visual)

        # CSS設定
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), 
            self.css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        self.settings = Gtk.Settings.get_default()
        self.settings.connect("notify::gtk-theme-name", lambda s, p: self.update_css())
        self.update_css()
        
        # アイコン関連
        self.icon_theme = Gtk.IconTheme.get_default()
        self.icon_cache = {}
        self.build_icon_cache()
            
        # --- レイアウト構築 ---
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.main_box.get_style_context().add_class("dock-container")
        self.add(self.main_box)
        
        self._setup_launcher()     # 左: ランチャー
        self._setup_taskbar()      # 中: タスクバー
        self._setup_status_area()  # 右: ステータス
        
        # 定期実行タスク
        GLib.timeout_add_seconds(1, self.update_clock)
        if self.x11.enabled:
            GLib.timeout_add(1000, self.update_window_list)

        self.connect("realize", lambda w: self.align_to_bottom())
        self.connect("map-event", lambda w, e: self.align_to_bottom())
        self.show_all()

    def _setup_launcher(self):
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left_box.set_valign(Gtk.Align.CENTER)
        
        self.launcher_btn = Gtk.Button()
        self.launcher_btn.get_style_context().add_class("launcher-button")
        
        launcher_icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.MENU)
        self.launcher_btn.add(launcher_icon)
        self.launcher_btn.connect("clicked", self.on_launcher_clicked)
        
        left_box.pack_start(self.launcher_btn, False, False, 0)
        self.main_box.pack_start(left_box, False, False, 0)

    def _setup_taskbar(self):
        self.center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.center_box.set_halign(Gtk.Align.CENTER)
        self.center_box.set_valign(Gtk.Align.CENTER)
        self.main_box.pack_start(self.center_box, True, False, 0)

    def _setup_status_area(self):
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        right_box.set_valign(Gtk.Align.CENTER)
        status_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_container.get_style_context().add_class("status-pill")
        
        self.clock_label = Gtk.Label(label="00:00")
        self.clock_label.get_style_context().add_class("clock-label")
        status_container.pack_end(self.clock_label, False, False, 0)
        
        for icon in ["audio-volume-medium-symbolic", "network-wireless-symbolic"]:
            img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
            img.get_style_context().add_class("status-icon")
            status_container.pack_end(img, False, False, 0)
            
        right_box.pack_start(status_container, False, False, 0)
        self.main_box.pack_start(right_box, False, False, 0)

    def update_css(self):
        is_dark = self._is_dark_theme()
        theme_colors = config.COLORS["dark"] if is_dark else config.COLORS["light"]
        
        radius = int(config.DOCK_HEIGHT * config.RADIUS_RATIO)
        btn_padding = int(config.DOCK_HEIGHT * 0.1)
        
        # 右側のバーの高さを計算
        control_height = int(config.DOCK_HEIGHT * config.CONTROL_RATIO)
        
        # 高さから上下の余白を引いて、適切なパディングを少しだけ入れる（微調整）
        # 高さを固定するために min-height を使い、padding は最小限にする
        pill_padding_v = 0 
        pill_padding_h = 12
        
        css = f"""
        window {{ background-color: transparent; }}
        .dock-container {{
            background-color: {theme_colors["bg"]};
            border-radius: {radius}px {radius}px 0px 0px; 
            padding: 0px 10px;
        }}
        .app-button {{
            background-color: transparent;
            border: none;
            padding: {btn_padding}px;
            border-radius: 12px;
            margin: 0 4px;
            transition: all 200ms;
        }}
        .app-button:hover {{ background-color: {theme_colors["hover"]}; }}
        .launcher-button {{
            background-color: transparent;
            border: none;
            border-radius: 50%;
            min-width: {int(config.DOCK_HEIGHT * 0.7)}px;
            min-height: {int(config.DOCK_HEIGHT * 0.7)}px;
        }}
        .clock-label {{
            font-size: {int(config.DOCK_HEIGHT * 0.25)}px;
            font-weight: 500;
            color: {theme_colors["text"]};
        }}
        .status-pill {{
            background-color: {theme_colors["hover"]};
            border-radius: 20px;
            padding: {pill_padding_v}px {pill_padding_h}px;
            min-height: {control_height}px;
        }}
        .status-icon {{ color: {theme_colors["text"]}; opacity: 0.8; }}
        """
        self.css_provider.load_from_data(css.encode('utf-8'))

    def update_geometry(self):
        gdk_display = Gdk.Display.get_default()
        monitor = gdk_display.get_primary_monitor() or gdk_display.get_monitor(0)
        rect = monitor.get_geometry()
        self.dock_w = int(rect.width * config.WIDTH_RATIO)
        self.set_default_size(self.dock_w, config.DOCK_HEIGHT)

    def align_to_bottom(self):
        gdk_display = Gdk.Display.get_default()
        monitor = gdk_display.get_primary_monitor() or gdk_display.get_monitor(0)
        geo = monitor.get_geometry()
        
        x = geo.x + (geo.width - self.dock_w) // 2
        y = geo.y + geo.height - config.DOCK_HEIGHT
        
        self.move(x, y)
        self.resize(self.dock_w, config.DOCK_HEIGHT)
        return False

    def build_icon_cache(self):
        # アプリ情報の収集
        apps = Gio.AppInfo.get_all()
        for app in apps:
            icon = app.get_icon()
            if not icon: continue
            icon_str = icon.to_string()
            
            # ID, 実行ファイル名, WM_CLASSで検索できるようにキャッシュ
            if app.get_id(): 
                self.icon_cache[app.get_id().lower().replace(".desktop","")] = icon_str
            if app.get_executable():
                try: 
                    self.icon_cache[os.path.basename(app.get_executable()).lower()] = icon_str
                except: pass
            if isinstance(app, Gio.DesktopAppInfo) and app.get_startup_wm_class():
                self.icon_cache[app.get_startup_wm_class().lower()] = icon_str

    def load_icon_pixbuf(self, icon_string, size):
        if not icon_string: return None
        try:
            if self.icon_theme.has_icon(icon_string):
                return self.icon_theme.load_icon(icon_string, size, Gtk.IconLookupFlags.FORCE_SIZE)
            elif os.path.exists(icon_string):
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_string, size, size, True)
            return self.icon_theme.load_icon("application-default-icon", size, 0)
        except: return None

    def update_window_list(self):
        window_ids = self.x11.get_window_list()
        
        # リストをクリア
        for child in self.center_box.get_children():
            self.center_box.remove(child)

        icon_size = int(config.DOCK_HEIGHT * 0.7)

        for win_id in window_ids:
            try:
                app_class = self.x11.get_window_class(win_id)
                if not app_class: continue
                
                # 自分自身やデスクトップなどは除外
                if config.APP_ID in app_class or "modern dock" in app_class: continue
                if app_class in ["desktop_window", "dock", "gnome-shell", "xfce4-panel"]: continue

                icon_str = self._get_icon_string_for_class(app_class)
                pixbuf = self.load_icon_pixbuf(icon_str, icon_size)

                btn = Gtk.Button()
                btn.get_style_context().add_class("app-button")
                img = Gtk.Image()
                if pixbuf: img.set_from_pixbuf(pixbuf)
                btn.add(img)
                btn.show_all()
                
                # クリック時の動作
                btn.connect("clicked", lambda b, wid=win_id: self.x11.activate_window(wid))
                self.center_box.pack_start(btn, False, False, 0)
            except: continue
        return True

    def _get_icon_string_for_class(self, name):
        mapping = {"gnome-terminal-server": "utilities-terminal", "code": "vscode"}
        if name in mapping: return mapping[name]
        if name in self.icon_cache: return self.icon_cache[name]
        return name

    def update_clock(self):
        self.clock_label.set_text(datetime.datetime.now().strftime("%H:%M"))
        return True

    def _is_dark_theme(self):
        try:
            theme = self.settings.get_property("gtk-theme-name").lower()
            return "dark" in theme or self.settings.get_property("gtk-application-prefer-dark-theme")
        except: return False

    def on_launcher_clicked(self, button):
        app_info = Gio.DesktopAppInfo.new("io.github.libredeb.lightpad.desktop")
        if app_info:
            try: app_info.launch([], Gdk.AppLaunchContext())
            except Exception as e: print(f"Launch error: {e}")