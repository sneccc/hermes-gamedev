import pyray as rl
import math
from src.utils import get_distance, lerp_vec2
from src.constants import COLORS, TOWER_DATA, ENEMY_DATA

class Core:
    def __init__(self, pos):
        self.pos = pos
        self.health = 100
        self.radius = 40

    def take_damage(self, amount):
        self.health -= amount
        return self.health <= 0

    def draw(self):
        rl.draw_circle_v(self.pos, self.radius, COLORS["core"])
        rl.draw_circle_lines(int(self.pos.x), int(self.pos.y), self.radius + 5, rl.GREEN)

class Enemy:
    def __init__(self, path, enemy_type):
        self.path = path
        self.type = enemy_type
        stats = ENEMY_DATA[enemy_type]
        self.hp = stats["hp"]
        self.max_hp = stats["hp"]
        self.speed = stats["speed"]
        self.value = stats["value"]
        self.color = COLORS[enemy_type]

        self.segment = 0
        self.t = 0.0
        self.pos = rl.Vector2(path[0].x, path[0].y)
        self.finished = False

    def update(self, dt):
        if self.segment >= len(self.path) - 1:
            self.finished = True
            return

        p1 = self.path[self.segment]
        p2 = self.path[self.segment + 1]
        dist = get_distance(p1, p2)
        if dist < 1:
            self.segment += 1
            return

        self.t += (self.speed * dt) / dist

        if self.t >= 1.0:
            self.t = 0.0
            self.segment += 1
            if self.segment >= len(self.path) - 1:
                self.finished = True
                return

        self.pos = lerp_vec2(self.path[self.segment], self.path[self.segment+1], self.t)

    def take_damage(self, amount):
        self.hp -= amount
        return self.hp <= 0

    def draw(self):
        rl.draw_poly(self.pos, 3 if self.type == "swarmer" else 4, 15, 0, self.color)
        # Health bar
        rl.draw_rectangle(int(self.pos.x - 10), int(self.pos.y - 20), 20, 4, rl.BLACK)
        rl.draw_rectangle(int(self.pos.x - 10), int(self.pos.y - 20), int(20 * (self.hp / self.max_hp)), 4, rl.GREEN)

class Projectile:
    def __init__(self, pos, target, damage, speed, color):
        self.pos = rl.Vector2(pos.x, pos.y)
        self.target = target
        self.damage = damage
        self.speed = speed
        self.color = color
        self.hit = False

    def update(self, dt):
        if not self.target or self.target.hp <= 0:
            self.hit = True
            return

        dir_x = self.target.pos.x - self.pos.x
        dir_y = self.target.pos.y - self.pos.y
        dist = math.sqrt(dir_x**2 + dir_y**2)
        if dist < 5:
            self.target.take_damage(self.damage)
            self.hit = True
            return

        self.pos.x += (dir_x / dist) * self.speed * dt
        self.pos.y += (dir_y / dist) * self.speed * dt

    def draw(self):
        rl.draw_circle_v(self.pos, 4, self.color)

class Tower:
    def __init__(self, pos, tower_type):
        self.pos = pos
        self.type = tower_type
        stats = TOWER_DATA[tower_type]
        self.range = stats["range"]
        self.damage = stats["damage"]
        self.cooldown = stats["cooldown"]
        self.timer = 0
        self.color = COLORS[tower_type]

    def update(self, dt, enemies, projectiles):
        self.timer -= dt
        if self.timer <= 0:
            target = self.find_target(enemies)
            if target:
                projectiles.append(Projectile(self.pos, target, self.damage, 400, self.color))
                self.timer = self.cooldown

    def find_target(self, enemies):
        best_target = None
        min_dist = self.range
        for e in enemies:
            d = get_distance(self.pos, e.pos)
            if d < min_dist:
                min_dist = d
                best_target = e
        return best_target

    def draw(self):
        rl.draw_rectangle_v(rl.Vector2(self.pos.x - 15, self.pos.y - 15), rl.Vector2(30, 30), self.color)
        rl.draw_circle_lines(int(self.pos.x), int(self.pos.y), self.range, rl.fade(self.color, 0.2))
