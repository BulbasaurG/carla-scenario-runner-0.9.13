#%%
import pickle
import numpy as np
from pathlib import Path

FILE_PATH = Path(__file__).parent

with open(str(FILE_PATH/"PedestrianCrossing-00005-of-00010.pkl"), 'rb') as f:
    data = pickle.load(f)

for key in data.keys():
    print("Key: ", key)
    print("\tshape: ", data[key].shape)
    print("\tdtype: ", data[key].dtype)
# %%
import matplotlib.pyplot as plt
cw_ind = np.where(data['roadgraph_samples/type']==18)[0]
cw_id = data['roadgraph_samples/id'][cw_ind]
for cw in cw_id:
    cw_id_ind = np.where(data['roadgraph_samples/id']==cw)[0]
    if cw_id_ind.shape[0] != 5:
        print(cw_id_ind.shape)
    plt.plot(data["roadgraph_samples/xyz"][cw_id_ind,0], data["roadgraph_samples/xyz"][cw_id_ind,1],label=f"cw_{cw}")
# biking_ind = np.where(data['roadgraph_samples/type']==3)[0]
# driving_ind = np.where(data['roadgraph_samples/type']==2)[0]
# plt.scatter(data["roadgraph_samples/xyz"][biking_ind,0], data["roadgraph_samples/xyz"][biking_ind,1],s=1)
plt.show()

# %%s

car_ind = np.where(data['state/type']==1)[0]
ped_ind = np.where(data['state/type']==2)[0]
cyc_ind = np.where(data['state/type']==3)[0]
print(car_ind)
critical_time_step = [0,10,100,-1]
for step in critical_time_step:
    print(data['state/x'][0,step],data['state/y'][0,step],data['state/bbox_yaw'][0,step])
# print(data['state/length_1'][cyc_ind,1])
# print(data['state/width_1'][cyc_ind,1])
# print(data['state/length'][cyc_ind,1])
# print(data['state/width'][cyc_ind,1])
#%%
def __compute_yaw_rate(bbox_yaw_valid, t_s):
    """
    project bbox heading angle to [-pi,pi]
    """
    bbox_yaw_valid = np.arctan2(np.sin(bbox_yaw_valid),np.cos(bbox_yaw_valid))
    bbox_yaw_rate_valid = bbox_yaw_valid - np.insert(bbox_yaw_valid[:-1],0,0)
    bbox_yaw_rate_valid[0] = 0
    bbox_yaw_rate_valid = np.where(np.abs(bbox_yaw_rate_valid)>=np.pi,\
                            bbox_yaw_rate_valid-np.sign(bbox_yaw_rate_valid)*2*np.pi,\
                            bbox_yaw_rate_valid)
    return bbox_yaw_rate_valid / t_s

car_bbox_yaw = data['state/bbox_yaw'][car_ind,:].squeeze() /180 * np.pi
yaw_rate = __compute_yaw_rate(car_bbox_yaw, 1/20)
for i, car in enumerate(car_ind):
    plt.plot(car_bbox_yaw,label="bbox_yaw")
    plt.plot(yaw_rate,label="yaw_rate")
    # plt.ylim((-10,10))
    # plt.plot(data["state/x"][car].squeeze(),data["state/y"][car].squeeze(),label=f"car_{i}")
# for i, ped in enumerate(ped_ind):
#     plt.plot(data["state/x"][ped].squeeze(),data["state/y"][ped].squeeze(),label=f"ped_{i}")
# for i, cyc in enumerate(cyc_ind):
#     plt.plot(data["state/x"][cyc].squeeze(),data["state/y"][cyc].squeeze(),label=f"cyc_{i}")
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
