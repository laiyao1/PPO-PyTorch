import gym
import env

from place_db import PlaceDB
placedb = PlaceDB('adaptec1')

place_env = gym.make('place_env-v0', placedb = placedb)
print("place_env success")