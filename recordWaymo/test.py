#%%
import pickle
import numpy as np
from pathlib import Path

FILE_PATH = Path(__file__).parent

with open(str(FILE_PATH/"BikePassingby_0.pkl"), 'rb') as f:
    data = pickle.load(f)

for key in data.keys():
    print("Key: ", key)
    print("\tshape: ", data[key].shape)
    print("\tdtype: ", data[key].dtype)
# %%
