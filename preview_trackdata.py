import pandas as pd
from pprint import pprint
pd.set_option('display.max_columns', None)

file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/data/00_tracks.csv"
df = pd.read_csv(file)
df = df.loc[df.trackId != 51]
df = df.loc[df.trackId != 52]
print(file)
# pprint(df.columns)
pprint(df.head(3))

# count rows in each trackId group
counts = df.groupby('trackId').size().sort_values(ascending=False)

# get top 5 trackIds with the largest group size
top5_trackIds = counts.head(5)
print("Top 5 trackIds by group size:")
print(top5_trackIds)

# get the rows belonging to those top 5 trackIds
top5_tracks = df[df['trackId'].isin(top5_trackIds.index)]

pprint(top5_tracks.head(20))
