import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pygame
import zmq
import math
import random
from back_bone import gen_venus_map, overlap, overlap_ellipse
from heat_map import venusMap

# REAL WORLD SPECS (in cm)
ROBOT_RADIUS = 7.25
RAYCAST_MIN = int(ROBOT_RADIUS + 4)  # 4 cm from shell
RAYCAST_MAX = int(ROBOT_RADIUS + 80) # 80 cm from shell

# VISUAL SCALING FACTOR (1 cm = X pixels on screen)
SCALE = 4  

def raycast(pos, dir_vec, cubes, mountains, other_robot_pos):
    for d_int in range(RAYCAST_MIN, RAYCAST_MAX + 1, 2):
        d = float(d_int)
        cx = pos[0] + dir_vec[0] * d
        cy = pos[1] + dir_vec[1] * d
        
        # Laser is treated as 1cm thick in physics
        if overlap(cx, cy, 1.0, cubes):     return d - ROBOT_RADIUS, 'hit'
        if overlap(cx, cy, 1.0, mountains): return d - ROBOT_RADIUS, 'hit'
        if math.hypot(cx - other_robot_pos[0], cy - other_robot_pos[1]) < (ROBOT_RADIUS + 1.0):
            return d - ROBOT_RADIUS, 'hit'
    return 0, 'none'

def main():
    ctx = zmq.Context()

    sub_WallE = ctx.socket(zmq.SUB)
    sub_WallE.setsockopt(zmq.CONFLATE, 1)
    sub_WallE.connect("tcp://127.0.0.1:5551")
    sub_WallE.set(zmq.SUBSCRIBE, b"")

    sub_R2 = ctx.socket(zmq.SUB)
    sub_R2.setsockopt(zmq.CONFLATE, 1)
    sub_R2.connect("tcp://127.0.0.1:5552")
    sub_R2.set(zmq.SUBSCRIBE, b"")

    pub_sensor1 = ctx.socket(zmq.PUB)
    pub_sensor1.bind("tcp://127.0.0.1:5553")

    pub_sensor2 = ctx.socket(zmq.PUB)
    pub_sensor2.bind("tcp://127.0.0.1:5554")

    pygame.init()
    
    # 1200x800 Display Size translates to a 300x200 cm (3x2 meter) logical arena!
    screen_width, screen_height = 1000, 600
    logic_width = screen_width // SCALE
    logic_height = screen_height // SCALE
    
    screen = pygame.display.set_mode((screen_width, screen_height))
    font   = pygame.font.SysFont("Arial", 36, bold=True)
    clock  = pygame.time.Clock()

    offset_x = random.randint(20, 50)
    offset_y = random.randint(20, 50)

    cubes, mountains, craters, walls, shapes = gen_venus_map(logic_width, logic_height, offset_x, offset_y)
    gui_map = venusMap()

    W_pos, W_dir, W_state = [0, 0],  [1, 0], 'scanning'
    R_pos, R_dir, R_state = [0, 40], [0, 1], 'scanning'
    
    W_hits = []
    R_hits = []

    W_color = (181, 127, 12)
    R_color = (42, 90, 151)

    win_timer = 0
    running   = True

    rect_hazards = mountains + walls + cubes

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        try:
            w_data  = sub_WallE.recv_json(zmq.NOBLOCK)
            W_pos   = w_data['position']
            W_dir   = w_data['direction']
            W_state = w_data['state']
            W_hits  = w_data['hits']
            gui_map.claim(W_pos)
            for obs in w_data['obstacles']: gui_map.obstacles.add(tuple(obs))
        except zmq.Again:
            pass

        try:
            r_data  = sub_R2.recv_json(zmq.NOBLOCK)
            R_pos   = r_data['position']
            R_dir   = r_data['direction']
            R_state = r_data['state']
            R_hits  = r_data['hits']
            gui_map.claim(R_pos)
            for obs in r_data['obstacles']: gui_map.obstacles.add(tuple(obs))
        except zmq.Again:
            pass

        W_phys = [W_pos[0] + offset_x, W_pos[1] + offset_y]
        R_phys = [R_pos[0] + offset_x, R_pos[1] + offset_y]

        W_long_dist, W_long_type = raycast(W_phys, W_dir, cubes, mountains, R_phys)
        R_long_dist, R_long_type = raycast(R_phys, R_dir, cubes, mountains, W_phys)

        W_bump = [W_phys[0] + W_dir[0]*(ROBOT_RADIUS + 1), W_phys[1] + W_dir[1]*(ROBOT_RADIUS + 1)]
        R_bump = [R_phys[0] + R_dir[0]*(ROBOT_RADIUS + 1), R_phys[1] + R_dir[1]*(ROBOT_RADIUS + 1)]

        W_fatal = (
            overlap(W_bump[0], W_bump[1], 1, rect_hazards) or 
            overlap_ellipse(W_bump[0], W_bump[1], 1, craters) or
            math.hypot(W_phys[0]-R_phys[0], W_phys[1]-R_phys[1]) < (ROBOT_RADIUS*2 + 1)
        )
        
        R_fatal = (
            overlap(R_bump[0], R_bump[1], 1, rect_hazards) or 
            overlap_ellipse(R_bump[0], R_bump[1], 1, craters) or
            math.hypot(R_phys[0]-W_phys[0], R_phys[1]-W_phys[1]) < (ROBOT_RADIUS*2 + 1)
        )

        W_sensors = {
            "long_dist": W_long_dist,
            "long_type": W_long_type,
            "hit_fatal": W_fatal
        }
        R_sensors = {
            "long_dist": R_long_dist,
            "long_type": R_long_type,
            "hit_fatal": R_fatal
        }

        pub_sensor1.send_json(W_sensors)
        pub_sensor2.send_json(R_sensors)

        all_scanned = True
        screen.fill((20, 20, 20))

        # DRAW HEAT MAP
        for pos, count in gui_map.known.items():
            c  = min(50 + count * 20, 255)
            px = int((pos[0] + offset_x) * SCALE)
            py = int((pos[1] + offset_y) * SCALE)
            pygame.draw.circle(screen, (c, c, 100), (px, py), max(1, int(1.5 * SCALE)))

        # DRAW OBSTACLES
        for obs_pos in gui_map.obstacles:
            px = int((obs_pos[0] + offset_x) * SCALE)
            py = int((obs_pos[1] + offset_y) * SCALE)
            pygame.draw.circle(screen, (255, 0, 0), (px, py), max(1, int(2 * SCALE)))

        # DRAW SHAPES (scaled mathematically)
        for shape in shapes:
            rect = shape['rect']
            
            draw_rect = pygame.Rect(rect.left * SCALE, rect.top * SCALE, 
                                    rect.width * SCALE, rect.height * SCALE)

            if shape['type'] == 'cube':
                scanned_W = any(math.hypot(rect.centerx-(fc[0]+offset_x), rect.centery-(fc[1]+offset_y)) < 15 for fc in W_hits)
                scanned_R = any(math.hypot(rect.centerx-(fc[0]+offset_x), rect.centery-(fc[1]+offset_y)) < 15 for fc in R_hits)
                
                if scanned_W and scanned_R:
                    cube_color = (255, 105, 180) # Pink
                elif scanned_W:
                    cube_color = (255, 100, 0)   # Orange
                elif scanned_R:
                    cube_color = (0, 100, 255)   # Blue
                else:
                    cube_color = (255, 200, 0)   # Yellow
                    all_scanned = False
                
                pygame.draw.rect(screen, cube_color, draw_rect)
            elif shape['type'] == 'square': pygame.draw.rect(screen, (200, 100, 0), draw_rect)
            elif shape['type'] == 'ellipse': pygame.draw.ellipse(screen, (150, 0, 200), draw_rect)

        is_done = all_scanned
        if is_done and win_timer == 0:
            win_timer = pygame.time.get_ticks()
        if is_done:
            W_color = (random.randint(50,255), random.randint(50,255), random.randint(50,255))
            R_color = (random.randint(50,255), random.randint(50,255), random.randint(50,255))
            if pygame.time.get_ticks() - win_timer > 4000:
                running = False

        # DRAW WALLE
        px = int(W_phys[0] * SCALE)
        py = int(W_phys[1] * SCALE)
        pygame.draw.circle(screen, W_color, (px, py), int(ROBOT_RADIUS * SCALE))
        laser_len = W_long_dist + ROBOT_RADIUS if W_long_dist > 0 else 80 + ROBOT_RADIUS
        lx = int((W_phys[0] + W_dir[0]*laser_len) * SCALE)
        ly = int((W_phys[1] + W_dir[1]*laser_len) * SCALE)
        pygame.draw.line(screen, (0,255,0), (px, py), (lx, ly), 2)
        pygame.draw.circle(screen, (0,255,0), (lx, ly), 4)
        # if W_state in ['reversing', 'blind_move']:
        #     tx = int((W_pos[0] - W_dir[0]*15 + offset_x) * SCALE)
        #     ty = int((W_pos[1] - W_dir[1]*15 + offset_y) * SCALE)
        #     pygame.draw.circle(screen, (100, 100, 100), (tx, ty), int(4 * SCALE), 1) 

        # DRAW R2
        px = int(R_phys[0] * SCALE)
        py = int(R_phys[1] * SCALE)
        pygame.draw.circle(screen, R_color, (px, py), int(ROBOT_RADIUS * SCALE))
        laser_len = R_long_dist + ROBOT_RADIUS if R_long_dist > 0 else 80 + ROBOT_RADIUS
        lx = int((R_phys[0] + R_dir[0]*laser_len) * SCALE)
        ly = int((R_phys[1] + R_dir[1]*laser_len) * SCALE)
        pygame.draw.line(screen, (0,255,0), (px, py), (lx, ly), 2)
        pygame.draw.circle(screen, (0,255,0), (lx, ly), 4)
        # if R_state in ['reversing', 'blind_move']:
        #     tx = int((R_pos[0] - R_dir[0]*15 + offset_x) * SCALE)
        #     ty = int((R_pos[1] - R_dir[1]*15 + offset_y) * SCALE)
        #     pygame.draw.circle(screen, (100, 100, 100), (tx, ty), int(4 * SCALE), 1) 

        if is_done:
            text = font.render("Small step for a clanker, huge leap for our project!", True, (0, 255, 0))
            screen.blit(text, (screen_width//2 - text.get_width()//2, screen_height//2 - text.get_height()//2))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()