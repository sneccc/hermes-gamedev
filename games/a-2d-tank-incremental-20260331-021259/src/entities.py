import math
import pyray as rl
from constants import *
from utils import *


class Tank:
    def __init__(self):
        self.position = rl.Vector2(CENTER_X, CENTER_Y)
        self.rotation = 0.0  # Radians
        self.radius = TANK_RADIUS

        # Stats
        self.damage = BASE_DAMAGE
        self.fire_rate = BASE_FIRE_RATE  # Shots per second
        self.projectile_speed = BASE_PROJECTILE_SPEED
        self.multi_shot = 1
        self.crit_chance = 0.0  # 0.0 to 1.0
        self.scrap_multiplier = 1.0

        # State
        self.fire_cooldown = 0.0

    def draw(self):
        # Draw barrel(s)
        barrel_angle_offset = 0.2
        num_barrels = min(self.multi_shot, 5)  # Cap at 5 for visual clarity

        start_angle = -((num_barrels - 1) * barrel_angle_offset) / 2

        for i in range(num_barrels):
            angle = self.rotation + start_angle + (i * barrel_angle_offset)
            end_x = self.position.x + math.cos(angle) * BARREL_LENGTH
            end_y = self.position.y + math.sin(angle) * BARREL_LENGTH

            rl.draw_line_ex(
                self.position, rl.Vector2(end_x, end_y), BARREL_WIDTH, BARREL_COLOR
            )

        # Draw base
        rl.draw_circle(
            int(self.position.x), int(self.position.y), self.radius, TANK_COLOR
        )
        rl.draw_circle(
            int(self.position.x),
            int(self.position.y),
            int(self.radius * 0.6),
            rl.Color(0, 158, 47, 255),
        )


class Projectile:
    def __init__(self, pos, dir_vec, speed, damage, is_crit=False):
        self.position = rl.Vector2(pos.x, pos.y)
        self.velocity = vector2_scale(dir_vec, speed)
        self.damage = damage
        self.is_crit = is_crit
        self.radius = 4
        self.active = True
        self.color = (
            PROJECTILE_COLOR if not is_crit else rl.Color(255, 0, 0, 255)
        )  # Red if crit

    def update(self, dt):
        self.position.x += self.velocity.x * dt
        self.position.y += self.velocity.y * dt

        # Deactivate if out of bounds
        if (
            self.position.x < 0
            or self.position.x > WINDOW_WIDTH
            or self.position.y < 0
            or self.position.y > WINDOW_HEIGHT
        ):
            self.active = False

    def draw(self):
        if self.active:
            rl.draw_circle(
                int(self.position.x), int(self.position.y), self.radius, self.color
            )


class Enemy:
    def __init__(self, pos, enemy_type, health, scrap_value):
        self.position = rl.Vector2(pos.x, pos.y)
        self.type = enemy_type
        self.max_health = health
        self.health = health
        self.scrap_value = scrap_value
        self.active = True

        self.color = ENEMY_COLORS.get(enemy_type, rl.WHITE)
        self.speed = BASE_ENEMY_SPEED

        # Dimensions based on type
        if enemy_type == "square":
            self.radius = 15  # Used for collision and rough sizing
            self.sides = 4
        elif enemy_type == "triangle":
            self.radius = 18
            self.sides = 3
            self.speed *= 1.5  # Triangles are faster
        elif enemy_type == "hexagon":
            self.radius = 20
            self.sides = 6
            self.speed *= 0.8  # Hexagons are slower but tankier
        else:
            self.radius = 15
            self.sides = 4

        self.rotation = 0.0

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.active = False

    def update(self, dt, target_pos):
        if not self.active:
            return

        # Move towards target
        direction = vector2_normalize(vector2_sub(target_pos, self.position))
        self.position.x += direction.x * self.speed * dt
        self.position.y += direction.y * self.speed * dt

        # Rotate
        self.rotation += 1.0 * dt

    def draw(self):
        if not self.active:
            return

        # Draw health bar if damaged
        if self.health < self.max_health:
            hp_percent = max(0, self.health / self.max_health)
            bar_width = self.radius * 2
            bar_height = 4
            x = int(self.position.x - self.radius)
            y = int(self.position.y - self.radius - 10)

            rl.draw_rectangle(x, y, int(bar_width), bar_height, rl.RED)
            rl.draw_rectangle(x, y, int(bar_width * hp_percent), bar_height, rl.GREEN)

        # Draw shape
        rl.draw_poly(
            self.position,
            self.sides,
            self.radius,
            self.rotation * rl.RAD2DEG,
            self.color,
        )
        rl.draw_poly_lines(
            self.position, self.sides, self.radius, self.rotation * rl.RAD2DEG, rl.WHITE
        )


class Particle:
    def __init__(self, pos, color):
        self.position = rl.Vector2(pos.x, pos.y)
        angle = rl.get_random_value(0, 360) * rl.DEG2RAD
        speed = rl.get_random_value(50, 150)
        self.velocity = rl.Vector2(math.cos(angle) * speed, math.sin(angle) * speed)
        self.color = color
        self.life = 1.0
        self.radius = float(rl.get_random_value(2, 5))
        self.active = True

    def update(self, dt):
        self.position.x += self.velocity.x * dt
        self.position.y += self.velocity.y * dt
        self.life -= dt * 2.0  # Fade out
        self.radius *= 0.95

        if self.life <= 0:
            self.active = False

    def draw(self):
        if self.active:
            c = rl.Color(
                self.color.r, self.color.g, self.color.b, int(255 * max(0, self.life))
            )
            rl.draw_circle(int(self.position.x), int(self.position.y), self.radius, c)
