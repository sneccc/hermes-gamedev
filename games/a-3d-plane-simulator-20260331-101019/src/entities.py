import pyray as rl
from constants import *
from utils import *
import math

class PlayerPlane:
    def __init__(self):
        self.position = rl.Vector3(0.0, 10.0, 0.0)
        self.forward = rl.Vector3(0.0, 0.0, 1.0)
        self.up = rl.Vector3(0.0, 1.0, 0.0)
        self.right = rl.Vector3(1.0, 0.0, 0.0)
        self.speed = PLANE_SPEED_MIN
        self.radius = PLANE_COLLISION_RADIUS

    def update(self, dt, pitch_input, yaw_input, roll_input, throttle_input):
        self.speed += throttle_input * PLANE_ACCEL * dt
        self.speed = max(PLANE_SPEED_MIN, min(PLANE_SPEED_MAX, self.speed))

        if pitch_input != 0:
            pitch_rot = quaternion_from_axis_angle(self.right, pitch_input * PITCH_SPEED * dt)
            self.forward = vector3_rotate_by_quaternion(self.forward, pitch_rot)
            self.up = vector3_rotate_by_quaternion(self.up, pitch_rot)
            self.forward = normalize_vector3(self.forward)
            self.up = normalize_vector3(self.up)
            self.right = cross_product(self.up, self.forward)
            self.right = normalize_vector3(self.right)

        if yaw_input != 0:
            yaw_rot = quaternion_from_axis_angle(self.up, yaw_input * YAW_SPEED * dt)
            self.forward = vector3_rotate_by_quaternion(self.forward, yaw_rot)
            self.right = vector3_rotate_by_quaternion(self.right, yaw_rot)
            self.forward = normalize_vector3(self.forward)
            self.right = normalize_vector3(self.right)

        if roll_input != 0:
            roll_rot = quaternion_from_axis_angle(self.forward, roll_input * ROLL_SPEED * dt)
            self.up = vector3_rotate_by_quaternion(self.up, roll_rot)
            self.right = vector3_rotate_by_quaternion(self.right, roll_rot)
            self.up = normalize_vector3(self.up)
            self.right = normalize_vector3(self.right)

        vel_x = self.forward.x * self.speed
        vel_y = self.forward.y * self.speed
        vel_z = self.forward.z * self.speed

        gravity_effect = max(0, GRAVITY_PULL - (self.speed / PLANE_SPEED_MAX) * GRAVITY_PULL)
        vel_y -= gravity_effect

        self.position.x += vel_x * dt
        self.position.y += vel_y * dt
        self.position.z += vel_z * dt

    def draw(self):
        # Draw a simple box at position for now
        rl.draw_cube(self.position, 1.0, 1.0, 4.0, COLOR_PLANE)
        # Wings
        wings_pos = rl.Vector3(self.position.x, self.position.y, self.position.z)
        rl.draw_cube(wings_pos, 5.0, 0.2, 1.0, COLOR_PLANE)
        # Tail
        tail_pos = rl.Vector3(self.position.x, self.position.y + 0.5, self.position.z - 1.5)
        rl.draw_cube(tail_pos, 0.2, 1.0, 1.0, COLOR_PLANE)

class Ring:
    def __init__(self, position):
        self.position = position
        self.radius = RING_RADIUS
        self.active = True

    def draw(self):
        if self.active:
            # We orient rings facing Z axis (0,0,1) with some rotation based on cross products maybe later
            # For now circle 3D is good enough
            axis = rl.Vector3(1, 0, 0)
            angle = 90.0
            rl.draw_circle_3d(self.position, self.radius, axis, angle, COLOR_RING)
            rl.draw_circle_3d(self.position, self.radius * 0.9, axis, angle, COLOR_RING)
