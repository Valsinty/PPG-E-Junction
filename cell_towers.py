import pandas as pd

cols = ['radio','mcc','net','area','cell','unit','lon','lat','range','samples','changeable','created','updated','averageSignal']
cell_tower_data = pd.read_csv('244.csv.gz', compression='gzip', 
                                 header=None, names = cols, index_col=False, sep=',', quotechar='"')

cell_tower_data
