import torch
import torch.nn as nn
from torch.distributions import MultivariateNormal
from torch.distributions import Categorical
from gcn import PlaceGCN
import torchvision.models as models
from resnet import resnet20

################################## set device ##################################

print("============================================================================================")


# set device to cpu or cuda
device = torch.device('cpu')

if(torch.cuda.is_available()): 
    device = torch.device('cuda:0') 
    torch.cuda.empty_cache()
    print("Device set to : " + str(torch.cuda.get_device_name(device)))
else:
    print("Device set to : cpu")
    
print("============================================================================================")




################################## PPO Policy ##################################


class RolloutBuffer:
    def __init__(self):
        self.actions = []
        self.states = []
        self.logprobs = []
        self.rewards = []
        self.is_terminals = []
    

    def clear(self):
        del self.actions[:]
        del self.states[:]
        del self.logprobs[:]
        del self.rewards[:]
        del self.is_terminals[:]


class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim, graph_emb_dim, graph, has_continuous_action_space, action_std_init):
        super(ActorCritic, self).__init__()

        self.has_continuous_action_space = has_continuous_action_space

        if has_continuous_action_space:
            self.action_dim = action_dim
            self.action_var = torch.full((action_dim,), action_std_init * action_std_init).to(device)

        # gcn
        self.gcn = PlaceGCN(graph_emb_dim).to(device)
        # actor
        self.actor = nn.Sequential(
                        nn.Linear(32 + 64, 64), # GCN + CNN
                        nn.Tanh(),
                        nn.Linear(64, 64),
                        nn.Tanh(),
                        nn.Linear(64, action_dim),
                        # nn.Softmax(dim=-1)
        )
        
        # critic
        self.critic = nn.Sequential(
                        nn.Linear(32 + 64, 64),
                        nn.Tanh(),
                        nn.Linear(64, 64),
                        nn.Tanh(),
                        nn.Linear(64, 1)
                    )
        
        self.graph = graph
        self.resnet = resnet20().to(device)
        self.softmax = nn.Softmax(dim=-1)
        
    def set_action_std(self, new_action_std):

        if self.has_continuous_action_space:
            self.action_var = torch.full((self.action_dim,), new_action_std * new_action_std).to(device)
        else:
            print("--------------------------------------------------------------------------------------------")
            print("WARNING : Calling ActorCritic::set_action_std() on discrete action space policy")
            print("--------------------------------------------------------------------------------------------")


    def forward(self):
        raise NotImplementedError
    

    def act(self, state):
        one_hot_input = torch.eye(self.graph.num_nodes()).to(device)
        gcn_res = self.gcn(self.graph, one_hot_input)
        grid = int((state.shape[-1]-1) ** 0.5)
        cnn_input = state[1:].reshape(1, 1, grid, grid).float().to(device)
        # print("cnn_input", cnn_input)
        cnn_res = self.resnet(cnn_input)
        gcn_res = gcn_res[state[0].int()]
        gcn_res = gcn_res.squeeze()
        cnn_res = cnn_res.squeeze()
        # print("gcn_res shape", gcn_res.shape)
        # print("cnn_res shape", cnn_res.shape)
        cat_feature = torch.cat((gcn_res, cnn_res)).to(device)
        # print("cat feature", cat_feature)
        action_probs_tmp = self.actor(cat_feature)
        mask = state[1:].float().to(device)
        # print("mask sum = {}".format(mask.sum()))
        # print("mask", mask)
        # print("mask shape", mask.shape)
        action_probs = self.softmax(action_probs_tmp - 1.0e8 * mask)
        # print("action_probs", action_probs)
        dist = Categorical(action_probs)

        action = dist.sample()
        action_logprob = dist.log_prob(action)
        
        return action.detach(), action_logprob.detach()
    

    def evaluate(self, state, action):
        # print("===evaluate state===")
        # print(state)
        # print("state shape", state.shape)
        one_hot_input = torch.eye(self.graph.num_nodes()).to(device)
        gcn_res = self.gcn(self.graph, one_hot_input)
        grid = int((state.shape[-1] - 1) ** 0.5)
        # print("state shape", state.shape)
        cnn_input = state[:, 1:].reshape(-1, 1, grid, grid).float().to(device)
        # print("cnn_input shape", cnn_input.shape)
        cnn_res = self.resnet(cnn_input)
        # print("cnn_res shape", cnn_res.shape)
        gcn_res = torch.index_select(gcn_res, 0, state[:, 0].int().squeeze())
        # print("gcn_res shape", gcn_res.shape)
        gcn_res = gcn_res.squeeze()
        cnn_res = cnn_res.squeeze()
        cat_feature = torch.cat((gcn_res, cnn_res), dim = -1)
        action_probs_tmp = self.actor(cat_feature)
        mask = state[:, 1:].float().to(device)
        action_probs = self.softmax(mask * action_probs_tmp)
        dist = Categorical(action_probs)

        action_logprobs = dist.log_prob(action)
        dist_entropy = dist.entropy()
        state_values = self.critic(cat_feature)
        
        return action_logprobs, state_values, dist_entropy


class PPO:
    def __init__(self, state_dim, action_dim, graph_emb_dim, graph, lr_actor, lr_critic, gamma, K_epochs, 
                    eps_clip, has_continuous_action_space, action_std_init=0.6):

        self.has_continuous_action_space = has_continuous_action_space

        if has_continuous_action_space:
            self.action_std = action_std_init

        self.gamma = gamma
        self.eps_clip = eps_clip
        self.K_epochs = K_epochs
        
        self.buffer = RolloutBuffer()

        self.policy = ActorCritic(state_dim, action_dim, graph_emb_dim, graph, has_continuous_action_space, action_std_init).to(device)
        self.optimizer = torch.optim.Adam([
                        {'params': self.policy.actor.parameters(), 'lr': lr_actor},
                        {'params': self.policy.critic.parameters(), 'lr': lr_critic}
                    ])

        self.policy_old = ActorCritic(state_dim, action_dim, graph_emb_dim, graph, has_continuous_action_space, action_std_init).to(device)
        self.policy_old.load_state_dict(self.policy.state_dict())
        
        self.MseLoss = nn.MSELoss()
        self.graph = graph


    def set_action_std(self, new_action_std):
        
        if self.has_continuous_action_space:
            self.action_std = new_action_std
            self.policy.set_action_std(new_action_std)
            self.policy_old.set_action_std(new_action_std)
        
        else:
            print("--------------------------------------------------------------------------------------------")
            print("WARNING : Calling PPO::set_action_std() on discrete action space policy")
            print("--------------------------------------------------------------------------------------------")


    def decay_action_std(self, action_std_decay_rate, min_action_std):
        print("--------------------------------------------------------------------------------------------")

        if self.has_continuous_action_space:
            self.action_std = self.action_std - action_std_decay_rate
            self.action_std = round(self.action_std, 4)
            if (self.action_std <= min_action_std):
                self.action_std = min_action_std
                print("setting actor output action_std to min_action_std : ", self.action_std)
            else:
                print("setting actor output action_std to : ", self.action_std)
            self.set_action_std(self.action_std)

        else:
            print("WARNING : Calling PPO::decay_action_std() on discrete action space policy")

        print("--------------------------------------------------------------------------------------------")


    def select_action(self, state):

        if self.has_continuous_action_space:
            with torch.no_grad():
                # state = torch.FloatTensor(state).to(device)
                action, action_logprob = self.policy_old.act(state)
            # print("===state", state)
            self.buffer.states.append(torch.tensor([state], dtype = torch.int32))
            self.buffer.actions.append(action)
            self.buffer.logprobs.append(action_logprob)

            return action.detach().cpu().numpy().flatten()

        else:
            with torch.no_grad():
                # state = torch.FloatTensor(state).to(device)
                action, action_logprob = self.policy_old.act(state)
            # print("===state", state)
            self.buffer.states.append(state)
            self.buffer.actions.append(action)
            self.buffer.logprobs.append(action_logprob)

            return action.item()


    def update(self):

        # Monte Carlo estimate of returns
        rewards = []
        discounted_reward = 0
        for reward, is_terminal in zip(reversed(self.buffer.rewards), reversed(self.buffer.is_terminals)):
            if is_terminal:
                discounted_reward = 0
            discounted_reward = reward + (self.gamma * discounted_reward)
            rewards.insert(0, discounted_reward)
            
        # Normalizing the rewards
        rewards = torch.tensor(rewards, dtype=torch.float32).to(device)
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)

        # convert list to 
        # print("===self.buffer.states===")
        # print(self.buffer.states)
        old_states = torch.squeeze(torch.stack(self.buffer.states, dim=0)).detach().to(device)
        old_actions = torch.squeeze(torch.stack(self.buffer.actions, dim=0)).detach().to(device)
        old_logprobs = torch.squeeze(torch.stack(self.buffer.logprobs, dim=0)).detach().to(device)

        
        # Optimize policy for K epochs
        for _ in range(self.K_epochs):

            # Evaluating old actions and values
            logprobs, state_values, dist_entropy = self.policy.evaluate(old_states, old_actions)

            # match state_values tensor dimensions with rewards tensor
            state_values = torch.squeeze(state_values)
            
            # Finding the ratio (pi_theta / pi_theta__old)
            ratios = torch.exp(logprobs - old_logprobs.detach())

            # Finding Surrogate Loss
            advantages = rewards - state_values.detach()   
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1-self.eps_clip, 1+self.eps_clip) * advantages

            # final loss of clipped objective PPO
            loss = -torch.min(surr1, surr2) + 0.5*self.MseLoss(state_values, rewards) - 0.01*dist_entropy
            
            # take gradient step
            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()
            
        # Copy new weights into old policy
        self.policy_old.load_state_dict(self.policy.state_dict())

        # clear buffer
        self.buffer.clear()
    
    
    def save(self, checkpoint_path):
        torch.save(self.policy_old.state_dict(), checkpoint_path)
   

    def load(self, checkpoint_path):
        self.policy_old.load_state_dict(torch.load(checkpoint_path, map_location=lambda storage, loc: storage))
        self.policy.load_state_dict(torch.load(checkpoint_path, map_location=lambda storage, loc: storage))
        
        
       


