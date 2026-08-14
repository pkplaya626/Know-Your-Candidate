import pandas as pd
import json
import os
import zipfile
import shutil
import re

def build_website():
    # Helper to aggressively find the newest version of your files
    def get_latest_csv(prefix):
        for opt in [f"{prefix}_5.csv", f"{prefix}_4.csv", f"{prefix}_3.csv", f"{prefix}_2.csv", f"{prefix}.csv"]:
            if os.path.exists(opt): return opt
        return None
        
    house_csv = get_latest_csv('Cleaned_House_119th')
    senate_csv = get_latest_csv('Cleaned_Senate_119th')
    completed_cand_csv = get_latest_csv('Completed_Primary_Candidates_2026')
    late_cand_csv = get_latest_csv('Late_Primary_Candidates_2026')

    def deduplicate_congress_df(df):
        def make_key(r):
            chamber = str(r.get('Chamber', '')).strip()
            state = str(r.get('State', '')).strip()
            dist = str(r.get('District', '')).strip()
            name = str(r.get('Name', '')).strip()
            
            if 'House' in chamber:
                if 'large' in dist.lower() or 'al' in dist.lower() or dist == '0':
                    dist_num = "0"
                else:
                    m = re.search(r'\d+', dist)
                    dist_num = m.group(0) if m else dist.lower().strip()
                return f"House_{state}_{dist_num}"
            else:
                if 'Vacant' in name:
                    return f"Vacant_{state}_{dist}"
                return f"Senate_{state}_{name}"
                
        df['dedup_key'] = df.apply(make_key, axis=1)
        return df.drop_duplicates(subset=['dedup_key'], keep='last').drop(columns=['dedup_key'])

    current_dfs = []
    if house_csv: current_dfs.append(pd.read_csv(house_csv))
    if senate_csv: current_dfs.append(pd.read_csv(senate_csv))

    if current_dfs:
        df_current = deduplicate_congress_df(pd.concat(current_dfs, ignore_index=True))
    else:
        fallback_curr = get_latest_csv('Congressional_Current_Congress_119th')
        if fallback_curr:
            df_current = deduplicate_congress_df(pd.read_csv(fallback_curr))
        else:
            df_current = pd.DataFrame()

    cand_dfs = []
    if completed_cand_csv: cand_dfs.append(pd.read_csv(completed_cand_csv))
    if late_cand_csv: cand_dfs.append(pd.read_csv(late_cand_csv))

    if cand_dfs:
        df_candidates = pd.concat(cand_dfs, ignore_index=True).drop_duplicates(subset=['Name'], keep='last')
    else:
        fallback_cand = get_latest_csv('Congressional_Candidates_2026')
        if fallback_cand:
            df_candidates = pd.read_csv(fallback_cand).drop_duplicates(subset=['Name'], keep='last')
        else:
            df_candidates = pd.DataFrame()

    hardcoded_challengers = [
        {"Name": "Everett Wess", "Party": "Democrat", "Office / District": "AL", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Barry Moore", "Party": "Republican", "Office / District": "AL", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Hallie Shoffner", "Party": "Democrat", "Office / District": "AR", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Mark Baisley", "Party": "Republican", "Office / District": "CO", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Todd Achilles", "Party": "Democrat", "Office / District": "ID", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Juliana Stratton", "Party": "Democrat", "Office / District": "IL", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Don Tracy", "Party": "Republican", "Office / District": "IL", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Charles Booker", "Party": "Democrat", "Office / District": "KY", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Andy Barr", "Party": "Republican", "Office / District": "KY", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Jamie Davis", "Party": "Democrat", "Office / District": "LA", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Julia Letlow", "Party": "Republican", "Office / District": "LA", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Scott Colom", "Party": "Democrat", "Office / District": "MS", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Justin Murphy", "Party": "Republican", "Office / District": "NJ", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Larry Marker", "Party": "Republican", "Office / District": "NM", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "TBD - Runoff Winner", "Party": "Democrat", "Office / District": "OK", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Kevin Hern", "Party": "Republican", "Office / District": "OK", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "David Smith", "Party": "Republican", "Office / District": "OR", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Brian Bengs", "Party": "Democrat", "Office / District": "SD", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Marquita Bradshaw", "Party": "Democrat", "Office / District": "TN", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Bert Mizusawa", "Party": "Republican", "Office / District": "VA", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Rachel Fetty Anderson", "Party": "Democrat", "Office / District": "WV", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "James Talarico", "Party": "Democrat", "Office / District": "TX", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Ken Paxton", "Party": "Republican", "Office / District": "TX", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Abdul El-Sayed", "Party": "Democrat", "Office / District": "MI", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Mike Rogers", "Party": "Republican", "Office / District": "MI", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Alani Bankhead", "Party": "Democrat", "Office / District": "MT", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Kurt Alme", "Party": "Republican", "Office / District": "MT", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Seth Bodnar", "Party": "Democrat", "Office / District": "MT", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Roy Cooper", "Party": "Democrat", "Office / District": "NC", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Michael Whatley", "Party": "Republican", "Office / District": "NC", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Dan Osborn", "Party": "Independent", "Office / District": "NE", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Josh Turek", "Party": "Democrat", "Office / District": "IA", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Ashley Hinson", "Party": "Republican", "Office / District": "IA", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Mike Collins", "Party": "Republican", "Office / District": "GA", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Troy Jackson", "Party": "Democrat", "Office / District": "ME", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Sherrod Brown", "Party": "Democrat", "Office / District": "OH", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Annie Andrews", "Party": "Democrat", "Office / District": "SC", "Chamber": "Senate", "Upcoming 2026 Primary": False},
        {"Name": "Republican Nominee", "Party": "Republican", "Office / District": "AK", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Republican Nominee", "Party": "Republican", "Office / District": "DE", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Democratic Nominee", "Party": "Democrat", "Office / District": "FL", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Republican Nominee", "Party": "Republican", "Office / District": "MA", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Republican Nominee", "Party": "Republican", "Office / District": "NH", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Republican Nominee", "Party": "Republican", "Office / District": "RI", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Democratic Nominee", "Party": "Democrat", "Office / District": "WY", "Chamber": "Senate", "Upcoming 2026 Primary": True},
        {"Name": "Democratic Nominee", "Party": "Democrat", "Office / District": "SC", "Chamber": "Senate", "Upcoming 2026 Primary": True},
    ]
    
    if df_candidates.empty:
        df_candidates = pd.DataFrame(hardcoded_challengers)
    else:
        existing_cands = set(df_candidates['Name'].dropna().str.lower())
        new_cands = [c for c in hardcoded_challengers if c['Name'].lower() not in existing_cands]
        df_candidates = pd.concat([df_candidates, pd.DataFrame(new_cands)], ignore_index=True)

    if df_current.empty and df_candidates.empty:
        print("Error: Grounding CSV files not found. Please ensure the data files are in this folder.")
        return
        
    unified_list = []
    
    def parse_age(val):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return "Unknown"
    
    def fmt_curr(val):
        try:
            val_f = float(val)
            if val_f == 0: return "N/A"
            return f"${val_f:,.2f}"
        except:
            return str(val) if pd.notna(val) else "N/A"
            
    def get_custom_status(name, current_status):
        overrides = {
            "Ashley Moody": "2026 special election for final two years of Marco Rubio's term",
            "Joni Ernst": "Incumbent not running for re-election in 2026.",
            "Gary Peters": "Incumbent not running for re-election in 2026.",
            "Tina Smith": "Incumbent not running for re-election in 2026.",
            "Steve Daines": "Incumbent not running for re-election in 2026.",
            "Thom Tillis": "Incumbent not running for re-election in 2026.",
            "Jeanne Shaheen": "Incumbent not running for re-election in 2026.",
            "Jon Husted": "2026 special election for final two years of JD Vance's term",
            "John Cornyn": "Incumbent defeated in primary for 2026 election.",
            "Tommy Tuberville": "Retiring to run for governor",
            "Dick Durbin": "Incumbent not running for re-election in 2026.",
            "Mitch McConnell": "Incumbent not running for re-election in 2026.",
            "Bill Cassidy": "Incumbent defeated in primary for 2026 election.",
            "Alan Armstrong": "Ineligible to run for a full term this year.",
            "Cynthia Lummis": "Incumbent not running for re-election in 2026."
        }
        for key, val in overrides.items():
            if key.lower() in str(name).lower():
                return val
        return current_status

    for idx, row in df_current.iterrows():
        bg_id = str(row.get('Bioguide ID')).strip() if pd.notna(row.get('Bioguide ID')) else f"CURR_{idx}"
        
        name = str(row.get('Name')).strip()
        name_parts = name.split()
        first_n = name_parts[0] if len(name_parts) > 0 else ""
        last_n = name_parts[-1] if len(name_parts) > 1 else ""
        wiki_name = f"{first_n}_{last_n}"
        
        # Exclude members replaced in our alternate timeline
        if name in ["Marco Rubio", "J.D. Vance", "Markwayne Mullin"]:
            continue
            
        photos = []
        if pd.notna(row.get('Bioguide ID')):
            bg_upper = bg_id.upper()
            bg_lower = bg_id.lower()
            first_letter = bg_upper[0] if bg_upper else 'A'
            photos = [
                f"https://www.congress.gov/img/member/{bg_lower}_200.jpg",
                f"https://theunitedstates.io/images/congress/450x550/{bg_upper}.jpg",
                f"https://theunitedstates.io/images/congress/225x275/{bg_upper}.jpg",
                f"https://bioguideretro.congress.gov/Static_Files/images/bioguide/{first_letter}/{bg_upper}.jpg",
                f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}.jpg",
                f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}_official_portrait.jpg"
            ]
        else:
            photos = [f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}.jpg", "placeholder"]
            
        chamber_str = str(row.get('Chamber')).strip()
        dist_val = row.get('District')
        dist_str = str(dist_val).strip() if pd.notna(dist_val) else "N/A"
        
        if "Senate" in chamber_str or dist_str.lower() == "unknown":
            dist_str = "N/A"
        
        term_start = str(row.get('Term Start')).strip() if pd.notna(row.get('Term Start')) else "N/A"
        term_end = str(row.get('Term End Date')).strip() if pd.notna(row.get('Term End Date')) else ""
        term_str = f"{term_start} - {term_end[:10]}" if term_end and term_end != "N/A" else term_start

        comm_val = row.get('Committee Assignments')
        comm_str = str(comm_val).strip() if pd.notna(comm_val) else "None"
        
        status_val = str(row.get('Status')).strip() if pd.notna(row.get('Status')) else "Active Member"
        status_val = get_custom_status(name, status_val)
        
        member_dict = {
            "id": bg_id,
            "name": name,
            "chamber": chamber_str,
            "party": str(row.get('Party')).strip(),
            "state": str(row.get('State')).strip(),
            "district": dist_str,
            "status": status_val,
            "term_start": term_str,
            "age": parse_age(row.get('Age')),
            "birthdate": str(row.get('Birthdate')).strip() if pd.notna(row.get('Birthdate')) else "Unknown",
            "education": str(row.get('Education')).strip() if pd.notna(row.get('Education')) else "N/A",
            "previous_professions": str(row.get('Previous Professions')).strip() if pd.notna(row.get('Previous Professions')) else "N/A",
            "receipts": fmt_curr(row.get('Total Receipts')),
            "disbursements": fmt_curr(row.get('Total Disbursements')),
            "funding_sources": str(row.get('Main Funding Sources')).strip() if pd.notna(row.get('Main Funding Sources')) else "N/A",
            "platforms": str(row.get('Policy Focus & Platforms')).strip() if pd.notna(row.get('Policy Focus & Platforms')) else "N/A",
            "voting_alignment": str(row.get('Projected/Historical Voting Alignment')).strip() if pd.notna(row.get('Projected/Historical Voting Alignment')) else "N/A",
            "committees": comm_str,
            "net_worth": str(row.get('Estimated Net Worth')).strip() if pd.notna(row.get('Estimated Net Worth')) else "N/A",
            "photos": photos,
            "photo_url": photos[0]
        }
        unified_list.append(member_dict)
        
    US_STATES = {
        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR', 'CALIFORNIA': 'CA',
        'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE', 'FLORIDA': 'FL', 'GEORGIA': 'GA',
        'HAWAII': 'HI', 'IDAHO': 'ID', 'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA',
        'KANSAS': 'KS', 'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
        'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS', 'MISSOURI': 'MO',
        'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ',
        'NEW MEXICO': 'NM', 'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH',
        'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
        'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT', 'VERMONT': 'VT',
        'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY',
        'DISTRICT OF COLUMBIA': 'DC', 'PUERTO RICO': 'PR', 'GUAM': 'GU', 
        'VIRGIN ISLANDS': 'VI', 'AMERICAN SAMOA': 'AS', 'NORTHERN MARIANA ISLANDS': 'MP'
    }

    def parse_state_abbrev(office_str):
        if not office_str or office_str == "N/A" or office_str.lower() == "unknown":
            return "N/A"
        office_upper = office_str.upper()
        for full_name, code in US_STATES.items():
            if full_name in office_upper:
                return code
        match = re.search(r'\b([A-Z]{2})(?:-\d+)?\b', office_upper)
        if match and match.group(1) in US_STATES.values():
            return match.group(1)
        return "N/A"

    for idx, row in df_candidates.iterrows():
        bg_id = f"CAND_{idx}"
        
        name = str(row.get('Name')).strip()
        name_parts = name.split()
        first_n = name_parts[0] if len(name_parts) > 0 else ""
        last_n = name_parts[-1] if len(name_parts) > 1 else ""
        wiki_name = f"{first_n}_{last_n}"
        
        candidate_photos = [
            f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}.jpg",
            f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}_portrait.jpg",
            "placeholder"
        ]
        
        chamber_str = str(row.get('Chamber')).strip()
        office_dist = str(row.get('Office / District')).strip() if pd.notna(row.get('Office / District')) else str(row.get('State')).strip()
        state_abbrev = parse_state_abbrev(office_dist)
            
        if "Senate" in chamber_str or office_dist.lower() == "unknown":
            office_dist = "N/A"
            
        status_val = str(row.get('Status')).strip() if pd.notna(row.get('Status')) else "Candidate"
        if row.get('Upcoming 2026 Primary') == True:
            status_val += " (Upcoming Primary)"

        candidate_dict = {
            "id": bg_id,
            "name": name,
            "chamber": chamber_str + " (Candidate)" if "Candidate" not in chamber_str else chamber_str,
            "party": str(row.get('Party')).strip(),
            "state": state_abbrev,
            "district": office_dist,
            "status": status_val,
            "term_start": str(row.get('Projected Start')).strip() if pd.notna(row.get('Projected Start')) else "N/A",
            "age": parse_age(row.get('Age')),
            "birthdate": str(row.get('Birthdate')).strip() if pd.notna(row.get('Birthdate')) else "Unknown",
            "education": str(row.get('Education')).strip() if pd.notna(row.get('Education')) else "N/A",
            "previous_professions": str(row.get('Previous Professions')).strip() if pd.notna(row.get('Previous Professions')) else "N/A",
            "receipts": fmt_curr(row.get('Campaign Receipts')),
            "disbursements": fmt_curr(row.get('Campaign Disbursements')),
            "funding_sources": str(row.get('Main Funding Sources')).strip() if pd.notna(row.get('Main Funding Sources')) else "N/A",
            "platforms": str(row.get('Core Campaigning Issues & Platform Focus')).strip() if pd.notna(row.get('Core Campaigning Issues & Platform Focus')) else "N/A",
            "voting_alignment": str(row.get('Projected/Historical Voting Alignment')).strip() if pd.notna(row.get('Projected/Historical Voting Alignment')) else "N/A",
            "committees": str(row.get('Historical Committee Assignments (If any)')).strip() if pd.notna(row.get('Historical Committee Assignments (If any)')) else "None",
            "net_worth": str(row.get('Estimated Net Worth')).strip() if pd.notna(row.get('Estimated Net Worth')) else "N/A",
            "photos": candidate_photos,
            "photo_url": candidate_photos[0]
        }
        unified_list.append(candidate_dict)
        
    print(f"Compiled {len(unified_list)} total unified profiles across clean datasets.")
    
    os.makedirs('candidate_profiles_site', exist_ok=True)
    
    index_file_path = 'candidate_profiles_site/index.html'
    map_file_path = 'candidate_profiles_site/map.html'

    shared_modal_body = """
    <!-- Candidate Immersive Profile Modal -->
    <div id="profileModal" class="hidden fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
        <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div class="fixed inset-0 bg-black bg-opacity-80 transition-opacity" onclick="closeModal()"></div>
            <span class="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div class="inline-block align-bottom bg-yt-bg rounded-xl text-left overflow-hidden shadow-2xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full border border-yt-borderHover">
                
                <div class="absolute top-4 right-4 z-10">
                    <button onclick="closeModal()" class="p-2 bg-yt-hover hover:bg-yt-border text-yt-textMuted hover:text-yt-text rounded-full transition-colors focus:outline-none">
                        <i data-lucide="x" class="w-5 h-5"></i>
                    </button>
                </div>

                <div id="modalHeader" class="relative overflow-hidden px-6 py-8 sm:p-10 border-b border-yt-border bg-yt-elevated">
                    <div class="flex flex-col sm:flex-row gap-6 items-center">
                        <div class="relative shrink-0">
                            <img id="modalPhoto" data-photo-idx="0" class="w-32 h-40 object-cover rounded-lg shadow-md border border-yt-border bg-yt-hover" src="" alt="Candidate Photo">
                            <span id="modalPartyBadge" class="absolute -bottom-2 -right-2 px-3 py-1 text-xs font-bold rounded-md text-yt-text shadow border border-opacity-20"></span>
                        </div>
                        <div class="text-center sm:text-left space-y-2">
                            <span id="modalChamberTag" class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold border"></span>
                            <h2 class="text-3xl font-bold text-yt-text" id="modalName"></h2>
                            <p class="text-sm font-medium text-yt-textMuted flex flex-wrap justify-center sm:justify-start gap-x-4 gap-y-1">
                                <span class="flex items-center"><i data-lucide="map-pin" class="w-4 h-4 mr-1"></i> Representing: <strong id="modalRegion" class="text-yt-text ml-1"></strong></span>
                                <span class="flex items-center"><i data-lucide="calendar" class="w-4 h-4 mr-1"></i> Term: <strong id="modalTerm" class="text-yt-text ml-1"></strong></span>
                            </p>
                        </div>
                    </div>
                </div>

                <div class="px-6 py-8 sm:p-10 grid grid-cols-1 md:grid-cols-2 gap-8 max-h-[60vh] overflow-y-auto custom-scrollbar bg-yt-bg">
                    <div class="space-y-6">
                        <div class="bg-yt-elevated p-5 rounded-xl border border-yt-border shadow-sm">
                            <h4 class="text-[11px] font-bold text-yt-textMuted uppercase tracking-wider mb-3 flex items-center"><i data-lucide="user" class="w-4 h-4 mr-1.5 text-[#3ea6ff]"></i> Biographical Info</h4>
                            <div class="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <span class="block text-xs font-semibold text-yt-textFaint">Age / Birthday</span>
                                    <span class="font-bold text-yt-text" id="modalAgeBirth"></span>
                                </div>
                                <div>
                                    <span class="block text-xs font-semibold text-yt-textFaint">Est. Net Worth</span>
                                    <span class="font-bold text-[#3ea6ff]" id="modalNetWorth"></span>
                                </div>
                                <div class="col-span-2">
                                    <span class="block text-xs font-semibold text-yt-textFaint">Education</span>
                                    <span class="font-medium text-yt-textMuted" id="modalEducation"></span>
                                </div>
                                <div class="col-span-2">
                                    <span class="block text-xs font-semibold text-yt-textFaint">Previous Careers</span>
                                    <span class="font-medium text-yt-textMuted" id="modalProfessions"></span>
                                </div>
                            </div>
                        </div>

                        <div class="p-5 rounded-xl border border-[#3ea6ff]/30 bg-[#3ea6ff]/5 shadow-sm">
                            <h4 class="text-[11px] font-bold text-[#3ea6ff] uppercase tracking-wider mb-3 flex items-center"><i data-lucide="scroll" class="w-4 h-4 mr-1.5"></i> Platform & Priorities</h4>
                            <div class="text-sm font-normal text-yt-textMuted leading-relaxed custom-scrollbar max-h-48 overflow-y-auto pr-2" id="modalPlatform">
                            </div>
                        </div>
                    </div>

                    <div class="space-y-6">
                        <div class="bg-yt-elevated p-5 rounded-xl border border-yt-border shadow-sm">
                            <h4 class="text-[11px] font-bold text-yt-textMuted uppercase tracking-wider mb-3 flex items-center"><i data-lucide="dollar-sign" class="w-4 h-4 mr-1.5 text-[#2ba640]"></i> FEC Campaign Finance</h4>
                            <div class="grid grid-cols-2 gap-4 text-sm mb-4">
                                <div class="bg-yt-input p-3 rounded-lg border border-yt-border text-center">
                                    <span class="block text-[10px] font-bold text-yt-textFaint uppercase tracking-wider">Total Raised</span>
                                    <span class="font-bold text-[#2ba640] text-sm mt-0.5 block" id="modalReceipts"></span>
                                </div>
                                <div class="bg-yt-input p-3 rounded-lg border border-yt-border text-center">
                                    <span class="block text-[10px] font-bold text-yt-textFaint uppercase tracking-wider">Disbursements</span>
                                    <span class="font-bold text-[#ff4e45] text-sm mt-0.5 block" id="modalDisbursements"></span>
                                </div>
                            </div>
                            <div>
                                <span class="block text-[10px] font-bold text-yt-textFaint uppercase tracking-wider mb-1.5">Main Funding Sources</span>
                                <p class="text-xs font-medium text-yt-textMuted bg-yt-input p-3 rounded-lg border border-yt-border shadow-sm leading-relaxed max-h-32 overflow-y-auto custom-scrollbar" id="modalFunding"></p>
                            </div>
                        </div>

                        <div class="bg-yt-elevated p-5 rounded-xl border border-yt-border shadow-sm">
                            <div class="mb-4">
                                <h4 class="text-[11px] font-bold text-yt-textMuted uppercase tracking-wider mb-2 flex items-center"><i data-lucide="bar-chart-2" class="w-4 h-4 mr-1.5 text-[#3ea6ff]"></i> Voting Alignment</h4>
                                <div class="bg-yt-input p-4 rounded-xl border border-yt-border shadow-sm w-full" id="modalVoting"></div>
                            </div>
                            <div>
                                <h4 class="text-[11px] font-bold text-yt-textMuted uppercase tracking-wider mb-2 flex items-center"><i data-lucide="layers" class="w-4 h-4 mr-1.5 text-[#3ea6ff]"></i> Committee Assignments</h4>
                                <div class="text-xs font-medium text-yt-textMuted bg-yt-input p-3 rounded-lg border border-yt-border shadow-sm max-h-40 overflow-y-auto custom-scrollbar leading-relaxed" id="modalCommittees"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bg-yt-elevated px-6 py-4 sm:px-10 flex justify-end border-t border-yt-border">
                    <button type="button" onclick="closeModal()" class="w-full sm:w-auto inline-flex justify-center rounded-lg border border-yt-borderHover shadow-sm px-4 py-2 bg-yt-hover text-sm font-medium text-yt-text hover:bg-yt-border focus:outline-none">
                        Close Profile
                    </button>
                </div>
            </div>
        </div>
    </div>
    """

    shared_modal_js_handlers = """
        // Explicitly hardcode the exact 35 Class II and Special Election Defenders for bulletproof math
        const senateDefenders26 = {
            'AK': 'Sullivan', 'AL': 'Tuberville', 'AR': 'Cotton', 'CO': 'Hickenlooper',
            'DE': 'Coons', 'FL': 'Moody', 'GA': 'Ossoff', 'IA': 'Ernst', 'ID': 'Risch',
            'IL': 'Durbin', 'KS': 'Marshall', 'KY': 'McConnell', 'LA': 'Cassidy',
            'MA': 'Markey', 'ME': 'Collins', 'MI': 'Peters', 'MN': 'Smith', 'MS': 'Hyde-Smith',
            'MT': 'Daines', 'NC': 'Tillis', 'NE': 'Ricketts', 'NH': 'Shaheen', 'NJ': 'Booker',
            'NM': 'Lujan', 'OH': 'Husted', 'OK': 'Armstrong', 'OR': 'Merkley', 'RI': 'Reed',
            'SC': 'Graham', 'SD': 'Rounds', 'TN': 'Hagerty', 'TX': 'Cornyn', 'VA': 'Warner',
            'WV': 'Capito', 'WY': 'Lummis'
        };

        legislatorsData.forEach(item => {
            item.isUpIn2026 = false;
            item.isCandidate = item.chamber.includes('Candidate') || (item.status && item.status.toLowerCase().includes('candidate'));
            
            const lowerStatus = item.status ? item.status.toLowerCase() : '';
            const isLeaving = lowerStatus.includes('retiring') || lowerStatus.includes('not running') || lowerStatus.includes('defeated') || lowerStatus.includes('ineligible');
            
            if (item.chamber.includes('Senate') && !item.isCandidate) {
                const defenderName = senateDefenders26[item.state];
                const normalizedItemName = item.name.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
                
                if (defenderName && normalizedItemName.includes(defenderName)) {
                    item.isUpIn2026 = true;
                    item.termEndYear = 2027;
                    item.electionYear = 2026;
                    // Forcefully correct invalid CSV appointment dates
                    if (item.term_start) {
                        item.term_start = item.term_start.split(' - ')[0] + ' - 2027-01-03';
                    }
                } else if (item.term_start && item.term_start !== 'N/A') {
                    const startYear = parseInt(item.term_start.substring(0, 4));
                    if (!isNaN(startYear)) {
                        let nextEnd = startYear + 6;
                        while(nextEnd < 2027) nextEnd += 6;
                        if (nextEnd % 2 === 0) nextEnd += 1;
                        item.termEndYear = nextEnd;
                        item.electionYear = nextEnd - 1;
                        // Format the term date for the modal nicely
                        item.term_start = item.term_start.split(' - ')[0] + ' - ' + nextEnd + '-01-03';
                    }
                }
            } else if (item.chamber.includes('House') && !item.isCandidate) {
                item.termEndYear = 2027;
                item.electionYear = 2026;
                if (isLeaving) {
                    item.isUpIn2026 = true;
                }
                if (item.term_start) {
                    item.term_start = item.term_start.split(' - ')[0] + ' - 2027-01-03';
                }
            }
        });

        function updateElectionWatchBadge() {
            const senateUp = legislatorsData.filter(i => i.isUpIn2026 && i.chamber.includes('Senate') && !i.isCandidate);
            const dUp = senateUp.filter(i => i.party.includes('Democrat') || i.party === 'Independent').length;
            const rUp = senateUp.filter(i => i.party === 'Republican').length;
            
            const territories = ['AS', 'DC', 'GU', 'MP', 'PR', 'VI'];
            const votingHouseMembers = legislatorsData.filter(i => i.chamber === 'House' && !territories.includes(i.state));

            const hR = votingHouseMembers.filter(i => i.party === 'Republican').length;
            const hD = votingHouseMembers.filter(i => i.party.includes('Democrat') || i.party === 'Democratic-Farmer Labor').length;
            const hI = votingHouseMembers.filter(i => i.party !== 'Republican' && !i.party.includes('Democrat') && i.party !== 'Vacant' && i.party !== 'Democratic-Farmer Labor').length;
            const hV = votingHouseMembers.filter(i => i.party === 'Vacant' || i.status === 'Vacant').length;

            const hStats = document.getElementById('navHouseStats');
            if (hStats) {
                let vStr = hV > 0 ? `<span class="text-yt-textFaint font-normal mx-1.5">|</span> <span class="inline-flex items-center font-bold text-yt-text mr-1.5">${hV} Vacant</span>` : '';
                let iStr = hI > 0 ? `<span class="text-yt-textFaint font-normal mx-1.5">|</span> <span class="inline-flex items-center font-bold text-[#ffb000] mr-1.5">${hI} Ind</span>` : '';
                hStats.innerHTML = `<span class="font-bold text-yt-text mr-2 flex items-center"><i data-lucide="columns" class="w-3.5 h-3.5 mr-1 text-yt-textMuted"></i> HOUSE:</span>
                        <span class="inline-flex items-center font-bold text-[#ff4e45] mr-1.5">${hR} R</span>
                        <span class="text-yt-textFaint font-normal mx-1.5">|</span>
                        <span class="inline-flex items-center font-bold text-[#3ea6ff] mr-1.5">${hD} D</span>
                        ${iStr}
                        ${vStr}`;
            }

            const sStats = document.getElementById('sidebarHouseStats');
            if (sStats) {
                let vStr = hV > 0 ? ` <span class="text-yt-textFaint font-normal mx-1">|</span> <span class="text-yt-text">${hV} Vacant</span>` : '';
                let iStr = hI > 0 ? ` <span class="text-yt-textFaint font-normal mx-1">|</span> <span class="text-[#ffb000]">${hI} I</span>` : '';
                sStats.innerHTML = `<span class="text-[#ff4e45]">${hR} R</span> <span class="text-yt-textFaint font-normal mx-1">|</span> <span class="text-[#3ea6ff]">${hD} D</span>${iStr}${vStr}`;
            }
            
            const senDef = document.getElementById('senateDefendingCount');
            if(senDef) {
                senDef.innerHTML = `<span class="text-[#3ea6ff]">${dUp} D</span> / <span class="text-[#ff4e45]">${rUp} R</span>`;
            }
        }

        const defaultSilhouette = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' fill='%23aaaaaa' style='background-color:transparent'%3E%3Ccircle cx='50' cy='35' r='20'/%3E%3Cpath d='M20,80 C20,55 80,55 80,80 Z'/%3E%3C/svg%3E";

        window.handleImageFallback = function(img, profileId) {
            const item = legislatorsData.find(x => x.id === profileId);
            if (!item || !item.photos || item.photos.length === 0) {
                img.onerror = null;
                img.src = defaultSilhouette;
                return;
            }
            
            let currentIdx = parseInt(img.dataset.photoIdx || "0");
            currentIdx++;
            
            if (currentIdx < item.photos.length) {
                img.dataset.photoIdx = currentIdx;
                let nextUrl = item.photos[currentIdx];
                if (nextUrl === "placeholder") {
                    img.onerror = null;
                    img.src = defaultSilhouette;
                } else {
                    img.src = nextUrl;
                }
            } else {
                img.onerror = null;
                img.src = defaultSilhouette;
            }
        };

        function openProfile(id) {
            const item = legislatorsData.find(x => x.id === id);
            if (!item) return;

            document.getElementById('modalName').textContent = item.name;
            
            let officeLabel = item.chamber;
            if (item.chamber.includes('House')) {
                let dist = (item.district && item.district !== 'N/A' && item.district !== 'nan') ? item.district : '';
                if (dist.toLowerCase() === 'at-large' || dist === '0') dist = 'AL';
                officeLabel = dist ? `House • ${item.state}-${dist}` : `House • ${item.state}`;
            } else if (item.chamber.includes('Senate')) {
                officeLabel = `Senate • ${item.state}`;
            }
            
            document.getElementById('modalRegion').textContent = officeLabel;
            document.getElementById('modalTerm').textContent = item.term_start;
            
            const chamberTag = document.getElementById('modalChamberTag');
            chamberTag.textContent = item.chamber;
            if (item.chamber.includes('Senate')) {
                chamberTag.className = "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-[#3ea6ff]/10 text-[#3ea6ff] border border-[#3ea6ff]/30";
            } else {
                chamberTag.className = "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-yt-hover text-yt-textMuted border border-yt-border";
            }

            const partyBadge = document.getElementById('modalPartyBadge');
            partyBadge.textContent = item.party;
            if (item.party === 'Democrat' || item.party === 'Democratic' || item.party === 'Democratic-Farmer Labor') {
                partyBadge.className = "absolute -bottom-2 -right-2 px-3 py-1 text-xs font-bold rounded-md text-[#ffffff] bg-[#3ea6ff] shadow border border-opacity-20";
            } else if (item.party === 'Republican') {
                partyBadge.className = "absolute -bottom-2 -right-2 px-3 py-1 text-xs font-bold rounded-md text-[#ffffff] bg-[#ff4e45] shadow border border-opacity-20";
            } else if (item.party === 'Vacant' || item.status === 'Vacant') {
                partyBadge.className = "absolute -bottom-2 -right-2 px-3 py-1 text-xs font-bold rounded-md text-yt-inverse bg-yt-text shadow border border-opacity-20";
            } else {
                partyBadge.className = "absolute -bottom-2 -right-2 px-3 py-1 text-xs font-bold rounded-md text-[#ffffff] bg-[#ffb000] shadow border border-opacity-20";
            }

            const photoImg = document.getElementById('modalPhoto');
            photoImg.dataset.photoIdx = "0"; 
            
            if (item.photos && item.photos.length > 0 && item.photos[0] !== 'placeholder') {
                photoImg.src = item.photos[0];
                photoImg.onerror = function() {
                    window.handleImageFallback(this, item.id);
                };
            } else {
                photoImg.onerror = null;
                photoImg.src = defaultSilhouette;
            }

            document.getElementById('modalAgeBirth').textContent = `${item.age} years old (${item.birthdate})`;
            document.getElementById('modalNetWorth').textContent = item.net_worth;
            document.getElementById('modalEducation').textContent = item.education;
            document.getElementById('modalProfessions').textContent = item.previous_professions;

            const platformDiv = document.getElementById('modalPlatform');
            platformDiv.innerHTML = '';
            
            let cleanPlatforms = item.platforms;
            if (cleanPlatforms.startsWith('[') && cleanPlatforms.endsWith(']')) {
                try {
                    const arr = JSON.parse(cleanPlatforms.replace(/'/g, '"'));
                    if (Array.isArray(arr)) {
                        platformDiv.innerHTML = `<ul class="list-disc pl-4 space-y-2">` + arr.map(x => `<li>${x}</li>`).join('') + `</ul>`;
                        cleanPlatforms = '';
                    }
                } catch {}
            }
            if (cleanPlatforms) {
                const bullets = cleanPlatforms.split(', ');
                if (bullets.length > 1) {
                    platformDiv.innerHTML = `<ul class="list-disc pl-4 space-y-2">` + bullets.map(x => `<li>${x}</li>`).join('') + `</ul>`;
                } else {
                    platformDiv.innerHTML = `<p>${cleanPlatforms}</p>`;
                }
            }

            document.getElementById('modalReceipts').textContent = item.receipts;
            document.getElementById('modalDisbursements').textContent = item.disbursements;
            document.getElementById('modalFunding').textContent = item.funding_sources;
            
            const votingDiv = document.getElementById('modalVoting');
            const alignmentText = item.voting_alignment || "N/A";
            
            const match = alignmentText.match(/DW-NOMINATE:\s*([+-]?\d+\.?\d*)/i);
            
            if (match) {
                const score = parseFloat(match[1]);
                let pct = ((score + 1.0) / 2.0) * 100;
                pct = Math.max(0, Math.min(100, pct));
                
                const labelMatch = alignmentText.match(/\(([^)]+)\)/);
                const label = labelMatch ? labelMatch[1] : '';
                
                const loyaltyMatch = alignmentText.match(/•\s*(.*)/);
                const loyalty = loyaltyMatch ? loyaltyMatch[1].trim() : '';

                let scoreColor = "text-[#3ea6ff]";
                if (score <= -0.1) scoreColor = "text-[#3ea6ff]";
                else if (score >= 0.1) scoreColor = "text-[#ff4e45]";
                else scoreColor = "text-[#a855f7]";

                const signStr = score > 0 ? "+" + score.toFixed(2) : score.toFixed(2);

                votingDiv.innerHTML = `
                    <div class="space-y-3 w-full">
                        <div class="flex justify-between items-center text-xs w-full">
                            <span class="font-bold text-yt-text text-sm">
                                <span class="${scoreColor}">${signStr}</span>
                                ${label ? `<span class="text-yt-textMuted font-medium ml-1">(${label})</span>` : ''}
                            </span>
                            ${loyalty ? `<span class="text-[10px] font-bold text-yt-textMuted bg-yt-bg px-2 py-1 rounded border border-yt-borderHover whitespace-nowrap ml-2">${loyalty}</span>` : ''}
                        </div>
                        <div class="relative w-full pt-1 pb-1">
                            <div class="w-full h-2 rounded-full bg-gradient-to-r from-[#3ea6ff] via-[#a855f7] to-[#ff4e45] shadow-inner relative border border-yt-border">
                                <div class="absolute -top-1 w-2 h-4 bg-yt-text border border-yt-inverse rounded-sm shadow-md transition-all -ml-1 transform z-10" style="left: ${pct}%;"></div>
                            </div>
                            <div class="flex justify-between text-[9px] font-bold uppercase text-yt-textFaint mt-2">
                                <span class="text-[#3ea6ff]/80 tracking-wider">-1.0 (Prog)</span>
                                <span class="text-yt-textFaint tracking-wider text-center">Moderate</span>
                                <span class="text-[#ff4e45]/80 tracking-wider">+1.0 (Cons)</span>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                votingDiv.innerHTML = `<span class="text-sm font-normal text-yt-textMuted leading-relaxed">${alignmentText}</span>`;
            }
            
            const comms = item.committees.split('; ');
            document.getElementById('modalCommittees').innerHTML = comms.map(c => `
                <div class="py-1.5 border-b border-yt-border last:border-0 flex items-start">
                    <span class="w-1 h-1 mt-2 bg-[#3ea6ff] rounded-full shrink-0 mr-2"></span>
                    <span>${c}</span>
                </div>
            `).join('');

            const modal = document.getElementById('profileModal');
            modal.classList.remove('hidden');
            document.body.classList.add('overflow-hidden');
            lucide.createIcons();
        }

        function closeModal() {
            document.getElementById('profileModal').classList.add('hidden');
            document.body.classList.remove('overflow-hidden');
        }
        
        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('ytTheme', theme);
            if(typeof updateMapVisuals === 'function') updateMapVisuals();
        }
    """

    index_html_template = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Know Your Candidate</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&family=Roboto+Slab:wght@700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            darkMode: ['class', '[data-theme="amoled"]'],
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Roboto', 'sans-serif'],
                        slab: ['Roboto Slab', 'serif']
                    },
                    colors: {
                        yt: {
                            bg: 'var(--bg-main)',
                            elevated: 'var(--bg-elevated)',
                            input: 'var(--bg-input)',
                            hover: 'var(--bg-hover)',
                            border: 'var(--border-main)',
                            borderHover: 'var(--border-hover)',
                            text: 'var(--text-main)',
                            textMuted: 'var(--text-muted)',
                            textFaint: 'var(--text-faint)',
                            inverse: 'var(--text-inverse)'
                        }
                    }
                }
            }
        }
    </script>
    <style>
        :root {
            --bg-main: #0f0f0f;
            --bg-elevated: #181818;
            --bg-input: #121212;
            --bg-hover: #272727;
            --border-main: #303030;
            --border-hover: #3f3f3f;
            --text-main: #f1f1f1;
            --text-muted: #aaaaaa;
            --text-faint: #717171;
            --text-inverse: #0f0f0f;
        }
        [data-theme="amoled"] {
            --bg-main: #000000;
            --bg-elevated: #0a0a0a;
            --bg-input: #050505;
            --bg-hover: #1a1a1a;
            --border-main: #222222;
            --border-hover: #333333;
            --text-main: #ffffff;
            --text-muted: #888888;
            --text-faint: #555555;
            --text-inverse: #000000;
        }
        [data-theme="light"] {
            --bg-main: #f9f9f9;
            --bg-elevated: #ffffff;
            --bg-input: #f0f0f0;
            --bg-hover: #e5e5e5;
            --border-main: #cccccc;
            --border-hover: #aaaaaa;
            --text-main: #0f0f0f;
            --text-muted: #606060;
            --text-faint: #909090;
            --text-inverse: #ffffff;
        }
        body { font-family: 'Roboto', sans-serif; background-color: var(--bg-main); color: var(--text-main); }
        .custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: var(--text-faint); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
        .chip { background-color: var(--bg-hover); color: var(--text-main); padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; white-space: nowrap; cursor: pointer; transition: all 0.2s; border: none; }
        .chip:hover:not(.active) { background-color: var(--border-hover); }
        .chip.active { background-color: var(--text-main); color: var(--text-inverse); font-weight: 500; }
    </style>
    <script>
        (function() {
            const saved = localStorage.getItem('ytTheme') || 'dark';
            document.documentElement.setAttribute('data-theme', saved);
        })();
    </script>
</head>
<body class="h-full flex flex-col antialiased overflow-hidden">
    
    <header class="h-14 flex-shrink-0 flex items-center justify-between px-6 border-b border-yt-border bg-yt-bg z-40">
        <div class="flex items-center space-x-6">
            <div class="flex items-center text-yt-text">
                <i data-lucide="vote" class="w-6 h-6 mr-3 text-[#3ea6ff]"></i>
                <h1 class="text-xl font-bold tracking-tight font-slab">KYC Directory</h1>
            </div>
        </div>
        
        <div class="flex-1 flex justify-center max-w-2xl mx-auto px-4">
            <div class="flex w-full">
                <div class="flex-1 border border-yt-border bg-yt-input rounded-l-full flex items-center px-4 overflow-hidden focus-within:border-[#1c62b9]">
                    <i data-lucide="search" class="w-4 h-4 text-yt-textMuted hidden sm:block mr-2"></i>
                    <input type="text" id="searchInput" onkeyup="filterData()" placeholder="Search profiles, states, or parties..." 
                           class="w-full bg-transparent border-none outline-none text-yt-text text-sm py-2">
                </div>
                <button class="px-5 border border-l-0 border-yt-border bg-yt-hover rounded-r-full hover:bg-yt-border transition-colors flex items-center justify-center">
                    <i data-lucide="search" class="w-4 h-4 text-yt-text"></i>
                </button>
            </div>
        </div>
        
        <div class="flex items-center space-x-2 w-auto justify-end">
            <div class="relative group mr-2">
                <button class="p-2 text-yt-textMuted hover:text-yt-text hover:bg-yt-hover rounded-full transition-colors flex items-center">
                    <i data-lucide="sun-moon" class="w-5 h-5"></i>
                </button>
                <div class="absolute right-0 mt-2 w-40 bg-yt-elevated border border-yt-border rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                    <button onclick="setTheme('dark')" class="w-full text-left px-4 py-2 text-sm text-yt-text hover:bg-yt-hover rounded-t-lg">Dark Theme</button>
                    <button onclick="setTheme('amoled')" class="w-full text-left px-4 py-2 text-sm text-yt-text hover:bg-yt-hover">AMOLED Dark</button>
                    <button onclick="setTheme('light')" class="w-full text-left px-4 py-2 text-sm text-yt-text hover:bg-yt-hover rounded-b-lg">Light Theme</button>
                </div>
            </div>
            <select id="sortBy" onchange="sortAndRender()" class="hidden sm:block bg-transparent text-yt-textMuted font-medium text-sm outline-none cursor-pointer py-1.5 px-2 hover:text-yt-text rounded border border-transparent hover:border-yt-border">
                <option value="state-district" class="bg-yt-input">Sort: Region</option>
                <option value="senate-26" class="bg-yt-input">2026 Senate Races</option>
                <option value="name" class="bg-yt-input">Sort: Name</option>
                <option value="age-desc" class="bg-yt-input">Sort: Oldest</option>
                <option value="age-asc" class="bg-yt-input">Sort: Youngest</option>
            </select>
        </div>
    </header>

    <div class="flex flex-1 overflow-hidden">
        
        <aside class="w-60 flex-shrink-0 border-r border-yt-border bg-yt-bg flex flex-col h-full overflow-y-auto custom-scrollbar">
            <div class="p-3">
                <a href="index.html" class="flex items-center px-3 py-2.5 rounded-lg bg-yt-hover text-yt-text font-medium text-sm">
                    <i data-lucide="layout-grid" class="w-5 h-5 mr-4 text-yt-textMuted"></i> Profile Grid
                </a>
                <a href="map.html" class="flex items-center px-3 py-2.5 rounded-lg text-yt-text hover:bg-yt-hover font-medium text-sm mt-1 transition-colors">
                    <i data-lucide="map" class="w-5 h-5 mr-4 text-yt-textMuted"></i> Partisan Map
                </a>
            </div>
            
            <hr class="border-yt-border my-2 mx-4">
            
            <div class="px-4 py-2">
                <h3 class="text-xs font-bold text-yt-textMuted uppercase tracking-wider mb-3">119th Congress</h3>
                <div class="text-xs font-bold text-yt-textMuted mb-1">SENATE</div>
                <div class="text-sm font-bold text-yt-text mb-4"><span class="text-[#ff4e45]">53 R</span> <span class="text-yt-textFaint mx-1">|</span> <span class="text-[#3ea6ff]">47 D/I</span></div>
                
                <div class="text-xs font-bold text-yt-textMuted mb-1">HOUSE</div>
                <div class="text-sm font-bold text-yt-text mb-4" id="sidebarHouseStats"><span class="text-yt-textFaint">Loading...</span></div>
            </div>

            <hr class="border-yt-border my-2 mx-4">
            
            <div class="px-4 py-2">
                <h3 class="text-xs font-bold text-yt-text flex items-center mb-3"><i data-lucide="flag" class="w-3.5 h-3.5 mr-2 text-[#ffb000]"></i> 2026 Elections</h3>
                
                <div class="flex justify-between text-xs mb-1.5 text-yt-textMuted"><span class="font-medium">Senate Seats Up</span><span class="font-bold text-yt-text">35</span></div>
                <div class="flex justify-between text-xs mb-4 text-yt-textMuted"><span class="font-medium">Defending</span><span class="font-bold" id="senateDefendingCount"><span class="text-yt-textFaint">Loading...</span></span></div>
                
                <div class="flex justify-between text-xs mb-1 text-yt-textMuted"><span class="font-medium">House Seats Up</span><span class="font-bold text-yt-text">435</span></div>
                <div class="text-[10px] text-yt-textFaint">(All 2-Year Terms)</div>
            </div>

            <hr class="border-yt-border my-2 mx-4 mt-auto">
            
            <div class="p-4">
                <h3 class="text-xs font-bold text-yt-textMuted uppercase tracking-wider mb-2">Filter by State</h3>
                <select id="stateSelect" onchange="filterData()" class="w-full bg-yt-input border border-yt-border text-yt-text font-medium text-sm rounded-lg px-2 py-1.5 outline-none focus:border-[#3ea6ff] appearance-none">
                    <option value="all">All States & Territories</option>
                </select>
            </div>
        </aside>

        <main class="flex-1 flex flex-col h-full bg-yt-bg relative overflow-hidden">
            
            <div class="h-14 flex-shrink-0 flex items-center px-6 border-b border-yt-border gap-3 overflow-x-auto custom-scrollbar">
                <button class="chip active" data-filter="all" onclick="setFilter(this, 'chamber')">All</button>
                <button class="chip" data-filter="Senate" onclick="setFilter(this, 'chamber')">Senate</button>
                <button class="chip" data-filter="House" onclick="setFilter(this, 'chamber')">House</button>
                <div class="w-px h-6 bg-yt-border mx-1"></div>
                <button class="chip" data-filter="Democrat" onclick="setFilter(this, 'party')">Democrat</button>
                <button class="chip" data-filter="Republican" onclick="setFilter(this, 'party')">Republican</button>
                <div class="w-px h-6 bg-yt-border mx-1"></div>
                <button class="chip" data-filter="upIn26" onclick="setFilter(this, 'election')">Up for Re-Election '26</button>
                <button class="chip" data-filter="Candidate" onclick="setFilter(this, 'election')">2026 Challengers</button>
            </div>

            <div class="flex-1 overflow-y-auto custom-scrollbar p-6">
                <p class="text-sm text-yt-textMuted mb-4 font-medium" id="resultsLabel">Showing all profiles</p>
                
                <div id="cardsGrid" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-8 gap-x-4 gap-y-8"></div>
                
                <div id="noResults" class="hidden flex-col items-center justify-center h-64 text-center mt-10">
                    <i data-lucide="search-x" class="w-16 h-16 text-yt-border mb-4"></i>
                    <h3 class="text-xl font-bold text-yt-text">No profiles found</h3>
                    <p class="text-yt-textMuted mt-2 text-sm font-medium">Try adjusting your search or filters to find what you're looking for.</p>
                </div>
            </div>
        </main>
    </div>

    __MODAL_BODY_REPLACE__

    <script>
        const legislatorsData = __LEGISLATORS_DATA_REPLACE__;
        let activeChamber = 'all', activeParty = 'all', activeState = 'all', activeElection = 'all', searchQuery = '';

        window.addEventListener('DOMContentLoaded', () => {
            updateElectionWatchBadge();
            initializeStateFilter();
            filterData();
        });

        function initializeStateFilter() {
            const stateSelect = document.getElementById('stateSelect');
            const states = [...new Set(legislatorsData.map(item => item.state))].sort();
            states.forEach(state => {
                if(state && state !== 'N/A' && state !== 'nan') {
                    const opt = document.createElement('option');
                    opt.value = state;
                    opt.textContent = state;
                    stateSelect.appendChild(opt);
                }
            });
        }

        window.setFilter = function(element, type) {
            if(type === 'chamber') {
                document.querySelectorAll('button[data-filter="all"][onclick*="chamber"], button[data-filter="Senate"], button[data-filter="House"]').forEach(b => {
                    b.classList.remove('active');
                });
                activeChamber = element.dataset.filter;
            } else if (type === 'party') {
                if(element.classList.contains('active')) {
                    element.classList.remove('active');
                    activeParty = 'all';
                } else {
                    document.querySelectorAll('button[data-filter="Democrat"], button[data-filter="Republican"]').forEach(b => {
                        b.classList.remove('active');
                    });
                    activeParty = element.dataset.filter;
                }
            } else if (type === 'election') {
                if(element.classList.contains('active')) {
                    element.classList.remove('active');
                    activeElection = 'all';
                } else {
                    document.querySelectorAll('button[data-filter="upIn26"], button[data-filter="Candidate"]').forEach(b => {
                        b.classList.remove('active');
                    });
                    activeElection = element.dataset.filter;
                }
            }
            
            if (type === 'chamber' || (type !== 'chamber' && activeParty !== 'all' && element.dataset.filter === activeParty) || (type !== 'chamber' && activeElection !== 'all' && element.dataset.filter === activeElection)) {
                 element.classList.add('active');
            }

            filterData();
        }

        function filterData() {
            searchQuery = document.getElementById('searchInput').value.toLowerCase().trim();
            activeState = document.getElementById('stateSelect').value;

            const filtered = legislatorsData.filter(item => {
                const searchMatch = !searchQuery || item.name.toLowerCase().includes(searchQuery) || item.state.toLowerCase().includes(searchQuery) || item.party.toLowerCase().includes(searchQuery) || item.district.toLowerCase().includes(searchQuery);
                
                let chamberMatch = true;
                if (activeChamber === 'Senate') chamberMatch = item.chamber.includes('Senate');
                else if (activeChamber === 'House') chamberMatch = item.chamber.includes('House');

                let partyMatch = true;
                if (activeParty === 'Democrat') partyMatch = item.party === 'Democrat' || item.party === 'Democratic' || item.party === 'Democratic-Farmer Labor';
                else if (activeParty === 'Republican') partyMatch = item.party === 'Republican';

                const stateMatch = activeState === 'all' || item.state === activeState;
                
                let electionMatch = true;
                if (activeElection === 'upIn26') {
                    electionMatch = item.isUpIn2026 && !item.isCandidate;
                } else if (activeElection === 'Candidate') {
                    electionMatch = item.isCandidate;
                }
                
                return searchMatch && chamberMatch && partyMatch && stateMatch && electionMatch;
            });

            document.getElementById('resultsLabel').textContent = `Showing ${filtered.length} profiles`;
            window.filteredData = filtered;
            sortAndRender();
        }

        function sortAndRender() {
            const sortBy = document.getElementById('sortBy').value;
            const data = window.filteredData || [];
            const cardsGrid = document.getElementById('cardsGrid');
            const noResults = document.getElementById('noResults');

            if (data.length === 0) {
                cardsGrid.innerHTML = '';
                noResults.classList.remove('hidden');
                return;
            } else {
                noResults.classList.add('hidden');
            }

            data.sort((a, b) => {
                if (sortBy === 'name') return a.name.localeCompare(b.name);
                else if (sortBy === 'age-desc') return (typeof b.age === 'number' ? b.age : 0) - (typeof a.age === 'number' ? a.age : 0);
                else if (sortBy === 'age-asc') return (typeof a.age === 'number' ? a.age : 999) - (typeof b.age === 'number' ? b.age : 999);
                else if (sortBy === 'senate-26') {
                    const aUp = (a.chamber.includes('Senate') && (a.isUpIn2026 || a.isCandidate)) ? 0 : 1;
                    const bUp = (b.chamber.includes('Senate') && (b.isUpIn2026 || b.isCandidate)) ? 0 : 1;
                    if (aUp !== bUp) return aUp - bUp;
                    const stateComp = a.state.localeCompare(b.state);
                    if (stateComp !== 0) return stateComp;
                    const aCand = a.isCandidate ? 1 : 0;
                    const bCand = b.isCandidate ? 1 : 0;
                    return aCand - bCand;
                }
                else {
                    const isA_Sen = a.chamber.includes('Senate') ? 1 : 2;
                    const isB_Sen = b.chamber.includes('Senate') ? 1 : 2;
                    if (isA_Sen !== isB_Sen) return isA_Sen - isB_Sen;
                    const stateComp = a.state.localeCompare(b.state);
                    if (stateComp !== 0) return stateComp;
                    return parseDistrictNum(a.district) - parseDistrictNum(b.district);
                }
            });

            cardsGrid.innerHTML = data.map(item => {
                let partyColor = item.party.includes('Democrat') ? 'text-[#3ea6ff]' : (item.party === 'Republican' ? 'text-[#ff4e45]' : 'text-[#ffb000]');
                if (item.party === 'Vacant' || item.status === 'Vacant') partyColor = 'text-yt-text';
                
                let imgSrc = item.photos && item.photos.length > 0 ? item.photos[0] : 'placeholder';
                if (imgSrc === 'placeholder') imgSrc = defaultSilhouette;
                
                let officeLabel = item.chamber;
                if (item.chamber.includes('House')) {
                    let dist = (item.district && item.district !== 'N/A' && item.district !== 'nan') ? item.district : '';
                    if (dist.toLowerCase() === 'at-large' || dist === '0') dist = 'AL';
                    officeLabel = dist ? `House • ${item.state}-${dist}` : `House • ${item.state}`;
                } else if (item.chamber.includes('Senate')) {
                    officeLabel = `Senate • ${item.state}`;
                }
                
                let customStatusBadge = "";
                const lowerStatus = item.status ? item.status.toLowerCase() : '';
                const isLeaving = lowerStatus.includes('retiring') || lowerStatus.includes('not running') || lowerStatus.includes('defeated') || lowerStatus.includes('ineligible');

                if (isLeaving) {
                    customStatusBadge = `<span class="bg-[#ff4e45]/10 text-[#ff4e45] px-1.5 py-0.5 rounded text-[10px] font-bold w-fit mt-1">Leaving '26</span>`;
                } else if (item.chamber.includes('Senate') && item.isUpIn2026 && !item.isCandidate) {
                    customStatusBadge = `<span class="bg-[#ffb000]/10 text-[#ffb000] px-1.5 py-0.5 rounded text-[10px] font-bold w-fit mt-1">Seat Up '26</span>`;
                } else if (item.isCandidate) {
                    customStatusBadge = `<span class="bg-[#2ba640]/10 text-[#2ba640] px-1.5 py-0.5 rounded text-[10px] font-bold w-fit mt-1">Challenger '26</span>`;
                } else if (item.party === 'Vacant' || item.status === 'Vacant') {
                    customStatusBadge = `<span class="bg-yt-hover text-yt-text px-1.5 py-0.5 rounded text-[10px] border border-yt-border font-bold w-fit mt-1">VACANT SEAT</span>`;
                } else if (item.chamber.includes('Senate') && item.electionYear) {
                    customStatusBadge = `<span class="bg-yt-hover text-yt-textMuted px-1.5 py-0.5 rounded text-[10px] border border-yt-border font-bold w-fit mt-1">Up In '${item.electionYear.toString().substring(2)}</span>`;
                }

                return `
                    <div class="group cursor-pointer flex flex-col gap-2" onclick="openProfile('${item.id}')">
                        <div class="relative w-full aspect-[4/5] rounded-xl overflow-hidden bg-yt-hover border border-yt-border group-hover:border-yt-text transition-colors">
                            <img class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" 
                                 src="${imgSrc}" 
                                 loading="lazy"
                                 data-photo-idx="0"
                                 onerror="window.handleImageFallback(this, '${item.id}')"
                                 alt="${item.name}">
                        </div>
                        <div class="flex flex-col px-1">
                            <h3 class="text-sm font-bold text-yt-text leading-tight line-clamp-2">${item.name}</h3>
                            <p class="text-xs text-yt-textMuted mt-1 line-clamp-1 font-medium">${officeLabel}</p>
                            <p class="text-[11px] ${partyColor} font-bold line-clamp-1 mt-0.5">${item.party}</p>
                            ${customStatusBadge}
                        </div>
                    </div>
                `;
            }).join('');
        }

        function parseDistrictNum(val) {
            if (!val || val === 'N/A' || val === 'nan') return 999;
            if (val.toLowerCase().includes('at-large')) return 0;
            const matchSimple = val.match(/\d+/);
            return matchSimple ? parseInt(matchSimple[0]) : 999;
        }

        __MODAL_JS_HANDLERS_REPLACE__
    </script>
</body>
</html>
"""

    map_html_template = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Partisan Map Data Vis</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/topojson-client@3"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&family=Roboto+Slab:wght@700&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            darkMode: ['class', '[data-theme="amoled"]'],
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Roboto', 'sans-serif'],
                        slab: ['Roboto Slab', 'serif']
                    },
                    colors: {
                        yt: {
                            bg: 'var(--bg-main)',
                            elevated: 'var(--bg-elevated)',
                            input: 'var(--bg-input)',
                            hover: 'var(--bg-hover)',
                            border: 'var(--border-main)',
                            borderHover: 'var(--border-hover)',
                            text: 'var(--text-main)',
                            textMuted: 'var(--text-muted)',
                            textFaint: 'var(--text-faint)',
                            inverse: 'var(--text-inverse)'
                        }
                    }
                }
            }
        }
    </script>
    <style>
        :root {
            --bg-main: #0f0f0f;
            --bg-elevated: #181818;
            --bg-input: #121212;
            --bg-hover: #272727;
            --border-main: #303030;
            --border-hover: #3f3f3f;
            --text-main: #f1f1f1;
            --text-muted: #aaaaaa;
            --text-faint: #717171;
            --text-inverse: #0f0f0f;
        }
        [data-theme="amoled"] {
            --bg-main: #000000;
            --bg-elevated: #0a0a0a;
            --bg-input: #050505;
            --bg-hover: #1a1a1a;
            --border-main: #222222;
            --border-hover: #333333;
            --text-main: #ffffff;
            --text-muted: #888888;
            --text-faint: #555555;
            --text-inverse: #000000;
        }
        [data-theme="light"] {
            --bg-main: #f9f9f9;
            --bg-elevated: #ffffff;
            --bg-input: #f0f0f0;
            --bg-hover: #e5e5e5;
            --border-main: #cccccc;
            --border-hover: #aaaaaa;
            --text-main: #0f0f0f;
            --text-muted: #606060;
            --text-faint: #909090;
            --text-inverse: #ffffff;
        }
        body { font-family: 'Roboto', sans-serif; background-color: var(--bg-main); color: var(--text-main); }
        .custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: var(--text-faint); border-radius: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
        .state-path { transition: opacity 0.2s ease-in-out, fill 0.3s ease-in-out; }
        .state-path:hover { opacity: 0.8; }
    </style>
    <script>
        (function() {
            const saved = localStorage.getItem('ytTheme') || 'dark';
            document.documentElement.setAttribute('data-theme', saved);
        })();
    </script>
</head>
<body class="h-full flex flex-col antialiased overflow-hidden">
    
    <header class="h-14 flex-shrink-0 flex items-center justify-between px-6 border-b border-yt-border bg-yt-bg z-40">
        <div class="flex items-center space-x-6">
            <div class="flex items-center text-yt-text">
                <i data-lucide="vote" class="w-6 h-6 mr-3 text-[#3ea6ff]"></i>
                <h1 class="text-xl font-bold tracking-tight font-slab">KYC Directory</h1>
            </div>
        </div>
        <div class="flex items-center space-x-2 w-auto justify-end">
            <div class="relative group mr-2">
                <button class="p-2 text-yt-textMuted hover:text-yt-text hover:bg-yt-hover rounded-full transition-colors flex items-center">
                    <i data-lucide="sun-moon" class="w-5 h-5"></i>
                </button>
                <div class="absolute right-0 mt-2 w-40 bg-yt-elevated border border-yt-border rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                    <button onclick="setTheme('dark')" class="w-full text-left px-4 py-2 text-sm text-yt-text hover:bg-yt-hover rounded-t-lg">Dark Theme</button>
                    <button onclick="setTheme('amoled')" class="w-full text-left px-4 py-2 text-sm text-yt-text hover:bg-yt-hover">AMOLED Dark</button>
                    <button onclick="setTheme('light')" class="w-full text-left px-4 py-2 text-sm text-yt-text hover:bg-yt-hover rounded-b-lg">Light Theme</button>
                </div>
            </div>
        </div>
    </header>

    <div class="flex flex-1 overflow-hidden">
        
        <aside class="w-60 flex-shrink-0 border-r border-yt-border bg-yt-bg flex flex-col h-full overflow-y-auto custom-scrollbar">
            <div class="p-3">
                <a href="index.html" class="flex items-center px-3 py-2.5 rounded-lg text-yt-text hover:bg-yt-hover font-medium text-sm transition-colors">
                    <i data-lucide="layout-grid" class="w-5 h-5 mr-4 text-yt-textMuted"></i> Profile Grid
                </a>
                <a href="map.html" class="flex items-center px-3 py-2.5 rounded-lg bg-yt-hover text-yt-text font-medium text-sm mt-1">
                    <i data-lucide="map" class="w-5 h-5 mr-4 text-yt-textMuted"></i> Partisan Map
                </a>
            </div>
            
            <hr class="border-yt-border my-2 mx-4">
            
            <div class="px-4 py-2">
                <h3 class="text-xs font-bold text-yt-textMuted uppercase tracking-wider mb-3">119th Congress</h3>
                <div class="text-xs font-bold text-yt-textMuted mb-1">SENATE</div>
                <div class="text-sm font-bold text-yt-text mb-4"><span class="text-[#ff4e45]">53 R</span> <span class="text-yt-textFaint mx-1">|</span> <span class="text-[#3ea6ff]">47 D/I</span></div>
                
                <div class="text-xs font-bold text-yt-textMuted mb-1">HOUSE</div>
                <div class="text-sm font-bold text-yt-text mb-4" id="sidebarHouseStats"><span class="text-yt-textFaint">Loading...</span></div>
            </div>

            <hr class="border-yt-border my-2 mx-4">
            
            <div class="px-4 py-2">
                <h3 class="text-xs font-bold text-yt-text flex items-center mb-3"><i data-lucide="flag" class="w-3.5 h-3.5 mr-2 text-[#ffb000]"></i> 2026 Elections</h3>
                
                <div class="flex justify-between text-xs mb-1.5 text-yt-textMuted"><span class="font-medium">Senate Seats Up</span><span class="font-bold text-yt-text">35</span></div>
                <div class="flex justify-between text-xs mb-4 text-yt-textMuted"><span class="font-medium">Defending</span><span class="font-bold" id="senateDefendingCount"><span class="text-yt-textFaint">Loading...</span></span></div>
                
                <div class="flex justify-between text-xs mb-1 text-yt-textMuted"><span class="font-medium">House Seats Up</span><span class="font-bold text-yt-text">435</span></div>
                <div class="text-[10px] text-yt-textFaint">(All 2-Year Terms)</div>
            </div>
        </aside>

        <main class="flex-1 flex flex-col relative bg-yt-bg overflow-hidden min-h-0">
            
            <div class="h-14 flex-shrink-0 flex justify-between items-center px-6 border-b border-yt-border w-full bg-yt-bg z-10 relative">
                 <div class="flex items-center gap-4">
                     <h2 class="text-base font-bold text-yt-text">Geographic Partisan Map</h2>
                     <div id="mapLegend" class="flex items-center gap-3 text-xs font-medium text-yt-textMuted ml-4 border-l border-yt-border pl-4">
                         <!-- Legend renders here -->
                     </div>
                 </div>
                 <div class="flex bg-yt-input p-1 rounded-lg border border-yt-border">
                    <button id="btnSenateMode" onclick="toggleMapMode('Senate')" class="px-4 py-1.5 text-xs font-bold rounded-md transition-colors bg-yt-hover text-yt-text">Senate Mode</button>
                    <button id="btnSenate2026Mode" onclick="toggleMapMode('Senate2026')" class="px-4 py-1.5 text-xs font-bold rounded-md transition-colors text-yt-textMuted hover:text-yt-text flex items-center"><i data-lucide="flag" class="w-3 h-3 mr-1.5 text-[#ffb000]"></i> '26 Races</button>
                    <button id="btnHouseMode" onclick="toggleMapMode('House')" class="px-4 py-1.5 text-xs font-bold rounded-md transition-colors text-yt-textMuted hover:text-yt-text border-l border-yt-border ml-1 pl-4">House Mode</button>
                 </div>
            </div>

            <div class="flex-1 w-full relative min-h-0">
                <svg id="us-map" class="absolute inset-0 w-full h-full" viewBox="0 0 975 680" preserveAspectRatio="xMidYMid meet"></svg>
            </div>
            
            <div class="shrink-0 text-center pb-4 pt-1 w-full bg-yt-bg">
                <span class="bg-yt-elevated text-[11px] font-bold text-yt-textMuted px-3 py-1.5 rounded-full border border-yt-border shadow-sm inline-flex items-center"><i data-lucide="info" class="w-3.5 h-3.5 mr-1.5"></i> Click any state or territory to view its delegation</span>
            </div>
        </main>

        <aside class="w-[320px] flex-shrink-0 border-l border-yt-border bg-yt-bg flex flex-col h-full z-20">
            <div class="p-5 border-b border-yt-border bg-yt-input shrink-0">
                <div class="flex justify-between items-start mb-1">
                    <div class="flex items-center text-[#3ea6ff]">
                        <i data-lucide="map-pin" class="w-4 h-4 mr-2"></i>
                        <h3 class="text-sm font-bold text-yt-text" id="selectedStateLabel">State: Select on map</h3>
                    </div>
                    <div id="stateCounterBadge" class="hidden text-[10px] font-bold bg-yt-hover border border-yt-border px-2 py-1 rounded-md text-yt-text"></div>
                </div>
                <p class="text-[10px] text-yt-textMuted font-bold uppercase tracking-wider ml-6 mt-1" id="selectedStateSubtitle">NO DELEGATION SELECTED</p>
            </div>
            <div class="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2" id="delegationListContainer">
                <div class="flex flex-col items-center justify-center h-full text-center p-6 text-yt-textFaint">
                    <i data-lucide="map" class="w-12 h-12 mb-3 opacity-50"></i>
                    <p class="text-sm font-medium">Select a state on the map to view its active members and candidates.</p>
                </div>
            </div>
        </aside>
    </div>

    __MODAL_BODY_REPLACE__

    <script>
        const legislatorsData = __LEGISLATORS_DATA_REPLACE__;
        
        const fipsToState = {
            "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY", "60": "AS", "66": "GU", "69": "MP", "72": "PR", "78": "VI"
        };

        let mapMode = 'Senate', selectedState = '';
        let geoData = null;
        let pathGenerator = null;

        window.addEventListener('DOMContentLoaded', () => {
            updateElectionWatchBadge();
            loadMap();
            lucide.createIcons();
            toggleMapMode('Senate');
        });

        async function loadMap() {
            try {
                const us = await d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json");
                geoData = topojson.feature(us, us.objects.states).features;
                pathGenerator = d3.geoPath();
                renderMap();
                renderTerritories();
            } catch (err) {
                console.error("Failed to load geographic data", err);
            }
        }

        function toggleMapMode(mode) {
            mapMode = mode;
            document.getElementById('btnSenateMode').className = mode === 'Senate' ? "px-4 py-1.5 text-xs font-bold rounded-md transition-colors bg-yt-hover text-yt-text" : "px-4 py-1.5 text-xs font-bold rounded-md transition-colors text-yt-textMuted hover:text-yt-text";
            document.getElementById('btnSenate2026Mode').className = mode === 'Senate2026' ? "px-4 py-1.5 text-xs font-bold rounded-md transition-colors bg-yt-hover text-[#ffb000] flex items-center" : "px-4 py-1.5 text-xs font-bold rounded-md transition-colors text-yt-textMuted hover:text-yt-text flex items-center";
            document.getElementById('btnHouseMode').className = mode === 'House' ? "px-4 py-1.5 text-xs font-bold rounded-md transition-colors bg-yt-hover text-yt-text border-l border-yt-border ml-1 pl-4" : "px-4 py-1.5 text-xs font-bold rounded-md transition-colors text-yt-textMuted hover:text-yt-text border-l border-yt-border ml-1 pl-4";
            
            const legendContainer = document.getElementById('mapLegend');
            if (mode === 'House') {
                legendContainer.innerHTML = `
                    <span class="text-yt-textFaint font-bold uppercase mr-1">House Control:</span>
                    <div class="flex items-center">
                        <span class="mr-2 text-[#ff4e45]">100% GOP</span>
                        <div class="w-24 h-2.5 rounded-sm bg-gradient-to-r from-[#ff4e45] via-[#a855f7] to-[#3ea6ff] border border-yt-border"></div>
                        <span class="ml-2 text-[#3ea6ff]">100% DEM</span>
                    </div>
                    <span class="inline-flex items-center ml-2 text-yt-textMuted"><span class="w-2 h-2 bg-[#ffb000] rounded-sm mr-1.5"></span> Ind/Split</span>
                    <span class="inline-flex items-center ml-2 text-yt-textMuted"><span class="w-2 h-2 bg-yt-textFaint rounded-sm mr-1.5"></span> Vacant Seat(s)</span>
                `;
            } else if (mode === 'Senate') {
                legendContainer.innerHTML = `
                    <span class="text-yt-textFaint font-bold uppercase mr-1">Senate Legend:</span>
                    <span class="inline-flex items-center text-yt-textMuted"><span class="w-2 h-2 bg-[#ff4e45] rounded-sm mr-1.5"></span> Republican</span>
                    <span class="inline-flex items-center text-yt-textMuted"><span class="w-2 h-2 bg-[#3ea6ff] rounded-sm mr-1.5"></span> Democratic</span>
                    <span class="inline-flex items-center text-yt-textMuted"><span class="w-2 h-2 bg-[#a855f7] rounded-sm mr-1.5"></span> Split</span>
                    <span class="inline-flex items-center text-yt-textMuted"><span class="w-2 h-2 bg-[#ffb000] rounded-sm mr-1.5"></span> Ind/Other</span>
                `;
            } else if (mode === 'Senate2026') {
                legendContainer.innerHTML = `
                    <span class="text-[#ffb000] font-bold uppercase mr-1 flex items-center"><i data-lucide="flag" class="w-3 h-3 mr-1"></i> Defending Party:</span>
                    <span class="inline-flex items-center text-yt-textMuted"><span class="w-2 h-2 bg-[#ff4e45] rounded-sm mr-1.5"></span> Rep. Seat Up</span>
                    <span class="inline-flex items-center text-yt-textMuted"><span class="w-2 h-2 bg-[#3ea6ff] rounded-sm mr-1.5"></span> Dem. Seat Up</span>
                    <span class="inline-flex items-center text-yt-textMuted"><span class="w-2 h-2 bg-yt-input border border-yt-border rounded-sm mr-1.5"></span> No Race</span>
                `;
            }

            updateMapVisuals();
            if (selectedState) showStateDelegation(selectedState);
        }

        function renderMap() {
            const svg = d3.select("#us-map");
            
            const states = svg.selectAll("g.state-group")
                .data(geoData, d => d.id);

            const statesEnter = states.enter()
                .append("g")
                .attr("class", "state-group")
                .style("cursor", "pointer")
                .on("click", (e, d) => {
                    const abbrev = fipsToState[d.id];
                    if (abbrev) selectState(abbrev);
                });

            statesEnter.append("path")
                .attr("class", "state-path")
                .attr("d", pathGenerator)
                .attr("stroke", "var(--bg-main)")
                .attr("stroke-width", 1);

            statesEnter.append("text")
                .attr("class", "state-label")
                .attr("text-anchor", "middle")
                .attr("fill", "white")
                .style("font-size", "10px")
                .style("font-weight", "900")
                .style("pointer-events", "none")
                .style("text-shadow", "0px 1px 3px rgba(0,0,0,0.8)")
                .attr("x", d => {
                    const c = pathGenerator.centroid(d);
                    return c && !isNaN(c[0]) ? c[0] : 0;
                })
                .attr("y", d => {
                    const c = pathGenerator.centroid(d);
                    return c && !isNaN(c[1]) ? c[1] + 4 : 0;
                })
                .text(d => fipsToState[d.id] || "");

            statesEnter.append("title");
        }

        function renderTerritories() {
            const svg = d3.select("#us-map");
            const container = svg.append("g").attr("id", "territories-layer");
            
            container.append("text")
                .attr("x", 610)
                .attr("y", 590)
                .attr("text-anchor", "middle")
                .attr("fill", "var(--text-faint)")
                .style("font-size", "10px")
                .style("font-weight", "700")
                .text("Territories & D.C.");

            const territories = ['DC', 'PR', 'GU', 'VI', 'AS', 'MP'];
            
            const territoryPaths = {
                'DC': 'M 20 2 L 34 16 L 20 30 C 15 28 10 25 8 18 L 20 2 Z',
                'PR': 'M 4 10 L 10 9 L 20 9 L 30 10 L 36 12 L 36 18 L 30 20 L 20 21 L 10 20 L 4 17 Z',
                'GU': 'M 20 2 C 25 2 25 7 22 10 C 19 12 21 15 24 18 C 26 21 21 23 17 20 C 14 17 16 14 18 10 C 20 7 15 4 20 2 Z',
                'VI': 'M 10 6 C 14 4 18 6 16 10 C 12 10 8 8 10 6 Z M 22 6 C 26 6 28 10 24 12 C 20 12 20 8 22 6 Z M 16 18 C 22 16 30 16 28 20 C 22 22 14 20 16 18 Z',
                'AS': 'M 6 14 C 14 10 26 12 30 14 C 22 18 12 18 6 14 Z M 34 16 A 1.5 1.5 0 1 0 34 19 A 1.5 1.5 0 1 0 34 16',
                'MP': 'M 24 4 C 26 4 26 8 24 10 C 22 8 22 4 24 4 Z M 22 12 C 24 12 24 16 22 18 C 20 16 20 12 22 12 Z M 16 20 C 19 20 19 24 16 26 C 13 24 13 20 16 20 Z'
            };
            
            const boxes = container.selectAll("g.territory-group")
                .data(territories)
                .enter()
                .append("g")
                .attr("class", "territory-group state-group")
                .style("cursor", "pointer")
                .attr("transform", (d, i) => `translate(${490 + i * 45}, 600)`)
                .on("click", (e, d) => {
                    selectState(d);
                });

            boxes.append("rect")
                .attr("class", "territory-hitbox")
                .attr("width", 40)
                .attr("height", 35)
                .attr("fill", "transparent");

            boxes.append("path")
                .attr("class", "territory-shape state-path")
                .attr("d", d => territoryPaths[d])
                .attr("stroke", "var(--bg-main)")
                .attr("stroke-width", 1)
                .attr("fill", "var(--bg-hover)");

            boxes.append("text")
                .attr("x", 20)
                .attr("y", 42)
                .attr("text-anchor", "middle")
                .attr("fill", "var(--text-main)")
                .style("font-size", "10px")
                .style("font-weight", "900")
                .style("pointer-events", "none")
                .style("text-shadow", "0px 1px 3px rgba(0,0,0,0.8)")
                .text(d => d);

            boxes.append("title");
        }

        function getVisualStyles(stateAbbrev, colorScale) {
            const p = getStateRatios(stateAbbrev);
            let fill = "var(--bg-hover)"; 
            let hoverText = '';

            if (mapMode === 'Senate') {
                if (p.senGop === 2) fill = "#ff4e45";
                else if (p.senDem + p.senInd === 2) fill = "#3ea6ff";
                else if (p.senGop === 1 && (p.senDem === 1 || p.senInd === 1)) fill = "#a855f7";
                else if (p.senInd === 2) fill = "#ffb000"; 
                hoverText = `${stateAbbrev} Senate: ${p.senGop}R - ${p.senDem}D - ${p.senInd}I`;
            } else if (mapMode === 'House') {
                const total = p.houseDem + p.houseGop + p.houseInd; 
                const totalWithVacancies = total + p.houseVacant;
                
                if (totalWithVacancies > 0) {
                    if (total === 0 && p.houseVacant > 0) {
                        fill = "var(--text-faint)"; 
                    } else if (p.houseInd === total) {
                        fill = "#ffb000";
                    } else {
                        const demRatio = p.houseDem / (p.houseDem + p.houseGop);
                        fill = colorScale(demRatio);
                    }
                }
                hoverText = `${stateAbbrev} House: ${p.houseGop}R - ${p.houseDem}D - ${p.houseInd}I` + (p.houseVacant > 0 ? ` (${p.houseVacant} Vacant)` : '');
            } else if (mapMode === 'Senate2026') {
                const senUpMembers = legislatorsData.filter(x => x.state === stateAbbrev && x.chamber.includes('Senate') && x.isUpIn2026 && !x.isCandidate);
                if (senUpMembers.length === 0) {
                    fill = "var(--bg-elevated)"; 
                    hoverText = `${stateAbbrev}: No Senate Race in 2026`;
                } else {
                    const party = senUpMembers[0].party;
                    if (party === 'Republican') fill = "#ff4e45";
                    else if (party.includes('Democrat') || party === 'Independent') fill = "#3ea6ff";
                    hoverText = `${stateAbbrev}: 2026 Senate Race (${senUpMembers[0].name}, ${senUpMembers[0].party} Defending)`;
                }
            }

            let strokeColor = stateAbbrev === selectedState ? "var(--text-main)" : "var(--bg-main)";
            let strokeWidth = stateAbbrev === selectedState ? 2.5 : 1;

            return { fill, hoverText, strokeColor, strokeWidth };
        }

        function updateMapVisuals() {
            try {
                const svg = d3.select("#us-map");
                const colorScale = d3.scaleLinear().domain([0, 0.5, 1]).range(["#ff4e45", "#a855f7", "#3ea6ff"]);

                svg.selectAll("g.state-group").each(function(d) {
                    const group = d3.select(this);
                    const pathEl = group.select(".state-path");
                    const titleEl = group.select("title");
                    
                    const stateAbbrev = typeof d === 'string' ? d : fipsToState[d.id];
                    
                    if (!stateAbbrev) {
                        group.style("display", "none");
                        return;
                    }

                    const styles = getVisualStyles(stateAbbrev, colorScale);
                    
                    titleEl.text(styles.hoverText);
                    pathEl.attr("fill", styles.fill)
                          .attr("stroke", styles.strokeColor)
                          .attr("stroke-width", styles.strokeWidth);
                });
                
                // Safely bring the selected state to the front without breaking D3 iteration
                if (selectedState) {
                    svg.selectAll("g.state-group").filter(function(d) {
                        const abbr = typeof d === 'string' ? d : fipsToState[d.id];
                        return abbr === selectedState;
                    }).raise();
                }

            } catch(e) {
                console.error("Map visual update failed:", e);
            }
        }

        function getStateRatios(state) {
            const members = legislatorsData.filter(x => x.state === state);
            const sen = members.filter(x => x.chamber.includes('Senate') && !x.chamber.includes('Candidate'));
            const hou = members.filter(x => x.chamber.includes('House') && !x.chamber.includes('Candidate'));
            return {
                senGop: sen.filter(x => x.party === 'Republican').length,
                senDem: sen.filter(x => x.party.includes('Democrat')).length,
                senInd: sen.filter(x => x.party !== 'Republican' && !x.party.includes('Democrat')).length,
                houseGop: hou.filter(x => x.party === 'Republican').length,
                houseDem: hou.filter(x => x.party.includes('Democrat')).length,
                houseInd: hou.filter(x => x.party !== 'Republican' && !x.party.includes('Democrat') && x.party !== 'Vacant').length,
                houseVacant: hou.filter(x => x.party === 'Vacant' || x.status === 'Vacant').length
            };
        }

        function selectState(state) {
            selectedState = state;
            updateMapVisuals();
            showStateDelegation(state);
        }

        function showStateDelegation(state) {
            const list = document.getElementById('delegationListContainer');
            const allMembers = legislatorsData.filter(x => x.state === state);
            let display = [];
            if (mapMode === 'Senate') {
                display = allMembers.filter(x => x.chamber.includes('Senate') && !x.isCandidate);
                document.getElementById('selectedStateSubtitle').textContent = `U.S. SENATE DELEGATION FOR ${state}`;
            } else if (mapMode === 'House') {
                display = allMembers.filter(x => x.chamber.includes('House'));
                document.getElementById('selectedStateSubtitle').textContent = `U.S. HOUSE & CANDIDATES FOR ${state}`;
            } else if (mapMode === 'Senate2026') {
                display = allMembers.filter(x => x.chamber.includes('Senate') && (x.isUpIn2026 || x.isCandidate));
                document.getElementById('selectedStateSubtitle').textContent = `2026 SENATE RACE CANDIDATES FOR ${state}`;
            }
            
            document.getElementById('selectedStateLabel').textContent = `State: ${state}`;
            
            const p = getStateRatios(state);
            let badgeHTML = '';
            if (mapMode === 'Senate') {
                const arr = [];
                if (p.senGop > 0) arr.push(`<span class="text-[#ff4e45]">${p.senGop} R</span>`);
                if (p.senDem > 0) arr.push(`<span class="text-[#3ea6ff]">${p.senDem} D</span>`);
                if (p.senInd > 0) arr.push(`<span class="text-[#ffb000]">${p.senInd} I</span>`);
                badgeHTML = arr.join(' <span class="text-yt-border mx-1">|</span> ');
            } else if (mapMode === 'Senate2026') {
                const incumbents = display.filter(x => x.isUpIn2026 && !x.isCandidate);
                if (incumbents.length > 0) {
                    badgeHTML = `<span class="${incumbents[0].party === 'Republican' ? 'text-[#ff4e45]' : 'text-[#3ea6ff]'}">Defending: ${incumbents[0].party}</span>`;
                } else {
                    badgeHTML = `<span class="text-yt-textMuted">No Incumbent</span>`;
                }
            } else {
                const arr = [];
                if (p.houseGop > 0) arr.push(`<span class="text-[#ff4e45]">${p.houseGop} R</span>`);
                if (p.houseDem > 0) arr.push(`<span class="text-[#3ea6ff]">${p.houseDem} D</span>`);
                if (p.houseInd > 0) arr.push(`<span class="text-[#ffb000]">${p.houseInd} I</span>`);
                if (p.houseVacant > 0) arr.push(`<span class="text-yt-text">${p.houseVacant} Vac</span>`);
                badgeHTML = arr.join(' <span class="text-yt-border mx-1">|</span> ');
            }
            document.getElementById('stateCounterBadge').innerHTML = badgeHTML || `<span class="text-yt-textFaint">0 Seats</span>`;
            document.getElementById('stateCounterBadge').classList.remove('hidden');

            if (display.length === 0) {
                list.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-center p-6 text-yt-textFaint"><i data-lucide="users" class="w-12 h-12 mb-3 opacity-50"></i><p class="text-sm font-bold">No active profiles for this selection.</p></div>`;
                lucide.createIcons();
                return;
            }

            display.sort((a, b) => {
                const isCandA = a.chamber.includes('Candidate') ? 1 : 0;
                const isCandB = b.chamber.includes('Candidate') ? 1 : 0;
                if (isCandA !== isCandB) return isCandA - isCandB;
                const distA = parseInt(a.district.match(/\d+/) || [999]);
                const distB = parseInt(b.district.match(/\d+/) || [999]);
                return distA - distB;
            });

            list.innerHTML = display.map(item => {
                let partyColor = item.party.includes('Democrat') ? 'text-[#3ea6ff]' : (item.party === 'Republican' ? 'text-[#ff4e45]' : 'text-[#ffb000]');
                if (item.party === 'Vacant' || item.status === 'Vacant') partyColor = 'text-yt-text';
                
                let imgSrc = item.photos && item.photos.length > 0 ? item.photos[0] : 'placeholder';
                if (imgSrc === 'placeholder') imgSrc = defaultSilhouette;
                
                let officeLabel = item.chamber;
                if (item.chamber.includes('House')) {
                    let dist = (item.district && item.district !== 'N/A' && item.district !== 'nan') ? item.district : '';
                    if (dist.toLowerCase() === 'at-large' || dist === '0') dist = 'AL';
                    officeLabel = dist ? `House • ${item.state}-${dist}` : `House • ${item.state}`;
                } else if (item.chamber.includes('Senate')) {
                    officeLabel = `Senate • ${item.state}`;
                }

                let termEndBadge = "";
                const lowerStatus = item.status ? item.status.toLowerCase() : '';
                const isLeaving = lowerStatus.includes('retiring') || lowerStatus.includes('not running') || lowerStatus.includes('defeated') || lowerStatus.includes('ineligible');

                if (isLeaving) {
                    termEndBadge = `
                    <div class="flex flex-col items-center justify-center mr-1 shrink-0">
                        <span class="text-[7px] font-black text-[#ff4e45] uppercase tracking-widest mb-0.5">Leaving</span>
                        <span class="text-[10px] font-bold text-[#ff4e45] bg-[#ff4e45]/10 px-1.5 py-0.5 rounded border border-[#ff4e45]/20">'26</span>
                    </div>`;
                } else if (item.chamber.includes('Senate') && item.isUpIn2026 && !item.isCandidate) {
                    termEndBadge = `
                    <div class="flex flex-col items-center justify-center mr-1 shrink-0">
                        <span class="text-[7px] font-black text-[#ffb000] uppercase tracking-widest mb-0.5">Seat Up</span>
                        <span class="text-[10px] font-bold text-[#ffb000] bg-[#ffb000]/10 px-1.5 py-0.5 rounded border border-[#ffb000]/20">'26</span>
                    </div>`;
                } else if (item.isCandidate) {
                    termEndBadge = `
                    <div class="flex flex-col items-center justify-center mr-1 shrink-0">
                        <span class="text-[7px] font-black text-[#2ba640] uppercase tracking-widest mb-0.5">Challenger</span>
                        <span class="text-[10px] font-bold text-[#2ba640] bg-[#2ba640]/10 px-1.5 py-0.5 rounded border border-[#2ba640]/20">'26</span>
                    </div>`;
                } else if (item.chamber.includes('Senate') && item.electionYear) {
                    termEndBadge = `
                    <div class="flex flex-col items-center justify-center mr-1 shrink-0">
                        <span class="text-[7px] font-black text-yt-textFaint uppercase tracking-widest mb-0.5">Up In</span>
                        <span class="text-[10px] font-bold text-yt-textMuted bg-yt-hover px-1.5 py-0.5 rounded border border-yt-border">'${item.electionYear.toString().substring(2)}</span>
                    </div>`;
                }

                return `
                    <div class="flex items-center gap-3 p-3 bg-yt-input border border-yt-border rounded-xl hover:bg-yt-hover transition-all duration-200 group">
                        <div class="relative shrink-0 w-11 h-14 overflow-hidden rounded-lg bg-yt-hover cursor-pointer border border-yt-border" onclick="openProfile('${item.id}')">
                            <img class="w-full h-full object-cover transition-transform group-hover:scale-105" 
                                 src="${imgSrc}" 
                                 data-photo-idx="0"
                                 onerror="window.handleImageFallback(this, '${item.id}')"
                                 alt="${item.name}">
                        </div>
                        <div class="min-w-0 flex-1">
                            <h4 class="text-xs font-bold text-yt-text truncate group-hover:text-[#3ea6ff] cursor-pointer" onclick="openProfile('${item.id}')">${item.name}</h4>
                            <p class="text-[10px] text-yt-textMuted font-medium">${officeLabel}</p>
                            <span class="inline-flex text-[10px] font-bold ${partyColor} mt-0.5">${item.party}</span>
                        </div>
                        ${termEndBadge}
                        <button onclick="openProfile('${item.id}')" class="p-1.5 text-yt-textFaint hover:text-yt-text transition-colors">
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </button>
                    </div>
                `;
            }).join('');
            lucide.createIcons();
        }

        __MODAL_JS_HANDLERS_REPLACE__
    </script>
</body>
</html>
"""

    json_data_escaped = json.dumps(unified_list).replace("</script>", "<\\/script>")
    
    index_html_final = index_html_template.replace('__LEGISLATORS_DATA_REPLACE__', json_data_escaped)
    index_html_final = index_html_final.replace('__MODAL_BODY_REPLACE__', shared_modal_body)
    index_html_final = index_html_final.replace('__MODAL_JS_HANDLERS_REPLACE__', shared_modal_js_handlers)
    
    with open(index_file_path, 'w', encoding='utf-8') as f:
        f.write(index_html_final)
    print("Generated index.html successfully.")
    
    map_html_final = map_html_template.replace('__LEGISLATORS_DATA_REPLACE__', json_data_escaped)
    map_html_final = map_html_final.replace('__MODAL_BODY_REPLACE__', shared_modal_body)
    map_html_final = map_html_final.replace('__MODAL_JS_HANDLERS_REPLACE__', shared_modal_js_handlers)
    
    with open(map_file_path, 'w', encoding='utf-8') as f:
        f.write(map_html_final)
    print("Generated map.html successfully.")
    
    zip_scratch_path = '/workspace/scratch/candidate_profiles_site.zip'
    if os.path.exists('/workspace/scratch'):
        with zipfile.ZipFile(zip_scratch_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(index_file_path, 'index.html')
            zip_file.write(map_file_path, 'map.html')
            if house_csv: zip_file.write(house_csv, 'Cleaned_House_119th.csv')
            if senate_csv: zip_file.write(senate_csv, 'Cleaned_Senate_119th.csv')
            
        os.makedirs('/workspace/out', exist_ok=True)
        shutil.copy(zip_scratch_path, '/workspace/out/candidate_profiles_site.zip')
        print("All website assets compiled and compressed to out!")

if __name__ == '__main__':
    build_website()