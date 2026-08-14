import os
import csv
import json
import re
import math
import urllib.request
import urllib.parse
import zipfile
import shutil

def build_website():
    def get_latest_csv(prefix):
        filename = f"{prefix}.csv"
        return filename if os.path.exists(filename) else None

    def read_csv_dict(filepath):
        if not filepath or not os.path.exists(filepath): return []
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            reader = list(csv.DictReader(f))
            return reader

    house_csv = get_latest_csv('Cleaned_House_119th')
    senate_csv = get_latest_csv('Cleaned_Senate_119th')
    completed_cand_csv = get_latest_csv('Completed_Primary_Candidates_2026')
    late_cand_csv = get_latest_csv('Late_Primary_Candidates_2026')
    all_cand_csv = get_latest_csv('Congressional_Candidates_2026')

    current_rows = []
    if house_csv: current_rows.extend(read_csv_dict(house_csv))
    if senate_csv: current_rows.extend(read_csv_dict(senate_csv))

    # Deduplicate current members
    dedup_current = {}
    for r in current_rows:
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
            key = f"House_{state}_{dist_num}"
        else:
            if 'Vacant' in name:
                key = f"Vacant_{state}_{dist}"
            else:
                key = f"Senate_{state}_{name}"
        dedup_current[key] = r

    current_members_list = list(dedup_current.values())

    # Candidate rows
    candidate_rows = []
    if all_cand_csv:
        candidate_rows.extend(read_csv_dict(all_cand_csv))
    if completed_cand_csv:
        candidate_rows.extend(read_csv_dict(completed_cand_csv))
    if late_cand_csv:
        candidate_rows.extend(read_csv_dict(late_cand_csv))

    dedup_cands = {}
    for r in candidate_rows:
        name = str(r.get('Name', '')).strip()
        if name:
            dedup_cands[name.lower()] = r

    candidates_list = list(dedup_cands.values())

    print(f"\n[+] Loaded {len(current_members_list)} current members and {len(candidates_list)} candidates.")

    HARDCODED_PHOTOS = {
        "James Talarico": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/James_Talarico.jpg/800px-James_Talarico.jpg",
        "Ken Paxton": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Ken_Paxton_official_photo_%28cropped%29.jpg/800px-Ken_Paxton_official_photo_%28cropped%29.jpg",
        "Mike Rogers": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Mike_Rogers_official_portrait.jpg/800px-Mike_Rogers_official_portrait.jpg",
        "Abdul El-Sayed": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Abdul_El-Sayed_by_Gage_Skidmore.jpg/800px-Abdul_El-Sayed_by_Gage_Skidmore.jpg",
        "Roy Cooper": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Roy_Cooper_official_photo.jpg/800px-Roy_Cooper_official_photo.jpg",
        "Dan Osborn": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Dan_Osborn_for_Senate_%28cropped%29.jpg/800px-Dan_Osborn_for_Senate_%28cropped%29.jpg",
        "Michael Whatley": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Michael_Whatley_in_2024.jpg/800px-Michael_Whatley_in_2024.jpg",
        "Charles Booker": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Charles_Booker.jpg/800px-Charles_Booker.jpg",
        "Andy Barr": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Andy_Barr_official_photo.jpg/800px-Andy_Barr_official_photo.jpg",
        "Juliana Stratton": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Juliana_Stratton.jpg/800px-Juliana_Stratton.jpg",
        "Ashley Hinson": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/Ashley_Hinson_Official_Portrait.jpg/800px-Ashley_Hinson_Official_Portrait.jpg",
        "Mike Collins": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Mike_Collins_118th_Congress.jpg/800px-Mike_Collins_118th_Congress.jpg",
        "Julia Letlow": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Julia_Letlow_official_portrait.jpg/800px-Julia_Letlow_official_portrait.jpg",
        "Sherrod Brown": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Sherrod_Brown_official_photo_2019.jpg/800px-Sherrod_Brown_official_photo_2019.jpg",
        "Andy Beshear": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Andy_Beshear_official_portrait.jpg/800px-Andy_Beshear_official_portrait.jpg",
        "Barry Moore": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Barry_Moore_117th_U.S_Congress.jpg/800px-Barry_Moore_117th_U.S_Congress.jpg",
        "Kevin Hern": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Kevin_Hern_118th_Congress.jpg/800px-Kevin_Hern_118th_Congress.jpg",
        "Alex Vindman": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Alexander_Vindman_official_portrait.jpg/800px-Alexander_Vindman_official_portrait.jpg",
        "Brian Kemp": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Brian_Kemp_official_portrait%2C_2023.jpg/800px-Brian_Kemp_official_portrait%2C_2023.jpg",
        "Chris Sununu": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Chris_Sununu_official_portrait_%28cropped%29.jpg/800px-Chris_Sununu_official_portrait_%28cropped%29.jpg",
        "Colin Allred": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Colin_Allred_official_photo.jpg/800px-Colin_Allred_official_photo.jpg",
        "Brad Lander": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Brad_Lander_by_Gage_Skidmore.jpg/800px-Brad_Lander_by_Gage_Skidmore.jpg",
        "Steve Toth": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Steve_Toth_Texas_House.jpg/800px-Steve_Toth_Texas_House.jpg",
        "Troy Jackson": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Troy_Jackson_2019.jpg/800px-Troy_Jackson_2019.jpg",
        "Josh Turek": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Josh_Turek.jpg/800px-Josh_Turek.jpg",
        "Mark Baisley": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Mark_Baisley_2023.jpg/800px-Mark_Baisley_2023.jpg",
        "Marquita Bradshaw": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Marquita_Bradshaw.jpg/800px-Marquita_Bradshaw.jpg",
        "Annie Andrews": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Annie_Andrews_portrait.jpg/800px-Annie_Andrews_portrait.jpg"
    }

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

    def parse_age(val):
        if val is None: return "Unknown"
        val_str = str(val).strip()
        if val_str in ['', 'Unknown', 'nan', 'NaN', 'N/A', 'None']: return "Unknown"
        try:
            age_int = int(float(val_str))
            return age_int if age_int > 0 else "Unknown"
        except (ValueError, TypeError):
            return "Unknown"

    def fmt_curr(val):
        if val is None: return "N/A"
        val_str = str(val).strip()
        if val_str in ['', 'Unknown', 'nan', 'NaN', 'N/A', 'None', '$nan']: return "N/A"
        try:
            if val_str.startswith('$'): return val_str
            val_f = float(val_str)
            if math.isnan(val_f) or val_f == 0: return "N/A"
            return f"${val_f:,.2f}"
        except:
            return val_str if val_str else "N/A"

    def clean_str(val, default="N/A"):
        if val is None: return default
        val_str = str(val).strip()
        if val_str in ['', 'nan', 'NaN', 'None', 'Unknown']: return default
        return val_str

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

    unified_list = []

    # 1. Process Current Members
    for idx, row in enumerate(current_members_list):
        bg_id = str(row.get('Bioguide ID', '')).strip() if row.get('Bioguide ID') else f"CURR_{idx}"
        name = str(row.get('Name', '')).strip()
        if name in ["Marco Rubio", "J.D. Vance", "Markwayne Mullin"]:
            continue

        name_parts = name.split()
        first_n = name_parts[0] if len(name_parts) > 0 else ""
        last_n = name_parts[-1] if len(name_parts) > 1 else ""
        wiki_name = f"{first_n}_{last_n}"

        photos = []
        if name in HARDCODED_PHOTOS:
            photos.append(HARDCODED_PHOTOS[name])

        if row.get('Bioguide ID') and str(row.get('Bioguide ID')).strip() not in ['', 'nan', 'N/A']:
            bg_upper = bg_id.upper()
            bg_lower = bg_id.lower()
            first_letter = bg_upper[0] if bg_upper else 'A'
            photos.extend([
                f"https://www.congress.gov/img/member/{bg_lower}_200.jpg",
                f"https://theunitedstates.io/images/congress/450x550/{bg_upper}.jpg",
                f"https://theunitedstates.io/images/congress/225x275/{bg_upper}.jpg",
                f"https://bioguideretro.congress.gov/Static_Files/images/bioguide/{first_letter}/{bg_upper}.jpg",
                f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}.jpg",
                f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}_official_portrait.jpg"
            ])
        else:
            photos.extend([f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}.jpg", "placeholder"])

        chamber_str = str(row.get('Chamber', '')).strip()
        dist_val = row.get('District')
        dist_str = str(dist_val).strip() if dist_val and str(dist_val).strip() not in ['nan', 'Unknown'] else "N/A"
        if "Senate" in chamber_str or dist_str.lower() == "unknown":
            dist_str = "N/A"

        term_start = clean_str(row.get('Term Start'), "N/A")
        term_end = clean_str(row.get('Term End Date'), "")
        term_str = f"{term_start} - {term_end[:10]}" if term_end and term_end != "N/A" else term_start

        comm_val = clean_str(row.get('Committee Assignments'), "None")
        status_val = clean_str(row.get('Status'), "Active Member")
        status_val = get_custom_status(name, status_val)

        member_dict = {
            "id": bg_id,
            "name": name,
            "chamber": chamber_str,
            "party": clean_str(row.get('Party'), "Independent"),
            "state": clean_str(row.get('State'), "N/A"),
            "district": dist_str,
            "status": status_val,
            "term_start": term_str,
            "age": parse_age(row.get('Age')),
            "birthdate": clean_str(row.get('Birthdate'), "Unknown"),
            "education": clean_str(row.get('Education'), "N/A"),
            "previous_professions": clean_str(row.get('Previous Professions'), "N/A"),
            "receipts": fmt_curr(row.get('Total Receipts')),
            "disbursements": fmt_curr(row.get('Total Disbursements')),
            "funding_sources": clean_str(row.get('Main Funding Sources'), "N/A"),
            "platforms": clean_str(row.get('Policy Focus & Platforms'), "N/A"),
            "voting_alignment": clean_str(row.get('Projected/Historical Voting Alignment'), "N/A"),
            "committees": comm_val,
            "net_worth": clean_str(row.get('Estimated Net Worth'), "N/A"),
            "photos": photos,
            "photo_url": photos[0]
        }
        unified_list.append(member_dict)

    # 2. Process Candidates
    for idx, row in enumerate(candidates_list):
        bg_id = f"CAND_{idx}"
        name = str(row.get('Name', '')).strip()

        candidate_photos = []
        if name in HARDCODED_PHOTOS:
            candidate_photos.append(HARDCODED_PHOTOS[name])

        name_parts = name.split()
        first_n = name_parts[0] if len(name_parts) > 0 else ""
        last_n = name_parts[-1] if len(name_parts) > 1 else ""
        wiki_name = f"{first_n}_{last_n}"

        candidate_photos.extend([
            f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}.jpg",
            f"https://en.wikipedia.org/wiki/Special:FilePath/{wiki_name}_portrait.jpg",
            "placeholder"
        ])

        chamber_str = clean_str(row.get('Chamber'), "Senate (Candidate)")
        office_dist = clean_str(row.get('Office / District'), "N/A")
        state_abbrev = parse_state_abbrev(office_dist)
        if state_abbrev == "N/A" and len(office_dist) == 2 and office_dist.upper() in US_STATES.values():
            state_abbrev = office_dist.upper()

        if "Senate" in chamber_str or office_dist.lower() == "unknown":
            office_dist = "N/A"

        status_val = clean_str(row.get('Status'), "Candidate")
        is_upcoming = str(row.get('Upcoming 2026 Primary', '')).strip().lower() == 'true'
        if is_upcoming and "Upcoming" not in status_val:
            status_val += " (Upcoming Primary)"

        candidate_dict = {
            "id": bg_id,
            "name": name,
            "chamber": chamber_str if "Candidate" in chamber_str or "Winner" in chamber_str else f"{chamber_str} (Candidate)",
            "party": clean_str(row.get('Party'), "Independent"),
            "state": state_abbrev,
            "district": office_dist,
            "status": status_val,
            "term_start": clean_str(row.get('Projected Start'), "Jan. 3, 2027 (If elected)"),
            "age": parse_age(row.get('Age')),
            "birthdate": clean_str(row.get('Birthdate'), "Unknown"),
            "education": clean_str(row.get('Education'), "N/A"),
            "previous_professions": clean_str(row.get('Previous Professions'), "N/A"),
            "receipts": fmt_curr(row.get('Campaign Receipts')),
            "disbursements": fmt_curr(row.get('Campaign Disbursements')),
            "funding_sources": clean_str(row.get('Main Funding Sources'), "N/A"),
            "platforms": clean_str(row.get('Core Campaigning Issues & Platform Focus') or row.get('Policy Focus & Platforms'), "N/A"),
            "voting_alignment": clean_str(row.get('Projected/Historical Voting Alignment'), "N/A"),
            "committees": clean_str(row.get('Historical Committee Assignments (If any)') or row.get('Committee Assignments'), "None"),
            "net_worth": clean_str(row.get('Estimated Net Worth'), "N/A"),
            "photos": candidate_photos,
            "photo_url": candidate_photos[0]
        }
        unified_list.append(candidate_dict)

    print(f"\n[OK] Compiled {len(unified_list)} total unified profiles.")

    os.makedirs('candidate_profiles_site', exist_ok=True)
    index_file_path = 'candidate_profiles_site/index.html'
    map_file_path = 'candidate_profiles_site/map.html'

    def update_index_file(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        start_marker = "const legislatorsData = "
        idx_start = content.find(start_marker)
        if idx_start == -1:
            print(f"Error: Could not find legislatorsData in {filepath}")
            return
        
        idx_end = content.find(";\n        let activeChamber", idx_start)
        if idx_end == -1:
            idx_end = content.find(";\n        \n        const fipsToState", idx_start)
        if idx_end == -1:
            idx_end = content.find(";\n        const fipsToState", idx_start)
        if idx_end == -1:
            bracket_idx = content.find("[", idx_start)
            depth = 0
            for i in range(bracket_idx, len(content)):
                if content[i] == '[': depth += 1
                elif content[i] == ']':
                    depth -= 1
                    if depth == 0:
                        idx_end = i + 1
                        break

        json_data_escaped = json.dumps(unified_list).replace("</script>", "<\\/script>")
        new_content = content[:idx_start + len(start_marker)] + json_data_escaped + content[idx_end:]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[OK] Updated {filepath}")

    update_index_file(index_file_path)
    update_index_file(map_file_path)

if __name__ == '__main__':
    build_website()