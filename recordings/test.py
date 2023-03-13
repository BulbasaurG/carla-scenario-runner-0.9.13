import matplotlib.pyplot as plt
import pickle

with open("/home/manolotis/scenario_runner_original/recordings/PedestrianCrossing_0.pkl", "rb") as f:
    a = pickle.load(f)

for key in a.keys():
    print("Key: ", key)
    print("\tshape: ", a[key].shape)
    print("\tdtype: ", a[key].dtype)
plt.scatter(a["roadgraph_samples/xyz"][:13300, 0], a["roadgraph_samples/xyz"][:13300, 1], s=1)
# plt.show()


plt.scatter(a["state/x"][:2, :].flatten(),a["state/y"][:2, :].flatten(), s=1)
plt.show()