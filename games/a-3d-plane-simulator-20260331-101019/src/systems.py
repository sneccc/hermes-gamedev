import pyray as rl
from constants import *
from entities import Ring
import random


class GameState:
    def __init__(self):
        self.score = 0
        self.time_remaining = TIME_START
        self.state = "playing"  # playing, game_over, win

    def add_score(self):
        self.score += 1
        self.time_remaining += TIME_BONUS_PER_RING
        if self.score >= SCORE_TO_WIN:
            self.state = "win"

    def update(self, dt):
        if self.state == "playing":
            self.time_remaining -= dt
            if self.time_remaining <= 0:
                self.state = "game_over"


class RingManager:
    def __init__(self):
        self.rings = []
        self.spawn_initial_ring()

    def spawn_initial_ring(self):
        self.rings.append(Ring(rl.Vector3(0.0, 10.0, RING_SPAWN_DIST)))

    def spawn_next_ring(self, player_pos, player_forward):
        # Spawn a ring somewhat ahead of the player
        # Randomize position slightly
        base_x = player_pos.x + player_forward.x * RING_SPAWN_DIST
        base_y = player_pos.y + player_forward.y * RING_SPAWN_DIST
        base_z = player_pos.z + player_forward.z * RING_SPAWN_DIST

        # Keep y somewhat grounded
        base_y = max(RING_SPAWN_VAR_Y_MIN, min(RING_SPAWN_VAR_Y_MAX, base_y))

        offset_x = random.uniform(-RING_SPAWN_VAR_XY, RING_SPAWN_VAR_XY)
        offset_y = random.uniform(-RING_SPAWN_VAR_XY / 2, RING_SPAWN_VAR_XY / 2)

        new_pos = rl.Vector3(base_x + offset_x, base_y + offset_y, base_z)
        self.rings.append(Ring(new_pos))

    def update(self, dt, player):
        # Remove old rings behind the player
        active_rings = []
        for r in self.rings:
            # Check dot product to see if it's behind player
            dir_to_ring = rl.Vector3(
                r.position.x - player.position.x,
                r.position.y - player.position.y,
                r.position.z - player.position.z,
            )
            # Simple check: distance along forward vector
            dot = (
                dir_to_ring.x * player.forward.x
                + dir_to_ring.y * player.forward.y
                + dir_to_ring.z * player.forward.z
            )

            # If it's way behind or we passed it
            if dot < -20.0:
                pass  # remove it
            else:
                active_rings.append(r)

        self.rings = active_rings

        # Make sure there are always 2 rings
        while len(self.rings) < 2:
            self.spawn_next_ring(player.position, player.forward)

    def draw(self):
        for r in self.rings:
            r.draw()


class CollisionSystem:
    def __init__(self):
        pass

    def check_collisions(self, player, ring_manager, game_state):
        if game_state.state != "playing":
            return

        # Ground collision
        if player.position.y - player.radius <= GROUND_Y:
            game_state.state = "game_over"
            return

        # Ring collision
        for r in ring_manager.rings:
            if not r.active:
                continue

            # Sphere collision for simplicity
            dx = player.position.x - r.position.x
            dy = player.position.y - r.position.y
            dz = player.position.z - r.position.z
            dist_sq = dx * dx + dy * dy + dz * dz

            # Plane is a sphere, ring is a point?
            # Actually, ring is a torus, but let's just use distance from center
            # A pass-through is when plane is close to center
            if dist_sq < r.radius * r.radius:
                r.active = False
                game_state.add_score()
