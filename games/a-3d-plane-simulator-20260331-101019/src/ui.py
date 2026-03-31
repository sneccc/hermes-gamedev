import pyray as rl
from constants import *


class HUDSystem:
    def __init__(self):
        pass

    def draw(self, game_state, player):
        rl.draw_text(
            f"SCORE: {game_state.score}/{SCORE_TO_WIN}", 20, 20, 20, COLOR_TEXT
        )
        rl.draw_text(f"TIME: {game_state.time_remaining:.1f}", 20, 50, 20, COLOR_TEXT)
        rl.draw_text(f"SPEED: {player.speed:.1f}", 20, 80, 20, COLOR_TEXT)
        rl.draw_text(f"ALTITUDE: {player.position.y:.1f}", 20, 110, 20, COLOR_TEXT)

        if player.position.y < 10.0:
            rl.draw_text(
                "PULL UP!",
                WINDOW_WIDTH // 2 - 100,
                WINDOW_HEIGHT // 2 + 100,
                30,
                COLOR_WARNING,
            )

        if game_state.state == "game_over":
            rl.draw_text(
                "GAME OVER",
                WINDOW_WIDTH // 2 - 150,
                WINDOW_HEIGHT // 2 - 50,
                40,
                COLOR_WARNING,
            )
        elif game_state.state == "win":
            rl.draw_text(
                "YOU WIN!",
                WINDOW_WIDTH // 2 - 120,
                WINDOW_HEIGHT // 2 - 50,
                40,
                COLOR_RING,
            )
