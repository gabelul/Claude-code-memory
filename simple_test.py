import pandas as pd

# Simple test
df = pd.read_csv('data.csv')
df.to_json('output.json')