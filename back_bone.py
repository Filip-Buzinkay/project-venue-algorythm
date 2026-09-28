import random 
import pygame
 
def overlap(x, y, radius, objects):
    for obj in objects:
        closest_x = max(obj.left, min(x, obj.right))
        closest_y = max(obj.top, min(y, obj.bottom))
        distance_x = x - closest_x
        distance_y = y - closest_y
        if (distance_x**2 + distance_y**2) < (radius**2):
            return True
    return False

def overlap_ellipse(x, y, radius, ellipses):
    for rect in ellipses:
        cx = rect.centerx
        cy = rect.centery
        a = (rect.width / 2.0) + radius
        b = (rect.height / 2.0) + radius
        
        if a == 0 or b == 0: continue
        
        if ((x - cx)**2 / a**2) + ((y - cy)**2 / b**2) <= 1.0:
            return True
    return False
 
def gen_venus_map(width, height, ox=0, oy=0):
    cubes, mountains, craters, shapes = [], [], [], []
 
    # Safe zone protects actual robot spawn area (in cm)
    safe_zone = pygame.Rect(ox - 30, oy - 30, 80, 100)
 
    def get_valid_rect(w, h):
        for _ in range(500):
            r = pygame.Rect(random.randint(20, width-w-20), random.randint(20, height-h-20), w, h)
            if r.colliderect(safe_zone): continue
            too_close = any(r.colliderect(obj.inflate(20, 20)) for obj in cubes + mountains + craters)
            if not too_close: return r
        for _ in range(1000):
            r = pygame.Rect(random.randint(20, width-w-20), random.randint(20, height-h-20), w, h)
            if not r.colliderect(safe_zone): return r
        return pygame.Rect(20, 20, w, h)
 
    # 5 Targets (3x3 cm or 6x6 cm)
    for _ in range(5):
        size = random.choice([3, 6])
        rect = get_valid_rect(size, size)
        cubes.append(rect)
        shapes.append({'type': 'cube', 'rect': rect})
 
    # 1 Massive Mountain (30x30 cm)
    rect = get_valid_rect(30, 30)
    mountains.append(rect)
    shapes.append({'type': 'square', 'rect': rect})
 
    # 2 Craters (30x30 to 35x35 cm)
    for _ in range(2):
        rect = get_valid_rect(random.choice([30, 35]), random.choice([30, 35]))
        craters.append(rect)
        shapes.append({'type': 'ellipse', 'rect': rect})
 
    # Solid arena bounding walls
    walls = [
        pygame.Rect(-50, -50, 50, height+100), pygame.Rect(width, -50, 50, height+100),
        pygame.Rect(-50, -50, width+100, 50),  pygame.Rect(-50, height, width+100, 50)
    ]
    return cubes, mountains, craters, walls, shapes