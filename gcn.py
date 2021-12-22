import dgl
import numpy as np
import torch
from dgl.nn import GraphConv

# def make_gcn_model(in_feats):
#     gcn = torch.nn.Sequential(
#         GraphConv(in_feats = in_feats, out_feats = 64, norm='both', weight=True, bias=True, 
#             activation = torch.nn.ReLU(), allow_zero_in_degree=False),
#         GraphConv(in_feats = 64, out_feats = 32, norm='both', weight=True, bias=True, 
#             activation = torch.nn.ReLU(), allow_zero_in_degree=False)
#     )
#     gcn = GraphConv(in_feats = in_feats, out_feats = 64, norm='both', weight=True, bias=True, 
#              activation = torch.nn.ReLU, allow_zero_in_degree=True)
#     return gcn

gcn_msg = dgl.function.copy_u(u='h', out='m')
gcn_reduce = dgl.function.sum(msg='m', out='h')

class GCNLayer(torch.nn.Module):
    def __init__(self, in_feats, out_feats):
        super(GCNLayer, self).__init__()
        self.linear = torch.nn.Linear(in_feats, out_feats)

    def forward(self, g, feature):
        # Creating a local scope so that all the stored ndata and edata
        # (such as the `'h'` ndata below) are automatically popped out
        # when the scope exits.
        with g.local_scope():
            g.ndata['h'] = feature
            g.update_all(gcn_msg, gcn_reduce)
            h = g.ndata['h']
            return self.linear(h)


class PlaceGCN(torch.nn.Module):
    def __init__(self, in_feats):
        super(PlaceGCN, self).__init__()
        # self.layer1 = GraphConv(in_feats = in_feats, out_feats = 64, norm='both', weight=True, bias=True, 
        #     allow_zero_in_degree=False)
        # self.layer2 = GraphConv(in_feats = 64, out_feats = 32, norm='both', weight=True, bias=True, 
        #     allow_zero_in_degree=False)
        self.layer1 = GCNLayer(in_feats, 64)
        self.layer2 = GCNLayer(64, 32)

    def forward(self, g, features):
        x = torch.nn.functional.relu(self.layer1(g, features))
        x = self.layer2(g, x)
        return x


if __name__ == "__main__":
    # in_feats = 500
    g = dgl.graph(([0,1,2,3,2,5], [1,2,3,4,0,3]))
    g = dgl.add_self_loop(g)
    feat = torch.ones(6, 10)
    conv = GraphConv(10, 2, norm='both', activation = torch.nn.ReLU(), weight=True, bias=True)
    res = conv(g, feat)
    print(res)