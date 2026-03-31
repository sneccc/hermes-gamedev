import pyray as rl
import math
import random
from src.constants import SCREEN_WIDTH, SCREEN_HEIGHT, COLORS, PATH_POINTS, SLOTS, TOWER_DATA, ENEMY_DATA
from src.entities import Core, Enemy, Tower, Projectile
from src.ui import Interface
from src.utils import ParticleSystem, get_distance

class GameEngine:
    def __init__(self):
        self.reset()
        self.ui = Interface()
        self.particles = ParticleSystem()
        
    def reset(self):
        self.core = Core(PATH_POINTS[-1])
        self.enemies = []
        self.towers = {} # index: Tower
        self.projectiles = []
        self.credits = 200
        self.wave = 0
        self.wave_active = False
        self.spawn_timer = 0
        self.enemies_to_spawn = 0
        self.game_over = False
        self.paused = True

    def start_wave(self):
        if self.wave_active: return
        self.wave += 1
        self.wave_active = True
        self.enemies_to_spawn = 5 + self.wave * 2
        self.spawn_timer = 0

    def update(self, dt):
        if self.game_over or self.paused:
            if rl.is_key_pressed(rl.KEY_SPACE):
                if self.game_over:
                    self.reset()
                self.paused = False
            return

        if rl.is_key_pressed(rl.KEY_SPACE) and not self.wave_active:
            self.start_wave()

        # Spawning
        if self.wave_active and self.enemies_to_spawn > 0:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                etype = "tank" if self.wave >= 5 and random.random() < 0.2 else "swarmer"
                self.enemies.append(Enemy(PATH_POINTS, etype))
                self.enemies_to_spawn -= 1
                self.spawn_timer = 0.8 / (1 + self.wave * 0.1)

        # Tower placement
        slot_idx = self.ui.get_clicked_slot(SLOTS)
        if slot_idx != -1 and slot_idx not in self.towers:
            cost = 50 # Default pulse
            ttype = "pulse"
            if rl.is_key_down(rl.KEY_TWO):
                cost = 150
                ttype = "beam"
            
            if self.credits >= cost:
                self.credits -= cost
                self.towers[slot_idx] = Tower(SLOTS[slot_idx], ttype)

        # Updates
        for e in self.enemies[:]:
            e.update(dt)
            if e.finished:
                if self.core.take_damage(10):
                    self.game_over = True
                self.enemies.remove(e)
            elif e.hp <= 0:
                self.credits += e.value
                self.particles.emit(e.pos, e.color)
                self.enemies.remove(e)

        for t in self.towers.values():
            t.update(dt, self.enemies, self.projectiles)

        for p in self.projectiles[:]:
            p.update(dt)
            if p.hit:
                if p.target in self.enemies:
                    if p.target.take_damage(p.damage):
                        pass # Handled in enemy loop
                self.projectiles.remove(p)
            elif get_distance(p.pos, p.target.pos) > 1000: # Cleanup
                self.projectiles.remove(p)

        self.particles.update(dt)

        if self.wave_active and not self.enemies and self.enemies_to_spawn <= 0:
            self.wave_active = False
            self.credits += 50 # Wave bonus

    def draw(self):
        rl.clear_background(COLORS["bg"])
        
        # Draw path
        for i in range(len(PATH_POINTS)-1):
            rl.draw_line_ex(PATH_POINTS[i], PATH_POINTS[i+1], 30, COLORS["path"])
            rl.draw_line_ex(PATH_POINTS[i], PATH_POINTS[i+1], 34, COLORS["neon"])

        # Draw slots
        for i, s in enumerate(SLOTS):
            color = rl.GRAY if i not in self.towers else rl.DARKGRAY
            rl.draw_circle_v(s, 20, color)
            if i not in self.towers:
                rl.draw_circle_lines(int(s.x), int(s.y), 20, rl.DARKGRAY)

        self.core.draw()
        for t in self.towers.values(): t.draw()
        for e in self.enemies: e.draw()
        for p in self.projectiles: p.draw()
        self.particles.draw()

        self.ui.draw_hud(self.credits, self.core.health, self.wave)

        if self.paused:
            self.ui.draw_menu("NEON BASTION")
        elif self.game_over:
            self.ui.draw_menu("GAME OVER")

def main():
    rl.init_window(SCREEN_WIDTH, SCREEN_HEIGHT, "Neon Bastion")
    rl.set_target_fps(60)
    
    engine = GameEngine()
    
    while not rl.window_should_close():
        dt = rl.get_frame_time()
        engine.update(dt)
        
        rl.begin_drawing()
        engine.draw()
        rl.end_drawing()
        
    rl.close_window()

if __name__ == "__main__":
    main()
