import dgl
from place_db import PlaceDB

def build_graph_from_placedb(placedb):
    src_node_list = []
    dst_node_list = []
    for net_name in placedb.net_info:
        net_node_list = list(placedb.net_info[net_name].keys())
        # print("net_node_list", net_node_list)
        for i in range(len(net_node_list)-1):
            for j in range(i+1, len(net_node_list)):
                # print("i", i, "j", j)
                src_node_list.append(placedb.node_info[net_node_list[i]]['id'])
                dst_node_list.append(placedb.node_info[net_node_list[j]]['id'])
    g = dgl.graph((src_node_list, dst_node_list))
    if placedb.node_cnt > g.num_nodes():
        g.add_nodes(placedb.node_cnt - g.num_nodes())
    g = dgl.add_reverse_edges(g)
    g = dgl.add_self_loop(g)
    return g


if __name__ == "__main__":
    placedb = PlaceDB("adaptec1")
    g = build_graph_from_placedb(placedb)
    print("num of nodes: {}".format(g.num_nodes()))
    print("num of edges: {}".format(g.num_edges()))
