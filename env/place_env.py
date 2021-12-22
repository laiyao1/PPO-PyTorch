import math
from typing import Optional

import gym
from gym import spaces, logger
from gym.utils import seeding
import numpy as np
import sys 
sys.path.append("..")
from place_db import PlaceDB
from build_graph import build_graph_from_placedb

class PlaceEnv(gym.Env):

    def __init__(self, placedb, grid = 40):
        
        # need to get GCN vector and CNN 
        assert grid * grid >= 2 * placedb.node_cnt 
        self.grid = grid
        self.max_height = placedb.max_height
        self.max_width = placedb.max_width
        self.placedb = placedb
        self.num_macro = placedb.node_cnt
        self.node_name_list = list(self.placedb.node_info.keys())
        self.action_space = spaces.Discrete(self.grid * self.grid)
        self.state = None
        self.graph = build_graph_from_placedb(self.placedb)
    
    def reset(self):
        num_macro_placed = 0
        num_macro = self.num_macro
        canvas = np.zeros((self.grid, self.grid))
        node_pos = {}
        self.state = (canvas, num_macro_placed, num_macro, node_pos)
        return self.state

    # hpwl without pin offset
    def comp_simple_hpwl(self, node_pos):
        simple_hpwl = 0
        for net_name in self.placedb.net_info:
            min_x = self.grid
            min_y = self.grid
            max_x = 0
            max_y = 0
            for node_name in self.placedb.net_info[net_name]:
                min_x = min(min_x, node_pos[0])
                min_y = min(min_y, node_pos[1])
                max_x = max(max_x, node_pos[0])
                max_y = max(max_y, node_pos[1])
        return simple_hpwl * (self.max_height / self.grid)
        
    # hpwl within pin offset
    def comp_hpwl(self):
        pass

    def step(self, action):
        err_msg = f"{action!r} ({type(action)}) invalid"
        assert self.action_space.contains(action), err_msg

        canvas, num_macro_placed, num_macro, node_pos = self.state
        # print("===action: {}".format(action))
        x = action // self.grid
        y = action % self.grid

        if canvas[x][y] == 1:
            reward = -1e8
            done = True
        else:
            canvas[x][y] = 1
            node_pos[self.node_name_list[num_macro_placed]] = (x, y)
            num_macro_placed += 1
            
            if num_macro_placed == num_macro:
                reward = -comp_simple_hpwl(node_pos)
                done = True
            else:
                reward = 0
                done = False
        
        self.state = (canvas, num_macro_placed, num_macro, node_pos)
        return self.state, reward, done, {}

    def render(self, mode='human'):
        return None
        
    def close(self):
        return None

    