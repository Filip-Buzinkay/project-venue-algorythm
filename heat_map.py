from math import hypot
import heapq

class venusMap:
    def __init__(self, gridSize=10):
        self.gridSize = gridSize
        self.known = {}
        self.obstacles = set()
        self.clankers = []
        self.bingo = []

    def gridLock(self, pos):
        return (int(round(pos[0]/self.gridSize)*self.gridSize),
                int(round(pos[1]/self.gridSize)*self.gridSize))
    
    def claim(self, pos):
        policko = self.gridLock(pos)
        self.known[policko] = self.known.get(policko, 0) + 1 

    def mark_obstacle(self, pos):
        self.obstacles.add(self.gridLock(pos))

    def found_cubes(self, pos):
        for cube in self.bingo:
            # 10cm grouping to prevent double counting tiny cubes
            if hypot(cube[0] - pos[0], cube[1] - pos[1]) < 10: 
                return
        self.bingo.append(pos)
        print(f'I got a jar of dirt @{pos} count: {len(self.bingo)}') 
    
    def feel_the_heat(self, pos):
        return self.known.get(self.gridLock(pos), 0)

    def find_nearest_unknown(self, start_pos):
        start_node = self.gridLock(start_pos)
        queue = [start_node]
        visited = set([start_node])

        while queue:
            curr = queue.pop(0)
            if curr not in self.known:
                return curr
            
            for dx, dy in [(self.gridSize, 0), (-self.gridSize, 0), (0, self.gridSize), (0, -self.gridSize)]:
                nxt = (curr[0] + dx, curr[1] + dy)
                if nxt not in visited and nxt not in self.obstacles:
                    visited.add(nxt)
                    queue.append(nxt)
                    
            if len(visited) > 2000: 
                break
        return None

    def astar(self, start_pos, goal_pos):
        start = self.gridLock(start_pos)
        goal = self.gridLock(goal_pos)
        
        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return path
            
            for dx, dy in [(self.gridSize, 0), (-self.gridSize, 0), (0, self.gridSize), (0, -self.gridSize),
                           (self.gridSize, self.gridSize), (-self.gridSize, -self.gridSize), 
                           (self.gridSize, -self.gridSize), (-self.gridSize, self.gridSize)]:
                nxt = (current[0] + dx, current[1] + dy)
                
                if nxt in self.obstacles:
                    continue
                    
                cost = g_score[current] + hypot(dx, dy)
                
                for ox, oy in [(-self.gridSize, 0), (self.gridSize, 0), (0, -self.gridSize), (0, self.gridSize)]:
                    if (nxt[0]+ox, nxt[1]+oy) in self.obstacles:
                        cost += 100 
                        
                if nxt not in g_score or cost < g_score[nxt]:
                    came_from[nxt] = current
                    g_score[nxt] = cost
                    f_score = cost + hypot(goal[0]-nxt[0], goal[1]-nxt[1])
                    heapq.heappush(open_set, (f_score, nxt))
                    
            if len(came_from) > 1000: 
                break
        return []