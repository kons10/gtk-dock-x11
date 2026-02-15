import math
import time
from gi.repository import GLib

class Easing:
    """アニメーションの動きの質（イージング）を定義するクラス"""
    
    @staticmethod
    def linear(t):
        return t

    @staticmethod
    def ease_out_quad(t):
        return t * (2 - t)

    @staticmethod
    def ease_out_cubic(t):
        return 1 - pow(1 - t, 3)

    @staticmethod
    def ease_out_back(t):
        """少し行き過ぎてから戻る、ポップな動き"""
        c1 = 1.70158
        c3 = c1 + 1
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

class Animator:
    """値を0.0から1.0へ変化させるアニメーション管理クラス"""
    def __init__(self, duration_ms, update_callback, complete_callback=None, easing_func=None):
        self.duration = duration_ms / 1000.0  # 秒に変換
        self.update_callback = update_callback
        self.complete_callback = complete_callback
        self.start_time = 0
        self.easing_func = easing_func if easing_func else Easing.ease_out_quad
        self.timer_id = None

    def start(self):
        """アニメーションを開始"""
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
        
        self.start_time = time.time()
        # 約60FPS (16ms) で更新
        self.timer_id = GLib.timeout_add(16, self._tick)

    def stop(self):
        """アニメーションを強制停止"""
        if self.timer_id is not None:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

    def _tick(self):
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # 進捗率 (0.0 -> 1.0)
        progress = min(elapsed / self.duration, 1.0)
        
        # イージング適用
        eased_value = self.easing_func(progress)
        
        # コールバック呼び出し (UI更新)
        if self.update_callback:
            self.update_callback(eased_value)

        # 終了判定
        if progress >= 1.0:
            if self.complete_callback:
                self.complete_callback()
            self.timer_id = None
            return False  # タイマー停止
        
        return True  # タイマー継続