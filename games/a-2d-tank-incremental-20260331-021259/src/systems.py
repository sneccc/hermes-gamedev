import pyray as rl
from entities import Projectile, Enemy, Particle, Tank
from utils import (
    vector2_distance,
    angle_between_vectors,
    vector2_normalize,
    vector2_sub,
)
import random
import math


class GameSystem:
    def __init__(self):
        self.tank = Tank()
        self.projectiles = []
        self.enemies = []
        self.particles = []

        self.scrap = 0
        self.wave = 1

        self.enemy_spawn_timer = 0
        self.current_enemy_spawn_rate = 2.0

        # Upgrades
        self.upgrades = {
            "fire_rate": {"level": 1, "cost": 10},
            "damage": {"level": 1, "cost": 15},
            "proj_speed": {"level": 1, "cost": 10},
            "multi_shot": {"level": 1, "cost": 50},
            "crit_chance": {"level": 0, "cost": 25},  # 0.05 per level
            "scrap_mult": {"level": 1, "cost": 30},
        }

    def update(self, dt):
        self._handle_spawning(dt)
        self._handle_tank(dt)
        self._update_entities(dt)
        self._handle_collisions()
        self._cleanup()

    def _handle_spawning(self, dt):
        self.enemy_spawn_timer += dt
        if self.enemy_spawn_timer >= self.current_enemy_spawn_rate:
            self.enemy_spawn_timer = 0

            # Spawn logic
            side = random.randint(0, 3)
            if side == 0:  # Top
                x = random.uniform(0, 1024)
                y = -30
            elif side == 1:  # Right
                x = 1024 + 30
                y = random.uniform(0, 768)
            elif side == 2:  # Bottom
                x = random.uniform(0, 1024)
                y = 768 + 30
            else:  # Left
                x = -30
                y = random.uniform(0, 768)

            pos = rl.Vector2(x, y)

            types = ["square", "triangle", "hexagon"]
            weights = [0.6, 0.3, 0.1]  # Base probabilities

            # Adjust weights based on wave
            if self.wave > 5:
                weights = [0.4, 0.4, 0.2]
            elif self.wave > 10:
                weights = [0.3, 0.4, 0.3]

            chosen_type = random.choices(types, weights=weights)[0]

            # Scale stats with wave
            base_hp = (
                20
                if chosen_type == "square"
                else (15 if chosen_type == "triangle" else 40)
            )
            health = int(base_hp * (1.1**self.wave))

            base_scrap = (
                2
                if chosen_type == "square"
                else (3 if chosen_type == "triangle" else 5)
            )
            scrap_value = int(
                base_scrap * (1.1 ** (self.wave / 2))
            )  # Scale slower than HP

            new_enemy = Enemy(pos, chosen_type, health, scrap_value)

            # Scale speed
            new_enemy.speed *= 1.0 + (self.wave * 0.05)

            self.enemies.append(new_enemy)

    def _handle_tank(self, dt):
        self.tank.fire_cooldown -= dt

        closest_enemy = None
        closest_dist = float("inf")

        for enemy in self.enemies:
            if not enemy.active:
                continue
            dist = vector2_distance(self.tank.position, enemy.position)
            if dist < closest_dist:
                closest_dist = dist
                closest_enemy = enemy

        if closest_enemy:
            # Rotate
            target_angle = angle_between_vectors(
                self.tank.position, closest_enemy.position
            )
            self.tank.rotation = target_angle

            # Fire
            if self.tank.fire_cooldown <= 0:
                self.tank.fire_cooldown = 1.0 / self.tank.fire_rate

                # Apply multi-shot logic
                num_barrels = min(self.tank.multi_shot, 5)
                barrel_angle_offset = 0.2
                start_angle = -((num_barrels - 1) * barrel_angle_offset) / 2

                for i in range(num_barrels):
                    angle = self.tank.rotation + start_angle + (i * barrel_angle_offset)
                    dir_vec = rl.Vector2(math.cos(angle), math.sin(angle))

                    # Calculate spawn position at end of barrel
                    spawn_x = (
                        self.tank.position.x + dir_vec.x * 40
                    )  # 40 is BARREL_LENGTH
                    spawn_y = self.tank.position.y + dir_vec.y * 40

                    is_crit = random.random() < self.tank.crit_chance
                    final_damage = self.tank.damage * (2.0 if is_crit else 1.0)

                    new_proj = Projectile(
                        rl.Vector2(spawn_x, spawn_y),
                        dir_vec,
                        self.tank.projectile_speed,
                        final_damage,
                        is_crit,
                    )
                    self.projectiles.append(new_proj)

    def _update_entities(self, dt):
        for p in self.projectiles:
            p.update(dt)

        for e in self.enemies:
            e.update(dt, self.tank.position)

        for pt in self.particles:
            pt.update(dt)

    def _handle_collisions(self):
        for p in self.projectiles:
            if not p.active:
                continue

            for e in self.enemies:
                if not e.active:
                    continue

                dist = vector2_distance(p.position, e.position)
                if dist < (p.radius + e.radius):
                    p.active = False
                    e.take_damage(p.damage)

                    # Create hit particles
                    for _ in range(3):
                        self.particles.append(Particle(p.position, rl.WHITE))

                    if not e.active:
                        self.scrap += int(e.scrap_value * self.tank.scrap_multiplier)
                        # Check wave progression (simple logic: every 10 kills increases wave)
                        # More complex logic could be used here

                        # Death particles
                        for _ in range(10):
                            self.particles.append(Particle(e.position, e.color))
                    break  # Projectile hit one enemy

        # Check if enemies hit tank (Game Over condition could be here, but for incremental, maybe just lose scrap or push enemies back)
        for e in self.enemies:
            if e.active:
                dist = vector2_distance(e.position, self.tank.position)
                if dist < (e.radius + self.tank.radius):
                    # For a true incremental, maybe they just stop and you have to kill them.
                    # Let's say they steal scrap and disappear
                    self.scrap = max(0, self.scrap - e.scrap_value * 2)
                    e.active = False
                    for _ in range(10):
                        self.particles.append(Particle(e.position, rl.RED))

    def _cleanup(self):
        self.projectiles = [p for p in self.projectiles if p.active]
        self.enemies = [e for e in self.enemies if e.active]
        self.particles = [p for p in self.particles if p.active]

    def draw(self):
        for e in self.enemies:
            e.draw()

        for p in self.projectiles:
            p.draw()

        self.tank.draw()

        for pt in self.particles:
            pt.draw()

    def purchase_upgrade(self, upgrade_id):
        if upgrade_id in self.upgrades:
            upgrade = self.upgrades[upgrade_id]
            if self.scrap >= upgrade["cost"]:
                self.scrap -= upgrade["cost"]
                upgrade["level"] += 1
                upgrade["cost"] = int(upgrade["cost"] * 1.5)  # 1.5 multiplier

                # Apply effect
                if upgrade_id == "fire_rate":
                    self.tank.fire_rate += 0.5
                elif upgrade_id == "damage":
                    self.tank.damage += 5
                elif upgrade_id == "proj_speed":
                    self.tank.projectile_speed += 50
                elif upgrade_id == "multi_shot":
                    self.tank.multi_shot += 1
                elif upgrade_id == "crit_chance":
                    self.tank.crit_chance = min(1.0, self.tank.crit_chance + 0.05)
                elif upgrade_id == "scrap_mult":
                    self.tank.scrap_multiplier += 0.2
