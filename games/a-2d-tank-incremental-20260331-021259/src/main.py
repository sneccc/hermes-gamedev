import pyray as rl
from constants import WINDOW_WIDTH, WINDOW_HEIGHT, GAME_TITLE, FPS, BG_COLOR
from systems import GameSystem
from ui import UI
import json
import os


def load_config():
    # Attempt to load config for future proofing/data-driven approach
    config_path = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def main():
    rl.init_window(WINDOW_WIDTH, WINDOW_HEIGHT, GAME_TITLE)
    rl.set_target_fps(FPS)

    # Load optional config
    config = load_config()

    game = GameSystem()
    ui = UI(game)

    # Simple wave progression based on kills
    kills = 0
    next_wave_kills = 10

    while not rl.window_should_close():
        dt = rl.get_frame_time()

        # Update
        game.update(dt)
        ui.update()

        # Wave progression logic
        # Count destroyed enemies this frame
        current_active = len([e for e in game.enemies if e.active])
        if hasattr(game, "last_active_count"):
            # Rough estimate: if enemies decreased and it wasn't due to cleanup
            pass  # In a real system, we'd track kills specifically

        # Drawing
        rl.begin_drawing()
        rl.clear_background(BG_COLOR)

        game.draw()
        ui.draw()

        rl.end_drawing()

    rl.close_window()


if __name__ == "__main__":
    main()
