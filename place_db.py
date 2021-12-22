import numpy as np
import os
# Macro dict (macro id -> name, x, y)

def read_node_file(fopen):
    node_info = {}
    node_cnt = 0
    for line in fopen.readlines():
        if not line.startswith("\t"):
            continue
        line = line.strip().split()
        if line[-1] != "terminal":
            continue
        node_name = line[0]
        x = int(line[1])
        y = int(line[2])
        node_info[node_name] = {"id": node_cnt, "x": x, "y": y}
        node_cnt += 1
    return node_info


def read_net_file(fopen, node_info):
    net_info = {}
    net_name = None
    for line in fopen.readlines():
        if not line.startswith("\t") and not line.startswith("NetDegree"):
            continue
        line = line.strip().split()
        if line[0] == "NetDegree":
            net_name = line[-1]
        else:
            node_name = line[0]
            if node_name in node_info:
                if not net_name in net_info:
                    net_info[net_name] = {}
                x_offset = float(line[-2])
                y_offset = float(line[-1])
                net_info[net_name][node_name] = {}
                net_info[net_name][node_name] = {"x_offset": x_offset, "y_offset": y_offset}
    for net_name in list(net_info.keys()):
        if len(net_info[net_name]) <= 1:
            net_info.pop(net_name)
    return net_info


def read_pl_file(fopen, node_info):
    max_height = 0
    max_width = 0
    for line in fopen.readlines():
        if not line.startswith('o'):
            continue
        line = line.strip().split()
        node_name = line[0]
        if not node_name in node_info:
            continue
        place_x = int(line[1])
        place_y = int(line[2])
        max_height = max(max_height, node_info[node_name]["x"] + place_x)
        max_width = max(max_width, node_info[node_name]["y"] + place_y)
    return max_height, max_width


class PlaceDB():

    def __init__(self, benchmark = "adaptec1"):
        assert os.path.exists(benchmark)
        node_file = open(os.path.join(benchmark, benchmark+".nodes"), "r")
        self.node_info = read_node_file(node_file)
        self.node_cnt = len(self.node_info)
        node_file.close()
        net_file = open(os.path.join(benchmark, benchmark+".nets"), "r")
        self.net_info = read_net_file(net_file, self.node_info)
        net_file.close()
        pl_file = open(os.path.join(benchmark, benchmark+".pl"), "r")
        self.max_height, self.max_width = read_pl_file(pl_file, self.node_info)

    def debug_str(self):
        print("node_cnt = {}".format(len(self.node_info)))
        # print("node_info", self.node_info)
        print("net_cnt = {}".format(len(self.net_info)))
        # print("net_info", self.net_info)
        print("max_height = {}".format(self.max_height))
        print("max_width = {}".format(self.max_width))


if __name__ == "__main__":
    placedb = PlaceDB("adaptec1")
    placedb.debug_str()


        