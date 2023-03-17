#%%
import pickle
import numpy as np
from pathlib import Path

FILE_PATH = Path(__file__).parent

with open(str(FILE_PATH/"SignalizedJunctionLeftTurn-00000-of-00010.pkl"), 'rb') as f:
    data = pickle.load(f)

for key in data.keys():
    print("Key: ", key)
    print("\tshape: ", data[key].shape)
    print("\tdtype: ", data[key].dtype)
# %%
import matplotlib.pyplot as plt
cw_ind = np.where(data['roadgraph_samples/type']==18)[0]
plt.scatter(data["roadgraph_samples/xyz"][cw_ind,0], data["roadgraph_samples/xyz"][cw_ind,1],s=1)
plt.show()

# %%s

car_ind = np.where(data['state/type']==1)[0]
ped_ind = np.where(data['state/type']==2)[0]
cyc_ind = np.where(data['state/type']==3)[0]

for i, car in enumerate(car_ind):
    plt.plot(data["state/x"][car].squeeze(),data["state/y"][car].squeeze(),label=f"car_{i}")
for i, ped in enumerate(ped_ind):
    plt.plot(data["state/x"][ped].squeeze(),data["state/y"][ped].squeeze(),label=f"ped_{i}")
plt.legend()
plt.show()

# %%
# PedestrianCrossing_0 not moved, actor state shape (128,1201)
# bikepassingby not moved, actor state shape (128,1201)
# SignalizedJunctionLeftTurn_1 moved, actor state shape (128,318)
print(data["state/x"][ped_ind].squeeze())


