import pandas as pd
import os

def inject_election_data():
    print("Parsing 2026 Senate Election Data...")
    
    # 1. Parse and generate Challenger/Candidate Data
    challengers = [
        {"Name": "Mike Collins", "Party": "Republican", "Office / District": "GA"},
        {"Name": "Josh Turek", "Party": "Democrat", "Office / District": "IA"},
        {"Name": "Ashley Hinson", "Party": "Republican", "Office / District": "IA"},
        {"Name": "Adam Hamilton", "Party": "Democrat", "Office / District": "KS"},
        {"Name": "Troy Jackson", "Party": "Democrat", "Office / District": "ME"},
        {"Name": "Abdul El-Sayed", "Party": "Democrat", "Office / District": "MI"},
        {"Name": "Mike Rogers", "Party": "Republican", "Office / District": "MI"},
        {"Name": "Alani Bankhead", "Party": "Democrat", "Office / District": "MT"},
        {"Name": "Kurt Alme", "Party": "Republican", "Office / District": "MT"},
        {"Name": "Seth Bodnar", "Party": "Democrat", "Office / District": "MT"},
        {"Name": "Roy Cooper", "Party": "Democrat", "Office / District": "NC"},
        {"Name": "Michael Whatley", "Party": "Republican", "Office / District": "NC"},
        {"Name": "Dan Osborn", "Party": "Independent", "Office / District": "NE"},
        {"Name": "Sherrod Brown", "Party": "Democrat", "Office / District": "OH"},
        {"Name": "Annie Andrews", "Party": "Democrat", "Office / District": "SC"},
        {"Name": "James Talarico", "Party": "Democrat", "Office / District": "TX"},
        {"Name": "Ken Paxton", "Party": "Republican", "Office / District": "TX"},
        {"Name": "Everett Wess", "Party": "Democrat", "Office / District": "AL"},
        {"Name": "Barry Moore", "Party": "Republican", "Office / District": "AL"},
        {"Name": "Hallie Shoffner", "Party": "Democrat", "Office / District": "AR"},
        {"Name": "Mark Baisley", "Party": "Republican", "Office / District": "CO"},
        {"Name": "Todd Achilles", "Party": "Democrat", "Office / District": "ID"},
        {"Name": "Juliana Stratton", "Party": "Democrat", "Office / District": "IL"},
        {"Name": "Don Tracy", "Party": "Republican", "Office / District": "IL"},
        {"Name": "Charles Booker", "Party": "Democrat", "Office / District": "KY"},
        {"Name": "Andy Barr", "Party": "Republican", "Office / District": "KY"},
        {"Name": "Jamie Davis", "Party": "Democrat", "Office / District": "LA"},
        {"Name": "Julia Letlow", "Party": "Republican", "Office / District": "LA"},
        {"Name": "Scott Colom", "Party": "Democrat", "Office / District": "MS"},
        {"Name": "Justin Murphy", "Party": "Republican", "Office / District": "NJ"},
        {"Name": "Larry Marker", "Party": "Republican", "Office / District": "NM"},
        {"Name": "Kevin Hern", "Party": "Republican", "Office / District": "OK"},
        {"Name": "David Smith", "Party": "Republican", "Office / District": "OR"},
        {"Name": "Brian Bengs", "Party": "Democrat", "Office / District": "SD"},
        {"Name": "Marquita Bradshaw", "Party": "Democrat", "Office / District": "TN"},
        {"Name": "Bert Mizusawa", "Party": "Republican", "Office / District": "VA"},
        {"Name": "Rachel Fetty Anderson", "Party": "Democrat", "Office / District": "WV"}
    ]
    
    df_cands = pd.DataFrame(challengers)
    df_cands['Chamber'] = 'Senate'
    df_cands['Status'] = 'Candidate'
    
    # Fill in blanks expected by the web builder script
    expected_cols = [
        "Projected Start", "Age", "Birthdate", "Education", 
        "Previous Professions", "Campaign Receipts", "Campaign Disbursements", 
        "Main Funding Sources", "Core Campaigning Issues & Platform Focus", 
        "Projected/Historical Voting Alignment", 
        "Historical Committee Assignments (If any)", "Estimated Net Worth"
    ]
    for c in expected_cols:
        df_cands[c] = "N/A"
        
    cand_file = "Congressional_Candidates_2026.csv"
    df_cands.to_csv(cand_file, index=False)
    print(f"✅ Successfully wrote {len(challengers)} challengers to {cand_file}")

    # 2. Update existing Incumbents Data
    incumbent_updates = {
        "Joni Ernst": "Retiring in 2026",
        "Gary Peters": "Retiring in 2026",
        "Tina Smith": "Retiring in 2026",
        "Steve Daines": "Retiring in 2026",
        "Thom Tillis": "Retiring in 2026",
        "Jeanne Shaheen": "Retiring in 2026",
        "John Cornyn": "Defeated in 2026 Primary",
        "Tommy Tuberville": "Retiring in 2026 (Running for Gov)",
        "Dick Durbin": "Retiring in 2026",
        "Mitch McConnell": "Retiring in 2026",
        "Bill Cassidy": "Defeated in 2026 Primary",
        "Cynthia Lummis": "Retiring in 2026",
        "Alan Armstrong": "Incumbent (Not running in '26)"
    }
    
    # Add newly appointed senators acting as 119th incumbents
    new_incumbents = [
        {"Name": "Ashley Moody", "State": "FL", "Party": "Republican", "Chamber": "Senate", "Status": "Incumbent (2026 Special)", "Term Start": "2025"},
        {"Name": "Jon Husted", "State": "OH", "Party": "Republican", "Chamber": "Senate", "Status": "Incumbent (2026 Special)", "Term Start": "2025"},
        {"Name": "Darline Graham", "State": "SC", "Party": "Republican", "Chamber": "Senate", "Status": "Incumbent (2026 Special)", "Term Start": "2026"},
        {"Name": "Alan Armstrong", "State": "OK", "Party": "Republican", "Chamber": "Senate", "Status": "Incumbent (Not running in '26)", "Term Start": "2026"},
    ]

    senate_file = "Cleaned_Senate_119th.csv"
    if os.path.exists(senate_file):
        df_senate = pd.read_csv(senate_file)
        
        # Ensure Status column exists
        if 'Status' not in df_senate.columns:
            df_senate['Status'] = "Active Member"
            
        # Update matching names
        for name, status in incumbent_updates.items():
            df_senate.loc[df_senate['Name'].str.contains(name, na=False, case=False), 'Status'] = status
            
        # Append special appointees if they don't already exist
        existing_names = df_senate['Name'].dropna().tolist()
        to_append = []
        for inc in new_incumbents:
            if not any(inc['Name'].lower() in str(n).lower() for n in existing_names):
                to_append.append(inc)
                
        if to_append:
            df_senate = pd.concat([df_senate, pd.DataFrame(to_append)], ignore_index=True)
            
        df_senate.to_csv(senate_file, index=False)
        print(f"✅ Updated {senate_file} with {len(incumbent_updates)} retirements/defeats and {len(to_append)} new appointees.")
    else:
        print(f"⚠️ Warning: {senate_file} not found. Ensure your ground-truth CSV is in the directory to update incumbent statuses.")

if __name__ == '__main__':
    inject_election_data()