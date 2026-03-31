import pyray as rl
from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT, COLORS, TOWER_DATA

class Interface:
    def __init__(self):
        self.font_size = 20

    def draw_hud(self, credits, health, wave):
        rl.draw_rectangle(0, 0, SCREEN_WIDTH, 40, COLORS["ui_bg"])
        rl.draw_text(f"CREDITS: {credits}", 20, 10, self.font_size, rl.GOLD)
        rl.draw_text(f"CORE HEALTH: {health}", 300, 10, self.font_size, rl.RED)
        rl.draw_text(f"WAVE: {wave}", 600, 10, self.font_size, rl.RAYWHITE)
        rl.draw_text("SPACE: Start Wave | 1: Pulse (50) | 2: Beam (150)", 800, 10, 15, rl.GRAY)

    def draw_menu(self, title):
        rl.draw_rectangle(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, rl.fade(rl.BLACK, 0.8))
        rl.draw_text(title, SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 50, 40, rl.RAYWHITE)
        rl.draw_text("Press SPACE to Start", SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 20, 20, rl.GRAY)

    def get_clicked_slot(self, slots):
        if rl.is_mouse_button_pressed(rl.MOUSE_LEFT_BUTTON):
            m_pos = rl.get_mouse_position()
            for i, s in enumerate(slots):
                if rl.check_collision_point_circle(m_pos, s, 20):
                    return i
        return -1
