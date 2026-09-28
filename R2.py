import zmq
from heat_map import venusMap
import time
import math
from math import hypot
import random

class Droid:
    def __init__(self, start, direction, venusMap):
        self.Pos       = [float(start[0]), float(start[1])]
        self.direction = direction
        self.state     = 'scanning'
        self.map       = venusMap
        
        self.speed     = 0.0 
        self.max_speed = 0.4
        self.robot_radius = 7.25

        self.scan_angle_swept = 0   
        self.locked_target  = None  
        self.lock_grace = 0    

        self.blindfold = 0 
        self.pause_timer = 0
        
        self.measure_angle = 0
        self.measure_dists = []
        self.lock_turn_remaining = 0
        
        self.path = []
        self.path_idx = 0
        
        self.dodge_target = [0.0, 0.0]
        self.state_after_reverse = 'scanning'
        
        self.blind_turn_remaining = 0
        self.blind_turn_dir = 1
        self.blind_move_timer = 0
        
        self.checkpoints = []

    @property
    def data(self):
        return {
            'position'  : self.Pos,
            'direction' : self.direction,
            'obstacles' : list(self.map.obstacles),
            'hits'      : self.map.bingo,
            'state'     : self.state,
            'speed'     : self.speed
        }

    def rotate_dir(self, deg):
        t  = math.radians(deg)
        nx = self.direction[0]*math.cos(t) - self.direction[1]*math.sin(t)
        ny = self.direction[0]*math.sin(t) + self.direction[1]*math.cos(t)
        m  = hypot(nx, ny)
        self.direction = [nx/m, ny/m]

    def turn_towards_point(self, tx, ty):
        dx, dy = self.direction
        vx, vy = tx - self.Pos[0], ty - self.Pos[1]
        dist = hypot(vx, vy)
        if dist == 0: return True
        vx, vy = vx/dist, vy/dist
        
        dot = dx*vx + dy*vy
        cross = dx*vy - dy*vx
        angle = math.degrees(math.atan2(cross, dot))
        
        if abs(angle) <= 1.0:
            self.direction = [vx, vy]
            return True
        else:
            self.rotate_dir(1.0 if angle > 0 else -1.0)
            return False

    def should_scan(self):
        for cp in self.checkpoints:
            if hypot(self.Pos[0] - cp[0], self.Pos[1] - cp[1]) < 80:
                return False
        return True
        
    def enter_reverse(self, next_state):
        self.speed = -(self.max_speed / 2.0)
        self.state = 'reversing'
        self.dodge_target = [self.Pos[0] - self.direction[0] * 15, self.Pos[1] - self.direction[1] * 15]
        self.blindfold = 15 
        self.state_after_reverse = next_state

    def update(self, long_dist, hit_fatal):
        self.map.claim(self.Pos)

        if self.pause_timer > 0:
            self.pause_timer -= 1
            self.speed = 0.0 
            return

        if self.blindfold > 0:
            self.blindfold -= 1
            hit_fatal = False 

        if self.state in ['reversing', 'avoid_friend_turn', 'blind_turn']:
            hit_fatal = False

        # Sensor specs: min 4cm, max 80cm
        seeing_object = (long_dist >= 4 and long_dist <= 80)
        hit_pos = [self.Pos[0] + self.direction[0]*(long_dist + self.robot_radius), 
                   self.Pos[1] + self.direction[1]*(long_dist + self.robot_radius)] if seeing_object else None
        
        if seeing_object and any(hypot(hit_pos[0]-c[0], hit_pos[1]-c[1]) < 10 for c in self.map.bingo):
            seeing_object = False

        if seeing_object:
            for clanker in self.map.clankers:
                if clanker == self.Pos: continue
                if hypot(hit_pos[0]-clanker[0], hit_pos[1]-clanker[1]) < 15:
                    seeing_object = False
                    break

        if hit_fatal:
            bump_pos = [self.Pos[0] + self.direction[0]* (self.robot_radius + 2), 
                        self.Pos[1] + self.direction[1]* (self.robot_radius + 2)]
            hit_friend = False
            for clanker in self.map.clankers:
                if clanker == self.Pos: continue
                if hypot(self.Pos[0]-clanker[0], self.Pos[1]-clanker[1]) < (self.robot_radius * 2 + 2): 
                    hit_friend = True
                    break
                    
            if hit_friend:
                print("[R2] Collision Alert! Bumped into WallE. Reversing.")
                self.enter_reverse('avoid_friend_turn')
                self.pause_timer = random.randint(15, 30)
                return
            
            print(f"[R2] Collision Alert! Hit an obstacle near {bump_pos}. Reversing.")
            next_state = 'scanning' if self.should_scan() else 'planning_sweep'
            if self.state == 'locked':
                self.map.found_cubes(bump_pos)
                self.locked_target = None
                
            self.map.mark_obstacle(bump_pos)
            self.enter_reverse(next_state)
            self.pause_timer = 15
            return

        if self.state == 'scanning':
            self.speed = 0.0
            if seeing_object:
                print("[R2] Object detected. Initiating measurement sweep.")
                self.state = 'measuring'
                self.measure_angle = 0
                self.measure_dists = [long_dist]
            else:
                self.rotate_dir(1) 
                self.scan_angle_swept += 1
                if self.scan_angle_swept >= 360:
                    print("[R2] 360-degree scan complete. Assessing map for next move.")
                    self.scan_angle_swept = 0
                    self.checkpoints.append(list(self.Pos)) 
                    self.state = 'planning_sweep'

        elif self.state == 'measuring':
            self.speed = 0.0
            self.rotate_dir(1)
            self.measure_angle += 1
            self.scan_angle_swept += 1
            
            if seeing_object:
                self.measure_dists.append(long_dist)
                obs_x = self.Pos[0] + self.direction[0] * (long_dist + self.robot_radius)
                obs_y = self.Pos[1] + self.direction[1] * (long_dist + self.robot_radius)
                self.map.mark_obstacle([obs_x, obs_y])
                
                if self.measure_angle > 45: 
                    print("[R2] Classification: MOUNTAIN (Too massive, aborting early)")
                    self.state = 'skipping'
            else:
                avg_dist = sum(self.measure_dists) / len(self.measure_dists)
                arc_width = math.radians(self.measure_angle) * (avg_dist + self.robot_radius)
                
                print(f"\n--- [R2] Object Measured organically ---")
                print(f"Crude Arc Width: {arc_width:.2f} cm")
                
                if 5 < arc_width < 10.0: 
                    print("[R2] Classification: big CUBE (Turning back to lock!)\n")
                    self.state = 'locking_turn'
                    self.lock_turn_remaining = self.measure_angle / 2.0
                elif 1.5 < arc_width < 5: 
                    print("[R2] Classification: big CUBE (Turning back to lock!)\n")
                    self.state = 'locking_turn'
                    self.lock_turn_remaining = self.measure_angle / 2.0
                else:
                    print("[R2] Classification: MOUNTAIN (Repositioning to break loop)\n")
                    self.state = 'blind_turn'
                    self.blind_turn_remaining = random.choice([90, 135, 180])
                    self.blind_turn_dir = random.choice([1, -1])

        elif self.state == 'skipping':
            self.speed = 0.0
            self.rotate_dir(1)
            self.scan_angle_swept += 1
            if seeing_object:
                obs_x = self.Pos[0] + self.direction[0] * (long_dist + self.robot_radius)
                obs_y = self.Pos[1] + self.direction[1] * (long_dist + self.robot_radius)
                self.map.mark_obstacle([obs_x, obs_y])
            else:
                print("[R2] Massive object cleared. Repositioning to avoid getting stuck in a loop.")
                self.state = 'blind_turn'
                self.blind_turn_remaining = random.choice([90, 135, 180])
                self.blind_turn_dir = random.choice([1, -1])

        elif self.state == 'locking_turn':
            self.speed = 0.0
            self.rotate_dir(-1)
            self.lock_turn_remaining -= 1
            if self.lock_turn_remaining <= 0:
                print("[R2] Target locked! Full speed ahead.")
                self.state = 'locked'
                self.lock_grace = 0

        elif self.state == 'locked':
            self.speed = self.max_speed
            if not seeing_object:
                self.lock_grace += 1
                if self.lock_grace > 30: 
                    print("[R2] Target lost or collected. Returning to search protocol.")
                    self.state = 'scanning' if self.should_scan() else 'planning_sweep'
            else:
                self.lock_grace = 0
            
        elif self.state == 'planning_sweep':
            self.speed = 0.0
            target = self.map.find_nearest_unknown(self.Pos)
            if target:
                path = self.map.astar(self.Pos, target)
                if path:
                    print(f"[R2] Path found to unexplored sector {target}. Commencing sweep.")
                    self.path = path
                    self.path_idx = 0
                    self.state = 'sweeping'
                else:
                    print(f"[R2] Sector {target} is unreachable. Marking as claimed to avoid loop.")
                    self.map.known[target] = 1 
                    self.state = 'blind_turn'
                    target_angle = random.choice([90, -90, 180])
                    self.blind_turn_remaining = abs(target_angle)
                    self.blind_turn_dir = 1 if target_angle > 0 else -1
            else:
                print("[R2] No immediate unknown sectors. Executing blind turn.")
                self.state = 'blind_turn'
                target_angle = random.choice([90, -90, 180])
                self.blind_turn_remaining = abs(target_angle)
                self.blind_turn_dir = 1 if target_angle > 0 else -1

        elif self.state == 'blind_turn':
            self.speed = 0.0
            self.rotate_dir(self.blind_turn_dir)
            self.blind_turn_remaining -= 1
            if self.blind_turn_remaining <= 0:
                print("[R2] Blind turn complete. Moving blindly forward.")
                self.state = 'blind_move'
                self.blind_move_timer = 40

        elif self.state == 'blind_move':
            self.speed = self.max_speed
            self.blind_move_timer -= 1
            if self.blind_move_timer <= 0:
                print("[R2] Blind move finished. Re-evaluating.")
                self.speed = 0.0
                self.state = 'scanning' if self.should_scan() else 'planning_sweep'

        elif self.state == 'sweeping':
            if seeing_object:
                print("[R2] Sweep interrupted by object. Initiating measurement.")
                self.state = 'measuring'
                self.measure_angle = 0
                self.measure_dists = [long_dist]
                self.speed = 0.0
                return
                
            if self.should_scan():
                print("[R2] Reached new vantage point. Stopping to scan.")
                self.state = 'scanning'
                self.scan_angle_swept = 0
                self.speed = 0.0
                return
                
            if self.path_idx >= len(self.path):
                print("[R2] Reached end of planned path. Replanning.")
                self.state = 'planning_sweep'
                self.speed = 0.0
                return
                
            wp = self.path[self.path_idx]
            dist_wp = hypot(wp[0] - self.Pos[0], wp[1] - self.Pos[1])
            
            if dist_wp < self.max_speed * 2:
                self.path_idx += 1
            else:
                if self.turn_towards_point(wp[0], wp[1]):
                    self.speed = self.max_speed
                else:
                    self.speed = 0.0

        elif self.state == 'reversing':
            dx = self.dodge_target[0] - self.Pos[0]
            dy = self.dodge_target[1] - self.Pos[1]
            dist_r = hypot(dx, dy)
            if dist_r <= abs(self.speed):
                print(f"[R2] Reverse complete. Transitioning to {self.state_after_reverse}.")
                self.speed = 0.0
                self.state = self.state_after_reverse
                self.scan_angle_swept = 0
                
                if self.state == 'avoid_friend_turn':
                    target_angle = random.choice([90, -90, 135, -135])
                    self.blind_turn_remaining = abs(target_angle)
                    self.blind_turn_dir = 1 if target_angle > 0 else -1
            else:
                self.speed = -(self.max_speed / 2.0)

        elif self.state == 'avoid_friend_turn':
            self.speed = 0.0
            self.rotate_dir(self.blind_turn_dir)
            self.blind_turn_remaining -= 1
            if self.blind_turn_remaining <= 0:
                print("[R2] Evasive spin complete. Resuming operations.")
                self.state = 'scanning' if self.should_scan() else 'planning_sweep'

        self.Pos[0] += self.speed * self.direction[0]
        self.Pos[1] += self.speed * self.direction[1]


def main():
    ctx = zmq.Context()

    R2_loc = ctx.socket(zmq.PUB)
    R2_loc.bind("tcp://127.0.0.1:5552")        

    sensor = ctx.socket(zmq.SUB)
    sensor.connect("tcp://127.0.0.1:5554")
    sensor.set(zmq.SUBSCRIBE, b"")

    WallE_loc = ctx.socket(zmq.SUB)
    WallE_loc.setsockopt(zmq.CONFLATE, 1)
    WallE_loc.connect("tcp://127.0.0.1:5551")  
    WallE_loc.set(zmq.SUBSCRIBE, b"")

    venus_map = venusMap()
    R2        = Droid([0, 40], [0, 1], venus_map)

    print("[R2] Systems initialized. R2 is ready.")
    while True:
        try:
            msg = sensor.recv_json(zmq.NOBLOCK)
            if 'long_dist' in msg: break
        except zmq.Again:
            time.sleep(0.05)
    print("[R2] Deployment successful. T0 for R2!")

    while True:
        venus_map.clankers = [R2.Pos]

        try:
            walle = WallE_loc.recv_json(zmq.NOBLOCK)
            R2.map.claim(walle['position'])
            venus_map.clankers.append(walle['position'])
            for obs in walle['obstacles']: R2.map.obstacles.add(tuple(obs))
        except zmq.Again:
            pass

        long_dist = 0
        hit_fatal = False
        valid = False

        while True:
            try:
                msg = sensor.recv_json(zmq.NOBLOCK)
                if 'long_dist' in msg: 
                    valid = True
                    long_dist = msg['long_dist']
                    hit_fatal = hit_fatal or msg['hit_fatal']
            except zmq.Again:
                break

        if valid:
            R2.update(long_dist, hit_fatal)

        R2_loc.send_json(R2.data)
        time.sleep(0.016)

if __name__ == '__main__':
    main()