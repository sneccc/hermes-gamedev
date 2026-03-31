import pyray as rl

WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
GAME_TITLE = "Tank Tycoon: Iron Idle"

FPS = 60

# Colors
BG_COLOR = rl.Color(20, 20, 25, 255)
TANK_COLOR = rl.Color(0, 228, 48, 255)
BARREL_COLOR = rl.Color(0, 158, 47, 255)
PROJECTILE_COLOR = rl.Color(253, 249, 0, 255)
UI_BG = rl.Color(30, 30, 40, 200)
TEXT_COLOR = rl.Color(230, 230, 230, 255)
HIGHLIGHT_COLOR = rl.Color(0, 121, 241, 255)
PARTICLE_COLORS = [
    rl.Color(255, 109, 194, 255),
    rl.Color(0, 228, 48, 255),
    rl.Color(0, 121, 241, 255),
    rl.Color(253, 249, 0, 255),
]

ENEMY_COLORS = {
    "square": rl.Color(255, 109, 194, 255),  # Pink
    "triangle": rl.Color(0, 121, 241, 255),  # Blue
    "hexagon": rl.Color(253, 249, 0, 255),  # Yellow
}

# Initial Stats
BASE_FIRE_RATE = 1.0  # Shots per second
BASE_DAMAGE = 10
BASE_PROJECTILE_SPEED = 400
BASE_ENEMY_SPEED = 50
BASE_ENEMY_SPAWN_RATE = 2.0  # Seconds per spawn

# Upgrade Scaling
UPGRADE_COST_BASE = 10
UPGRADE_COST_MULTIPLIER = 1.5

# Game Constants
CENTER_X = WINDOW_WIDTH / 2
CENTER_Y = WINDOW_HEIGHT / 2
TANK_RADIUS = 25
BARREL_LENGTH = 40
BARREL_WIDTH = 10
