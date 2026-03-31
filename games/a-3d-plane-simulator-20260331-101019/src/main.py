import pyray as rl
from constants import *
from entities import PlayerPlane
from systems import RingManager, GameState, CollisionSystem
from ui import HUDSystem

class GameLoop:
    def __init__(self):
        rl.init_window(WINDOW_WIDTH, WINDOW_HEIGHT, GAME_TITLE)
        rl.set_target_fps(FPS)
        
        self.player = PlayerPlane()
        self.ring_manager = RingManager()
        self.game_state = GameState()
        self.collision_system = CollisionSystem()
        self.hud = HUDSystem()
        
        self.camera = rl.Camera3D()
        self.camera.position = rl.Vector3(0.0, 10.0, -10.0)
        self.camera.target = rl.Vector3(0.0, 10.0, 0.0)
        self.camera.up = rl.Vector3(0.0, 1.0, 0.0)
        self.camera.fovy = 45.0
        self.camera.projection = rl.CAMERA_PERSPECTIVE
        
    def handle_input(self):
        pitch = 0.0
        yaw = 0.0
        roll = 0.0
        throttle = 0.0
        
        if rl.is_key_down(rl.KEY_W): pitch -= 1.0
        if rl.is_key_down(rl.KEY_S): pitch += 1.0
        if rl.is_key_down(rl.KEY_A): roll -= 1.0
        if rl.is_key_down(rl.KEY_D): roll += 1.0
        if rl.is_key_down(rl.KEY_Q): yaw -= 1.0
        if rl.is_key_down(rl.KEY_E): yaw += 1.0
        
        if rl.is_key_down(rl.KEY_SPACE) or rl.is_key_down(rl.KEY_LEFT_SHIFT): throttle += 1.0
        if rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_LEFT_ALT): throttle -= 1.0
        
        return pitch, yaw, roll, throttle

    def update(self):
        dt = rl.get_frame_time()
        
        if self.game_state.state == "playing":
            pitch, yaw, roll, throttle = self.handle_input()
            self.player.update(dt, pitch, yaw, roll, throttle)
            
            self.ring_manager.update(dt, self.player)
            
            # Simple collision
            for r in self.ring_manager.rings:
                if not r.active: continue
                vx = self.player.position.x - r.position.x
                vy = self.player.position.y - r.position.y
                vz = self.player.position.z - r.position.z
                dist_sq = vx*vx + vy*vy + vz*vz
                if dist_sq < RING_COLLISION_RADIUS * RING_COLLISION_RADIUS:
                    r.active = False
                    self.game_state.add_score()
                    
            if self.player.position.y < GROUND_Y:
                self.game_state.state = "game_over"
                
            self.game_state.time_remaining -= dt
            if self.game_state.time_remaining <= 0:
                self.game_state.state = "game_over"

        # Update camera to follow player behind and slightly above
        cam_offset_x = -self.player.forward.x * 20.0
        cam_offset_y = -self.player.forward.y * 20.0 + 5.0
        cam_offset_z = -self.player.forward.z * 20.0
        
        self.camera.position.x = self.player.position.x + cam_offset_x
        self.camera.position.y = self.player.position.y + cam_offset_y
        self.camera.position.z = self.player.position.z + cam_offset_z
        
        self.camera.target.x = self.player.position.x + self.player.forward.x * 10.0
        self.camera.target.y = self.player.position.y + self.player.forward.y * 10.0
        self.camera.target.z = self.player.position.z + self.player.forward.z * 10.0
        self.camera.up.x = self.player.up.x
        self.camera.up.y = self.player.up.y
        self.camera.up.z = self.player.up.z

    def draw(self):
        rl.begin_drawing()
        rl.clear_background(COLOR_BG)
        
        rl.begin_mode_3d(self.camera)
        
        # Draw ground grid
        rl.draw_grid(100, 10.0)
        
        # Draw entities
        self.player.draw()
        self.ring_manager.draw()
        
        rl.end_mode_3d()
        
        # Draw HUD
        self.hud.draw(self.game_state, self.player)
        
        rl.end_drawing()

    def run(self):
        while not rl.window_should_close():
            self.update()
            self.draw()
        rl.close_window()

def main():
    game = GameLoop()
    game.run()

if __name__ == "__main__":
    main()
