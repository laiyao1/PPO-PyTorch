from gym.envs.registration import register

register(
	id = 'place_env-v0',
	entry_point = 'env.place_env:PlaceEnv'
)