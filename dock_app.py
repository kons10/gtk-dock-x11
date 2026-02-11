import sys
import datetime
import os
import gi

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

# アプリケーションID
APP_ID = 'dock.ams.f5.si'

# --- 設定値 (ここを変えると全体が変わるよ) ---
DOCK_HEIGHT = 60      # シェルフの高さ
RADIUS_RATIO = 0.5    # 角の丸みの割合 (0.5 = 高さの半分)
WIDTH_RATIO = 1    # 画面横幅に対するシェルフの幅

class ModernDock(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_title("Modern Dock")
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        
        # 初期サイズ設定
        self.update_geometry()

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

        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), 
            self.css_provider, 
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        self.settings = Gtk.Settings.get_default()
        self.settings.connect("notify::gtk-theme-name", lambda s, p: self.update_css())
        
        self.update_css()
        
        self.icon_theme = Gtk.IconTheme.get_default()
        self.icon_cache = {}
        self.build_icon_cache()
        
        if HAS_XLIB:
            self.x_display = display.Display()
            self.x_root = self.x_display.screen().root
            self.atom_client_list = self.x_display.intern_atom('_NET_CLIENT_LIST')
            self.atom_active_window = self.x_display.intern_atom('_NET_ACTIVE_WINDOW')
            
        # レイアウト
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.main_box.get_style_context().add_class("dock-container")
        self.add(self.main_box)
        
        # [左] ランチャー
        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left_box.set_valign(Gtk.Align.CENTER)
        self.launcher_btn = Gtk.Button()
        self.launcher_btn.get_style_context().add_class("launcher-button")
        # アイコンサイズもドックの高さに合わせて調整
        l_icon_size = int(DOCK_HEIGHT * 0.5)
        launcher_icon = Gtk.Image.new_from_icon_name("view-app-grid-symbolic", Gtk.IconSize.MENU)
        self.launcher_btn.add(launcher_icon)
        self.launcher_btn.connect("clicked", self.on_launcher_clicked)
        left_box.pack_start(self.launcher_btn, False, False, 0)
        self.main_box.pack_start(left_box, False, False, 0)
        
        # [中] タスクバー
        self.center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.center_box.set_halign(Gtk.Align.CENTER)
        self.center_box.set_valign(Gtk.Align.CENTER)
        self.main_box.pack_start(self.center_box, True, False, 0)
        
        # [右] ステータス
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
        
        GLib.timeout_add_seconds(1, self.update_clock)
        if HAS_XLIB:
            GLib.timeout_add(1000, self.update_window_list)

        self.show_all()
        self.connect("realize", lambda w: self.align_to_bottom())
        self.connect("map-event", lambda w, e: self.align_to_bottom())

    def update_css(self):
        is_dark = self._is_dark_theme()
        # 高さに合わせた割合計算
        radius = int(DOCK_HEIGHT * RADIUS_RATIO)
        # アイコンの余白感
        btn_padding = int(DOCK_HEIGHT * 0.1)
        
        bg = "rgba(255, 255, 255, 0.85)" if not is_dark else "rgba(35, 35, 35, 0.9)"
        text = "#333333" if not is_dark else "#ffffff"
        hover = "rgba(0,0,0,0.05)" if not is_dark else "rgba(255,255,255,0.1)"

        css = f"""
        window {{ background-color: transparent; }}
        .dock-container {{
            background-color: {bg};
            /* 上の角だけを高さの割合で丸くする */
            border-radius: {radius}px {radius}px 0px 0px; 
            padding: 0px 20px;
        }}
        .app-button {{
            background-color: transparent;
            border: none;
            padding: {btn_padding}px;
            border-radius: 12px;
            margin: 0 4px;
            transition: all 200ms;
        }}
        .app-button:hover {{ background-color: {hover}; }}
        .launcher-button {{
            background-color: transparent;
            border: none;
            border-radius: 50%;
            min-width: {int(DOCK_HEIGHT * 0.7)}px;
            min-height: {int(DOCK_HEIGHT * 0.7)}px;
        }}
        .clock-label {{
            font-size: {int(DOCK_HEIGHT * 0.25)}px;
            font-weight: 500;
            color: {text};
        }}
        .status-pill {{
            background-color: {hover};
            border-radius: 20px;
            padding: 4px 12px;
        }}
        .status-icon {{ color: {text}; opacity: 0.8; }}
        """
        self.css_provider.load_from_data(css.encode('utf-8'))

    def update_geometry(self):
        gdk_display = Gdk.Display.get_default()
        monitor = gdk_display.get_primary_monitor() or gdk_display.get_monitor(0)
        rect = monitor.get_geometry()
        self.dock_w = int(rect.width * WIDTH_RATIO)
        self.set_default_size(self.dock_w, DOCK_HEIGHT)

    def align_to_bottom(self):
        gdk_display = Gdk.Display.get_default()
        monitor = gdk_display.get_primary_monitor() or gdk_display.get_monitor(0)
        geo = monitor.get_geometry()
        
        x = geo.x + (geo.width - self.dock_w) // 2
        y = geo.y + geo.height - DOCK_HEIGHT
        
        self.move(x, y)
        self.resize(self.dock_w, DOCK_HEIGHT)
        return False

    def build_icon_cache(self):
        apps = Gio.AppInfo.get_all()
        for app in apps:
            icon = app.get_icon()
            if not icon: continue
            icon_str = icon.to_string()
            if app.get_id(): self.icon_cache[app.get_id().lower().replace(".desktop","")] = icon_str
            if app.get_executable():
                try: self.icon_cache[os.path.basename(app.get_executable()).lower()] = icon_str
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
        if not HAS_XLIB: return True
        try:
            prop = self.x_root.get_full_property(self.atom_client_list, X.AnyPropertyType)
            if not prop: return True
            window_ids = prop.value
        except: return True

        for child in self.center_box.get_children():
            self.center_box.remove(child)

        # アイコンサイズは高さの70%くらいにする
        icon_size = int(DOCK_HEIGHT * 0.7)

        for win_id in window_ids:
            try:
                win = self.x_display.create_resource_object('window', win_id)
                wm_class = win.get_wm_class()
                if not wm_class: continue
                
                app_class = wm_class[1].lower()
                if APP_ID in app_class or "modern dock" in app_class: continue
                if app_class in ["desktop_window", "dock", "gnome-shell", "xfce4-panel"]: continue

                icon_str = self._get_icon_string_for_class(app_class)
                pixbuf = self.load_icon_pixbuf(icon_str, icon_size)

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

    def _get_icon_string_for_class(self, name):
        mapping = {"gnome-terminal-server": "utilities-terminal", "code": "vscode"}
        if name in mapping: return mapping[name]
        if name in self.icon_cache: return self.icon_cache[name]
        return name

    def activate_window(self, win_id):
        try:
            win = self.x_display.create_resource_object('window', win_id)
            data = [2, X.CurrentTime, 0, 0, 0]
            ev = xevent.ClientMessage(window=win, client_type=self.atom_active_window, data=(32, data))
            self.x_root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.x_display.flush()
        except: pass

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

class DockApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
    def do_activate(self):
        win = ModernDock(self)
        win.show_all()

if __name__ == '__main__':
    app = DockApp()
    app.run(sys.argv)