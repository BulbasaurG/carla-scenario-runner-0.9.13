#%%
import pickle
import numpy as np
from pathlib import Path

FILE_PATH = Path(__file__).parent

with open(str(FILE_PATH/"PedestrianCrossing-00000-of-00010.pkl"), 'rb') as f:
    data = pickle.load(f)

for key in data.keys():
    print("Key: ", key)
    print("\tshape: ", data[key].shape)
    print("\tdtype: ", data[key].dtype)
# %%
import matplotlib.pyplot as plt
# cw_ind = np.where(data['roadgraph_samples/type']==18)[0]
# plt.scatter(data["roadgraph_samples/xyz"][cw_ind,0], data["roadgraph_samples/xyz"][cw_ind,1],s=1)
biking_ind = np.where(data['roadgraph_samples/type']==3)[0]
driving_ind = np.where(data['roadgraph_samples/type']==2)[0]
plt.scatter(data["roadgraph_samples/xyz"][biking_ind,0], data["roadgraph_samples/xyz"][biking_ind,1],s=1)
plt.show()

# %%s

car_ind = np.where(data['state/type']==1)[0]
ped_ind = np.where(data['state/type']==2)[0]
cyc_ind = np.where(data['state/type']==3)[0]

for i, car in enumerate(car_ind):
    plt.plot(data["state/x"][car].squeeze(),data["state/y"][car].squeeze(),label=f"car_{i}")
for i, ped in enumerate(ped_ind):
    plt.plot(data["state/x"][ped].squeeze(),data["state/y"][ped].squeeze(),label=f"ped_{i}")
for i, cyc in enumerate(cyc_ind):
    plt.plot(data["state/x"][cyc].squeeze(),data["state/y"][cyc].squeeze(),label=f"cyc_{i}")
plt.legend()
plt.show()

# %%
# PedestrianCrossing_0 not moved, actor state shape (128,1201)
# bikepassingby not moved, actor state shape (128,1201)
# SignalizedJunctionLeftTurn_1 moved, actor state shape (128,318)
print(data["state/x"][ped_ind].squeeze().shape)

# chec bike bounding box extent
plt.plot(data["state/length"][car_ind,:].squeeze(),label='length')
plt.plot(data["state/width"][car_ind,:].squeeze(),label='width')
plt.legend()
plt.show()

#%%
data["state/length"][ped_ind,:]
data['state/width'][ped_ind,:]