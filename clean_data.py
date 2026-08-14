import pandas as pd
import os
import re
import shutil

base_map = {
    'HSVR': "House Committee on Veterans' Affairs",
    'HSAP': "House Committee on Appropriations",
    'HSAS': "House Committee on Armed Services",
    'HSSM': "House Committee on Small Business",
    'SSCM': "Senate Committee on Commerce, Science, and Transportation",
    'HSII': "House Committee on Natural Resources",
    'HSAG': "House Committee on Agriculture",
    'SSEV': "Senate Committee on Environment and Public Works",
    'HSHA': "Committee on House Administration",
    'HSFA': "House Committee on Foreign Affairs",
    'SSAP': "Senate Committee on Appropriations",
    'HSPW': "House Committee on Transportation and Infrastructure",
    'HSHM': "House Committee on Homeland Security",
    'SSFI': "Senate Committee on Finance",
    'SSJU': "Senate Committee on the Judiciary",
    'SSFR': "Senate Committee on Foreign Relations",
    'HSIF': "House Committee on Energy and Commerce",
    'HSJU': "House Committee on the Judiciary",
    'SSGA': "Senate Committee on Homeland Security and Governmental Affairs",
    'SSBK': "Senate Committee on Banking, Housing, and Urban Affairs",
    'SSAF': "Senate Committee on Agriculture, Nutrition, and Forestry",
    'HSBA': "House Committee on Financial Services",
    'SSAS': "Senate Committee on Armed Services",
    'HSGO': "House Committee on Oversight and Accountability",
    'HSSY': "House Committee on Science, Space, and Technology",
    'HSWM': "House Committee on Ways and Means",
    'HLIG': "House Permanent Select Committee on Intelligence",
    'SSEG': "Senate Committee on Energy and Natural Resources",
    'SSHR': "Senate Committee on Health, Education, Labor, and Pensions",
    'HSRU': "House Committee on Rules",
    'HSED': "House Committee on Education and the Workforce",
    'JSTX': "Joint Committee on Taxation",
    'JSEC': "Joint Economic Committee",
    'SSVA': "Senate Committee on Veterans' Affairs",
    'SSIN': "Senate Select Committee on Indian Affairs",
    'SSSB': "Senate Committee on Small Business and Entrepreneurship",
    'SSRA': "Senate Committee on Rules and Administration",
    'SSBU': "Senate Committee on the Budget",
    'HSBU': "House Committee on the Budget"
}

def clean_committees(cell):
    if pd.isna(cell) or str(cell).strip() == "": 
        return cell
    
    parts = str(cell).split(';')
    cleaned = []
    
    for p in parts:
        p = p.strip()
        if not p: continue
        
        match = re.match(r'^([A-Z]{4})(\d{2})?$', p)
        if match:
            prefix = match.group(1)
            is_sub = bool(match.group(2)) 
            
            if prefix in base_map:
                name = base_map[prefix]
                if is_sub:
                    cleaned.append(f"{name} (Subcommittee)")
                else:
                    cleaned.append(name)
            else:
                cleaned.append(p)
        else:
            cleaned.append(p)
            
    seen = set()
    final_list = []
    for c in cleaned:
        if c not in seen:
            seen.add(c)
            final_list.append(c)
            
    return "; ".join(final_list)

# Route the newly uploaded files to their base names so build_profile_site.py works seamlessly
file_mapping = {
    "Cleaned_House_119th_3.csv": "Cleaned_House_119th.csv",
    "Cleaned_House_119th_2.csv": "Cleaned_House_119th.csv",
    "Cleaned_Senate_119th_3.csv": "Cleaned_Senate_119th.csv",
    "Cleaned_Senate_119th_2.csv": "Cleaned_Senate_119th.csv",
    "Completed_Primary_Candidates_2026_3.csv": "Completed_Primary_Candidates_2026.csv",
    "Late_Primary_Candidates_2026_2.csv": "Late_Primary_Candidates_2026.csv",
    "Congressional_Candidates_2026_2.csv": "Congressional_Candidates_2026.csv",
    "Congressional_Current_Congress_119th_2.csv": "Congressional_Current_Congress_119th.csv"
}

for src, dst in file_mapping.items():
    if os.path.exists(src):
        # We will copy the highest numbered file, so we process ordered
        pass

# Actually, just copy directly. Highest numbers first will overwrite lower numbers if done right, 
# or just process specifically:
to_copy = [
    ("Cleaned_House_119th_3.csv", "Cleaned_House_119th.csv"),
    ("Cleaned_Senate_119th_3.csv", "Cleaned_Senate_119th.csv"),
    ("Completed_Primary_Candidates_2026_3.csv", "Completed_Primary_Candidates_2026.csv"),
    ("Late_Primary_Candidates_2026_2.csv", "Late_Primary_Candidates_2026.csv"),
    ("Congressional_Candidates_2026_2.csv", "Congressional_Candidates_2026.csv"),
    ("Congressional_Current_Congress_119th_2.csv", "Congressional_Current_Congress_119th.csv")
]

for src, dst in to_copy:
    if os.path.exists(src):
        shutil.copy(src, dst)
        print(f"Copied {src} over {dst}")

# Clean the base files
for file in ["Cleaned_House_119th.csv", "Cleaned_Senate_119th.csv", "Congressional_Current_Congress_119th.csv"]:
    if os.path.exists(file):
        df = pd.read_csv(file)
        if 'Committee Assignments' in df.columns:
            df['Committee Assignments'] = df['Committee Assignments'].apply(clean_committees)
            df.to_csv(file, index=False)
            print(f"Cleaned committees in {file}")

# Re-run build_profile_site.py
import subprocess
if os.path.exists('build_profile_site.py'):
    print("\nRunning build_profile_site.py...")
    result = subprocess.run(['python', 'build_profile_site.py'], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)