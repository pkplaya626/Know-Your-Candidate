import pandas as pd
import os
import urllib.request
from io import StringIO

print("Downloading live DW-NOMINATE voting data from Voteview...")

# Download the public dataset
url = "https://voteview.com/static/data/out/members/HSall_members.csv"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req).read().decode('utf-8')

# Load into Pandas
df_voteview = pd.read_csv(StringIO(response))

# Filter out empty bioguides and sort by congress to get the most recent data per member
df_voteview = df_voteview.dropna(subset=['bioguide_id', 'nominate_dim1'])
df_voteview = df_voteview.sort_values(by=['bioguide_id', 'congress'])
df_latest = df_voteview.drop_duplicates(subset=['bioguide_id'], keep='last')

# Create a mapping dictionary for Bioguide ID -> Formatted Alignment String
voting_map = {}
for _, row in df_latest.iterrows():
    bg_id = str(row['bioguide_id']).strip()
    dim1 = float(row['nominate_dim1'])
    
    # Calculate a proxy for "party loyalty / alignment" based on how far they are from the center
    # This maps scores like 0.70 into high 90s, and scores like 0.10 into mid 80s
    abs_score = abs(dim1)
    loyalty_pct = min(99, int(80 + (abs_score * 30))) 
    
    # Generate human readable labels based on the -1 to +1 spectrum
    if dim1 < -0.4:
        label = "Solidly Progressive"
    elif dim1 < -0.1:
        label = "Moderate Democrat"
    elif dim1 <= 0.1:
        label = "Centrist / Swing Voter"
        loyalty_pct = "Split"
    elif dim1 <= 0.4:
        label = "Moderate Republican"
    else:
        label = "Solidly Conservative"
        
    loyalty_str = f"~{loyalty_pct}% Party Loyalty" if loyalty_pct != "Split" else "Highly Independent"
    formatted_str = f"DW-NOMINATE: {dim1:+.2f} ({label}) • {loyalty_str}"
    
    voting_map[bg_id] = formatted_str

# Update local CSV files
files_to_update = ["Cleaned_House_119th.csv", "Cleaned_Senate_119th.csv"]

for file in files_to_update:
    if os.path.exists(file):
        df = pd.read_csv(file)
        
        # Apply the mapping if they have a Bioguide ID
        def apply_alignment(row):
            bg_id = str(row.get('Bioguide ID')).strip()
            # If we found real data, use it. Otherwise keep what they had.
            return voting_map.get(bg_id, row.get('Projected/Historical Voting Alignment'))
            
        df['Projected/Historical Voting Alignment'] = df.apply(apply_alignment, axis=1)
        df.to_csv(file, index=False)
        print(f"Injected historical voting alignment data into {file}")

print("\nDone! You can now re-run 'python build_profile_site.py' to update your UI.")