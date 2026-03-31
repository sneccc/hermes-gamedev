import pyray as rl
import json
import os

def load_config():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

CONFIG = load_config()

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

COLORS = {
    "bg": rl.Color(20, 20, 25, 255),
    "path": rl.Color(40, 40, 50, 255),
    "neon": rl.Color(0, 255, 255, 150),
    "core": rl.Color(0, 255, 100, 255),
    "swarmer": rl.RED,
    "tank": rl.ORANGE,
    "pulse": rl.SKYBLUE,
    "beam": rl.PURPLE,
    "text": rl.RAYWHITE,
    "ui_bg": rl.Color(0, 0, 0, 180)
}

TOWER_DATA = CONFIG.get("tower_stats", {})
ENEMY_DATA = CONFIG.get("enemy_stats", {})

PATH_POINTS = [
    rl.Vector2(0, 360),
    rl.Vector2(300, 360),
    rl.Vector2(300, 150),
    rl.Vector2(900, 150),
    rl.Vector2(900, 570),
    rl.Vector2(1100, 570),
    rl.Vector2(1100, 360),
    rl.Vector2(1200, 360)
]

SLOTS = [
    rl.Vector2(200, 300), rl.Vector2(400, 210), rl.Vector2(600, 210),
    rl.Vector2(800, 210), rl.Vector2(1000, 510), rl.Vector2(800, 630),
    rl.Vector2(600, 630), rl.Vector2(400, 630), rl.Vector2(1000, 300)
]
