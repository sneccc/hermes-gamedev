import pyray as rl


class UI:
    def __init__(self, game_system):
        self.game = game_system
        self.menu_width = 300
        self.menu_x = 1024 - self.menu_width
        self.buttons = []

        # Upgrades
        self._init_buttons()

    def _init_buttons(self):
        upgrades = [
            ("Fire Rate", "fire_rate"),
            ("Damage", "damage"),
            ("Proj Speed", "proj_speed"),
            ("Multi-Shot", "multi_shot"),
            ("Crit Chance", "crit_chance"),
            ("Scrap Mult", "scrap_mult"),
        ]

        y_offset = 100
        for name, key in upgrades:
            rect = rl.Rectangle(self.menu_x + 20, y_offset, self.menu_width - 40, 50)
            self.buttons.append(
                {
                    "rect": rect,
                    "label": name,
                    "id": key,
                    "hover": False,
                    "pressed": False,
                }
            )
            y_offset += 70

    def update(self):
        mouse_pos = rl.get_mouse_position()
        click = rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)

        for btn in self.buttons:
            btn["hover"] = rl.check_collision_point_rec(mouse_pos, btn["rect"])

            if btn["hover"] and click:
                btn["pressed"] = True
                self.game.purchase_upgrade(btn["id"])
            else:
                btn["pressed"] = False

    def draw(self):
        # Top Bar
        rl.draw_rectangle(0, 0, 1024, 60, rl.Color(30, 30, 40, 200))
        rl.draw_text(f"Scrap: {self.game.scrap}", 20, 20, 20, rl.WHITE)
        rl.draw_text(f"Wave: {self.game.wave}", 400, 20, 20, rl.WHITE)

        # Side Menu
        rl.draw_rectangle(
            self.menu_x, 60, self.menu_width, 768 - 60, rl.Color(40, 40, 50, 200)
        )
        rl.draw_text("Upgrades Shop", self.menu_x + 20, 70, 20, rl.RAYWHITE)

        for btn in self.buttons:
            u_id = btn["id"]
            upgrade = self.game.upgrades[u_id]
            cost = upgrade["cost"]
            level = upgrade["level"]
            can_afford = self.game.scrap >= cost

            # Button Colors
            bg_color = rl.DARKGRAY
            if can_afford:
                bg_color = rl.Color(0, 121, 241, 255)  # Blue
                if btn["hover"]:
                    bg_color = rl.Color(0, 150, 255, 255)  # Lighter blue
            else:
                bg_color = rl.Color(80, 80, 80, 255)

            text_color = rl.WHITE if can_afford else rl.LIGHTGRAY

            rl.draw_rectangle_rec(btn["rect"], bg_color)
            rl.draw_rectangle_lines_ex(
                btn["rect"], 2, rl.WHITE if btn["hover"] else rl.GRAY
            )

            # Label
            rl.draw_text(
                f"{btn['label']} (Lv {level})",
                int(btn["rect"].x) + 10,
                int(btn["rect"].y) + 10,
                20,
                text_color,
            )

            # Cost
            cost_text = f"Cost: {cost}"
            text_width = rl.measure_text(cost_text, 15)
            rl.draw_text(
                cost_text,
                int(btn["rect"].x + btn["rect"].width - text_width - 10),
                int(btn["rect"].y) + 30,
                15,
                rl.GREEN if can_afford else rl.RED,
            )
