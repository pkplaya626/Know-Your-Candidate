import pandas as pd
import os

def inject_vacancies():
    house_file = "Cleaned_House_119th.csv"
    if os.path.exists(house_file):
        df_house = pd.read_csv(house_file)
        
        # Remove outdated 118th Congress vacancies that were previously injected
        original_len = len(df_house)
        df_house = df_house[df_house['Name'] != 'Vacant Seat']
        new_len = len(df_house)
        
        if original_len != new_len:
            print(f"✅ Removed {original_len - new_len} outdated 118th Congress vacancies from {house_file}.")
        else:
            print(f"✅ No outdated vacancies found in {house_file}.")
        
        df_house.to_csv(house_file, index=False)
        
    else:
        print(f"⚠️ Warning: {house_file} not found. Please ensure it is in the current directory.")
        
if __name__ == '__main__':
    inject_vacancies()