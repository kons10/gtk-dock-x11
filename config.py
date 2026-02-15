# アプリケーションID
APP_ID = 'dock.ams.f5.si'

# --- 設定値 (ここを変えると全体が変わるよ) ---
DOCK_HEIGHT = 60      # シェルフの高さ
RADIUS_RATIO = 0.5    # 角の丸みの割合 (0.5 = 高さの半分)
WIDTH_RATIO = 1.0     # 画面横幅に対するシェルフの幅
CONTROL_RATIO = 0.8   # 右側ステータスバーの高さの割合 (1.0でシェルフと同じ高さ)

# ランチャー設定
# 起動したいアプリの .desktop ファイルIDを指定してね
# 例: "io.github.libredeb.lightpad.desktop" や "firefox.desktop" など
LAUNCHER_CMD = "io.github.libredeb.lightpad.desktop"

# テーマカラー設定 (必要ならここも調整できるようにしておいたよ)
COLORS = {
    "light": {
        "bg": "rgba(255, 255, 255, 0.85)",
        "text": "#333333",
        "hover": "rgba(0,0,0,0.05)"
    },
    "dark": {
        "bg": "rgba(35, 35, 35, 0.9)",
        "text": "#ffffff",
        "hover": "rgba(255,255,255,0.1)"
    }
}