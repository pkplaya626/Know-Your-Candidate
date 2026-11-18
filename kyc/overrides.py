"""Hand-curated corrections layered on top of the CSV rosters.

Everything here is an editorial judgement rather than pipeline logic, so it
lives apart from the loaders. Keep entries sourced and minimal - the CSVs are
the source of truth wherever they are correct.
"""

from urllib.parse import urlsplit

# A candidate's portrait chosen by a person, keyed on the profile's id (rules
# 3 and 17): a curated row's ``ID`` ("CAND_4") or a filer's ("FEC_<candidate
# id>"). A name key put one Mike Rogers's portrait on the other's profile,
# and in 2026-10-17 24 of the 25 entries that stood here named Commons files
# made up from a name ("Roy_Cooper_official_photo.jpg"), which do not exist -
# the guess rule 24 forbids. Each entry names a file a page serves now, and
# a person looked at the photograph and at the page:
#
#   url    the file shown: a government office's or the campaign's own file
#          as the page serves it, or a Commons file's upload address; or,
#          where an office's page draws the portrait with no address of its
#          own (a data: image), the file hosted here unmodified
#          ("photos/<hash>.png", listed in rule 101's manifest, ``hosted``,
#          with the page, the hash and the day read)
#   page   the page that names the person beside it (a Commons file: its own
#          description page, in the person's own category)
#   words  the page's words that name them beside it
#   by     whose photograph it is, for the credit line (rule 87); a Commons
#          file's credit is read from its page (``portraits.credit_all``),
#          never typed here
#   tie    why the person the page names is this profile's (rule 25: the
#          state, the office, the years)
#   seen   what the photograph shows: the person alone, nobody else in the
#          frame even in part, the face a tenth of the 4:5 card or more
#   read   the day the page and the photograph were read
#   seat   only for a file the legislature names by its seat ("rep17.jpg"),
#          which shows whoever holds it: the state, chamber, district, Open
#          States id and name of the member it was read for. The photograph
#          is withheld, and validate warns (photo-curated-unseated), once the
#          roster no longer seats them there (photos.curated_seated). A file
#          hosted here is the member's bytes, read once, and needs none.
#
# ``portraits`` puts the entry in the portrait cache as route ``curated``,
# where its size, its weight and a Commons file's credit are read like any
# other; it stands ahead of every automatic route, since a person chose it,
# and ``validate`` fails an entry without these fields, one a person
# refused (NOT_A_PORTRAIT) and one for a profile that no longer exists.
#
# The first entries (2026-10-25) are for people on the November ballot
# whom the background-people sweep of PR #139 left with the silhouette,
# where a route tied to them offers a clean photograph (the owner: "more
# content is better than strict rules", but "better to leave out background
# people").
CANDIDATE_PHOTOS = {
    "CAND_4": {
        "url": "https://www.texasattorneygeneral.gov/sites/default/files/inline-images/"
               "ken_paxton_bio_thumb.jpg",
        "page": "https://www.texasattorneygeneral.gov/about-office",
        "words": "\"About the Attorney General\": \"Ken Paxton is the 51st Attorney General of "
                 "Texas\", the image's alt text \"Texas Attorney General Ken Paxton\"",
        "by": "Office of the Texas Attorney General",
        "tie": "Ken Paxton, the Texas Republican Senate nominee, holds that office: his record "
               "of offices (history, Wikidata and his article agreeing) gives Texas Attorney "
               "General since 2015, and this site's Texas attorney general card shows the same "
               "file from the same page (officers.add_ag_photos)",
        "seen": "a studio portrait, him alone against a plain backdrop",
        "read": "2026-10-25",
    },
    "CAND_9": {
        "url": "https://run.imgix.net/68d35dd5-f7a6-4a7e-9057-c3908286d00f/"
               "e4f5b452-3eca-4f0c-82ea-227d95204138/e4f5b452-3eca-4f0c-82ea-227d95204138.jpg"
               "?ixlib=js-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=0%2C393%2C2102%2C2282"
               "&auto=compress%2Cformat&fit=fillmax&w=640&q=75&s=7faf701c8ebd5e5e8466e7faf23dc0dc",
        "page": "https://www.bradlanderforcongress.com/",
        "words": "the page's opening photograph, beside \"Fight, Don't Fold. Brad Lander is "
                 "running for Congress\" (the srcset's 640px form, signed by the site)",
        "by": "the campaign's website (bradlanderforcongress.com)",
        "tie": "the site his filed campaign site (landerfornyc.com) moved to, which enrich "
               "read as still naming him; his file names no surname, so rule 38's reader "
               "could not take it unattended",
        "seen": "him alone in front of a brick house and a red door, arms folded",
        "read": "2026-10-25",
    },
    "FEC_H6IL02355": {
        "url": "https://www.cookcountyil.gov/sites/g/files/ywwepo161/files/styles/"
               "crop_profile_photo/public/images/portraits/2021-09/"
               "donna_miller_6th_district_0.jpg?h=9326d3c7&itok=su4DaALf",
        "page": "https://www.cookcountyil.gov/all-people/donna-miller",
        "words": "\"Donna Miller - County Board Commissioner, 6th District\", the image's alt "
                 "text \"Board of Commissioner Donna Miller\"",
        "by": "Cook County",
        "tie": "the IL-2 nominee is that commissioner: the article her ballot page links is "
               "about the Cook County commissioner, and her campaign's site says \"As a Cook "
               "County Commissioner, she's led major initiatives\"",
        "seen": "a studio portrait, her alone before the county's seal",
        "read": "2026-10-25",
    },
    "FEC_H6IN05307": {
        "url": "https://indianasenatedemocrats.org/wp-content/uploads/2024/08/"
               "Ford_Headshot-with-State-Flag.jpg",
        "page": "https://indianasenatedemocrats.org/senator/s29/",
        "words": "\"State Senator J.D. Ford - Indiana Senate Democrats\", the image's alt text "
                 "\"Senator J.D. Ford\"",
        "by": "Indiana Senate Democrats",
        "tie": "the IN-5 nominee sits in the Indiana Senate (history: Member of the State "
               "Senate of Indiana since 2018, corroborated), and the legislature roster "
               "(Open States) links this caucus page for him; his card's own route stops "
               "because the legislature's page it links shows no photograph",
        "seen": "a studio portrait, him alone before the state flag",
        "read": "2026-10-25",
    },
    "FEC_H6TN09449": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/3/3d/"
               "Justin_J._Pearson_at_the_White_House.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Justin_J._Pearson_at_the_White_House.jpg",
        "words": "\"Tennessee state representative Justin J. Pearson at the White House, April "
                 "24, 2023\", in Category:Justin J. Pearson; {{PD-USGov-POTUS}}, author "
                 "\"@whitehouse (The White House)\"",
        "tie": "the TN-9 nominee is that representative (history: Member of the Tennessee "
               "House of Representatives since 2023, corroborated); the legislature serves "
               "his photograph only inline, with no file to link",
        "seen": "him alone outside the Eisenhower building, facing the camera",
        "read": "2026-10-25",
    },
    "FEC_H6TN09464": {
        # Brent Taylor, TN-9's Republican nominee. His Commons file was
        # refused (someone else in the frame); the Senate's member page draws
        # his portrait only inline, so it is hosted here unmodified (the PR
        # #141 review: TN-9's Democratic nominee had a photograph and he did
        # not).
        "url": "photos/dc407c55c78c101cce27.png",
        "page": "https://wapp.capitol.tn.gov/apps/LegislatorInfo/member?district=S31",
        "words": "\"Senator Brent Taylor\" heading the page, directly above the photograph "
                 "(alt text \"Photo of Brent Taylor\"), then \"Republican\", \"Memphis\", "
                 "\"District 31\", \"Born on August 9, 1968\"",
        "by": "Tennessee General Assembly",
        "tie": "the article his ballot page links (Brent Taylor (Tennessee politician)) says "
               "he has served since 2023 as a member of the Tennessee Senate representing "
               "District 31, born August 9, 1968, and is a candidate for Tennessee's 9th "
               "district; the roster (Open States) seats Brent Taylor in TN upper 31. The "
               "file is the page's data: image decoded, so it stays his whoever later "
               "holds the seat",
        "seen": "a studio portrait, him alone against a grey backdrop",
        "read": "2026-10-25",
    },
    "FEC_H6AZ05190": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/72/Jay_Feely_2026_%28cropped%29.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Jay_Feely_2026_(cropped).jpg",
        "words": "\"Jay Feely speaking with attendees at the 'Build the Red Wall' rally at Dream "
                 "City Church in Phoenix, Arizona\" (2026-04-17), in Category:Jay Feely; Gage "
                 "Skidmore's photograph, CC BY-SA 4.0",
        "tie": "the AZ-1 nominee, in Phoenix in his campaign's year; the article his ballot "
               "page links (Jay Feely) is his",
        "seen": "him alone at a lectern, microphones at the foot of the frame and nobody else",
        "read": "2026-10-25",
    },
    "FEC_H6CT01206": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/2/2e/Luke_Bronin_%28cropped_3x4%29.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Luke_Bronin_(cropped_3x4).jpg",
        "words": "\"Governor Dannel P. Malloy today joined Hartford Mayor Luke Bronin\" (2018-09-20), "
                 "in Category:Luke Bronin; extracted from the governor's office's Flickr "
                 "photograph, CC BY 2.0",
        "tie": "the CT-1 nominee, Hartford's mayor from 2016 to 2024 (history, corroborated); "
               "the article his ballot page links (Luke Bronin) is his",
        "seen": "him alone, head and shoulders, before a market's banner",
        "read": "2026-10-25",
    },
    "FEC_H6LA05341": {
        "url": "https://house.louisiana.gov/H_Reps/RepPics/rep17.jpg",
        "page": "https://house.louisiana.gov/H_Reps/members?ID=17",
        "words": "'State Representative Patricia \"Pat\" Moore', 'Democrat', 'District 17' "
                 "above the file",
        "by": "Louisiana House of Representatives",
        "tie": "her filed campaign site (patmooreforcongress.com) says \"State Representative, "
               "Louisiana House District 17 since 2019\" and links \"Official Louisiana House "
               "profile\"; its own headshot (refused for the chamber behind her) is the same "
               "woman. The file is keyed by seat, and legphotos withholds it unattended "
               "because its date is a copy's; a person compared the two photographs",
        "seen": "a studio portrait, her alone against a grey backdrop",
        "read": "2026-10-25",
        # rep17.jpg shows whoever holds District 17 (the PR #141 review).
        "seat": {"state": "LA", "chamber": "lower", "district": "17",
                 "legislator": "ocd-person/88548c7a-b637-4821-b336-c99cfa475e22",
                 "name": "Pat Moore"},
    },
    # The photo sweep of 2026-11-17 (the owner's request of 2026-11-15, "lets
    # try and fill those photos and any other missing from non eliminated
    # canidates"): everyone still in view whom every route left with the
    # silhouette - the members-elect, the nominees and Louisiana's qualified
    # candidates awaiting a result - was researched from the pages tied to
    # them (the campaign site their committee filed, or one whose disclaimer
    # names that committee exactly; their legislature's page; the article
    # their ballot page links, and its Commons files). Each photograph here
    # was found by one reader, re-opened and confirmed by a second who read
    # the page and fetched the file again as this project (its bytes, pixel
    # size and sha256 the same), measured on the 4:5 card, and looked at
    # again on a contact sheet; "seen" is the second reader's look. A file
    # over the caps is shown smaller from the same file where its host's
    # resizer or Photon serves it, else as it is, and said
    # (portraits.lighten_curated, rule 87).
    # Jamie Ager
    "FEC_H6NC11248": {
        "url": "https://agerforcongress.com/nitropack_static/nDWggFDzPwYfEWVodLHJgkYjRco"
               "wLtaf/assets/images/optimized/rev-7fa717c/agerforcongress.com/wp-content"
               "/uploads/2025/07/jamie-pigs-768x512.webp",
        "page": "https://agerforcongress.com/about",
        "words": "on \"Meet Jamie Ager | Ager for Congress\", under the heading \"Meet "
                 "Jamie Ager\", the file \"jamie-pigs\" (the srcset's 768px form of "
                 "jamie-pigs.webp; no alt text), directly before \"I know firsthand the "
                 "stress many small business owners and families face - navigating "
                 "health insurance, making payroll, managing cash flow\"",
        "by": "the campaign's website (agerforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "agerforcongress.com), 'Paid for by Ager for Congress' (the FEC "
               "committee exactly), whose home page names him for NC-11 ('Jamie Ager "
               "names bipartisan NC-11 transition committee', 'I'm Jamie Ager. In "
               "Congress, I'm fighting for Appalachian values'); the file names only "
               "his first name, so rule 38's reader could not take it unattended",
        "seen": "Looked at the file, the 960px original and the card: one man, "
                "crouching in a hay barn among pigs, cap with the Hickory Nut Gap farm "
                "badge (the same badge he wears in the Commons delegation crop), red "
                "jacket, smiling at the camera. No person anywhere in the frame; the "
                "small pale shapes by the far windows are animals and hanging gear, not "
                "people. The card's crop keeps his whole face, centred, near the top. "
                "Measured: brow (under the cap's brim) at about y=98, chin at about "
                "y=162 of the 768x512 file: about 64 px against a 51.2 px band, about "
                "1.2 tenths (1.17 tenths on the 960px file: 75 px against 64 px). "
                "Small, but over a tenth.",
        "read": "2026-11-17",
    },
    # Jessica Killin
    "FEC_H6CO05324": {
        "url": "https://run.imgix.net/0cdc1c93-4d9e-4c61-b29f-a8691a56ce6f/18371d67-0344"
               "-4012-bd58-9b91eb195a9c/18371d67-0344-4012-bd58-9b91eb195a9c.jpeg?ixlib="
               "js-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=3256%2C636%2C4018%2C"
               "3903&auto=compress%2Cformat&fit=fillmax&w=640&q=75&s=124e36879db8a6d51a5"
               "621a65c1672bd",
        "page": "https://www.killinforcolorado.com/about",
        "words": "the About page's opening photograph (alt text \"hero image\") under "
                 "\"About Jessica Killin\", on \"About — Jessica Killin for Congress\": \"A "
                 "proud fourth-generation Coloradan, Jessica is a ... Army veteran, and "
                 "public servant running for Congress\" (the srcset's 640px form, signed "
                 "by the site)",
        "by": "the campaign's website (killinforcolorado.com)",
        "tie": "the campaign site her committee filed with the FEC (campaignSite "
               "killinforcolorado.com), 'Paid for by Killin for Colorado' (the FEC "
               "committee exactly); the pages name her running for Congress in "
               "Colorado ('Fighting for Colorado', 'Raised in Colorado Springs', 'the "
               "places that make Southern Colorado special') though not the district "
               "number; the file names no one, so rule 38's reader could not take it "
               "unattended",
        "seen": "Looked at the card and the whole file: one woman, alone, red jacket "
                "over a white top, arms folded, smiling at the camera, Pikes Peak and "
                "Colorado Springs behind and a stone wall below. Nobody else anywhere "
                "in the frame. A posed professional portrait; the card keeps her whole "
                "face, centred. Measured: card: brow at about band 2.05, chin at about "
                "band 3.4, about 1.35 tenths (whole file: about 87 px brow to chin "
                "against a 62.2 px band, 1.4 tenths)",
        "read": "2026-11-17",
    },
    # Bob Brooks
    "FEC_H6PA07188": {
        "url": "https://www.brooksforcongress.com/wp-content/uploads/2026/07/1326-JR3B54"
               "01-scaled.jpg",
        "page": "https://www.brooksforcongress.com/",
        "words": "the image's alt text \"Bob Brooks petting his bulldog\" (on the Meet Bob "
                 "page the same file is \"Bob Brooks petting Aspen, the family bulldog\"), "
                 "on \"Bob Brooks for Congress | Put the fire out in Washington\"",
        "by": "the campaign's website (brooksforcongress.com)",
        "tie": "route 1(b): no site is on his filing or ballot page; a web search led "
               "to brooksforcongress.com (the IAFF's announcement of his run names "
               "it), whose footer reads 'PAID FOR BY BOB BROOKS FOR CONGRESS', his "
               "principal campaign committee exactly as the FEC registers it, and "
               "which names this race ('Bob Brooks for Pennsylvania's 7th "
               "Congressional District', 'Firefighter Bob Brooks Declares Victory in "
               "PA-07 Congressional Race', Nov 3, 2026)",
        "seen": "Looked at the whole file and the card: one bald, grey-bearded man, "
                "crouching by a stone fireplace in a red 'Pennsylvania Professional "
                "Firefighters Association' T-shirt (the union he presides over, as the "
                "page says), petting a bulldog on a dog bed. Nobody else anywhere in "
                "the frame; no screen, no picture of a person. His face is in "
                "three-quarter view looking down-left at the dog, eyes, nose and mouth "
                "plain. Wider than tall; the card keeps him whole-faced at its top "
                "right. Measured: brow at about y=211, chin at about y=435 of the "
                "2560x1707 file: about 224 px against a 170.7 px band, about 1.3 tenths "
                "(card: brow near band 1.4, chin near band 2.6)",
        "read": "2026-11-17",
    },
    # Scott Colom
    "CAND_39": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/f/f2/Scott_Colom_2_%28cro"
               "pped%29.png",
        "page": "https://commons.wikimedia.org/wiki/File:Scott_Colom_2_(cropped).png",
        "words": "\"Scott Colom is the 2026 Democratic nominee for U.S. Senate in "
                 "Mississippi\" (the file's description), File:Scott Colom 2 "
                 "(cropped).png, in Category:Scott Colom and the lead image of the "
                 "article Scott Colom; CC BY 4.0, author \"The Contrarian\", dated "
                 "2026-10-12, source named as the video \"Can a Democrat win in "
                 "Mississippi? (w/ Scott Colom)\"",
        "tie": "route (c): the article his ballot page links (Scott Colom, "
               "wikipediaVia election-page; item Q115492489, whose Commons sitelink is "
               "Category:Scott Colom) shows this file as its lead; his campaign site "
               "scottcolom.com ('Paid for by Scott Colom for Senate') names him as the "
               "district attorney running for the U.S. Senate in Mississippi",
        "seen": "Looked at the card and whole file: one man, head and shoulders, bald, "
                "short grey beard, blue jacket, open white shirt, a small "
                "U.S./Mississippi flag pin, facing the camera mid-sentence; behind him "
                "a bookshelf and framed photographs of people (pictures, not people in "
                "the frame, which the standard allows); nobody else, no screen. A video "
                "frame, a little soft, but a plain likeness. Measured: card: brow "
                "(eyebrows) at about band 3.1, chin at about band 7.0: about 3.9 tenths "
                "(the first reader said 4.3; either way far over a tenth)",
        "read": "2026-11-17",
    },
    # Brian Poindexter
    "FEC_H6OH07168": {
        "url": "https://poindexterforcongress.com/wp-content/uploads/2025/12/bp-hardhat-"
               "4-5-1024x819.jpg",
        "page": "https://poindexterforcongress.com/",
        "words": "on \"Brian Poindexter for Congress | Ready to Work for Working "
                 "Families\", under \"Ready to work for working families in congress\" and "
                 "directly before \"Why I'm Running for Congress: When times get tough, "
                 "working people are always asked to do more with less\"; the file is "
                 "\"bp-hardhat-4-5\" (his initials; the srcset's 1024px form; no alt text)",
        "by": "the campaign's website (poindexterforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "poindexterforcongress.com), 'Paid for by Poindexter for Congress' (the "
               "FEC committee exactly), which names this race: 'Ready to Work for "
               "Working Families in ohio's 7th congressional district'; the same "
               "photograph, same hard hat and sweatshirt, heads its share card beside "
               "'BRIAN POINDEXTER Working class values for Ohio's 7th Congressional "
               "District'; the file names only his initials, so rule 38's reader could "
               "not take it unattended",
        "seen": "Looked at the file and the card: one man, alone, in a sticker-covered "
                "ironworker's hard hat and a navy 'West Side Warriors' hoodie, arms "
                "folded, looking at the camera, an empty industrial lot blurred behind; "
                "nobody else anywhere in the frame. The same face as the man at the "
                "lectern in the Commons victory photograph of him and as the share card "
                "bp-og.jpg, where this very photograph stands beside 'BRIAN POINDEXTER "
                "Working class values for Ohio's 7th Congressional District'. The card "
                "keeps his whole face. Measured: brow (under the hat's brim) at about "
                "y=255, chin at about y=395 of the 1024x819 file: about 140 px against "
                "an 81.9 px band, about 1.7 tenths (card: brow near band 3.0, chin near "
                "band 4.8)",
        "read": "2026-11-17",
    },
    # Bob Harvie
    "FEC_H6PA01181": {
        "url": "https://bobharvieforcongress.com/wp-content/uploads/2026/08/harvie_redsh"
               "irt_squ.jpg",
        "page": "https://bobharvieforcongress.com/",
        "words": "the file \"harvie_redshirt_squ.jpg\" (alt text "
                 "\"Copyright©gerrihernandez\", the photographer's credit), directly above "
                 "\"About Bob\": \"Bob Harvie was elected to the Board of Bucks County "
                 "Commissioners in November 2019\", on \"Home - Bob Harvie for Congress\"",
        "by": "the campaign's website (bobharvieforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "bobharvieforcongress.com), 'Paid for by Bob Harvie For Congress ... PO "
               "Box 67 Langhorne, PA 19047' (the FEC committee exactly), naming him as "
               "the Bucks County commissioner running for Congress (PA-1 is Bucks "
               "County); the file is square, so rule 38's shape test (taller than "
               "wide, unless named a headshot) kept the pipeline from taking it",
        "seen": "Looked at the whole file, the card and three enlarged crops of its "
                "edges: one man, grey hair, red polo shirt, arms folded, smiling at the "
                "camera on a tree-lined street, a U.S. flag and a porch blurred at the "
                "left, a tree trunk at the right. The narrow gap between his right "
                "elbow and the tree trunk holds a featureless dark-and-grey blur (no "
                "skin tone, no head or limb above it: foliage above), and the left edge "
                "a thin dark vertical by a porch column; neither is a person that can "
                "be made out (the Jill Barry precedent of rule 38), so nobody else is "
                "in the frame. The same man as the campaign's share card "
                "bobharvie_OG.png, which names him 'Bob Harvie FOR CONGRESS'. Square; "
                "the card keeps him whole. Measured: brow at about y=430, chin at about "
                "y=790 of the 2180x2181 file: about 360 px against a 218.1 px band, "
                "about 1.65 tenths (card: brow near band 1.5, chin near band 3.15)",
        "read": "2026-11-17",
    },
    # Charlie Hatcher
    "FEC_H6TN05405": {
        "url": "https://charliehatcher.com/wp-content/uploads/2026/08/133-EXTRA_Portrait"
               "-of-Charlie-CU-2-scaled.png",
        "page": "https://charliehatcher.com/about/",
        "words": "the file \"133-EXTRA_Portrait-of-Charlie-CU-2-scaled.png\", a background "
                 "picture of the page \"About – Charlie Hatcher\" (no alt text), whose "
                 "words open \"ABOUT CHARLIE ... Charlie Hatcher is a farmer, "
                 "veterinarian, businessman, and public servant\"",
        "by": "the campaign's website (charliehatcher.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "charliehatcher.com), 'Paid for by Charlie Hatcher for Congress' (the "
               "FEC committee exactly), whose home page names this race: 'Now Doc "
               "Hatcher's running for Congress TN CD 5'; the file names only his first "
               "name, as a portrait, so rule 38's reader (which wants the surname, or "
               "the first name with 'headshot', 'portrait' or 'profile' only on that "
               "narrow, looked-at route) did not take it",
        "seen": "Looked at the card and the whole file: a close-up of one man alone, "
                "dark cap, grey work shirt, looking just past the camera, lit from the "
                "left, barn slats and light behind. Nobody else anywhere in the frame. "
                "The same lean face as the man on the home page's hero "
                "hatcher-hero-img.jpeg, who wears a 'HATCHER FAMILY DAIRY' cap. The "
                "card keeps his whole face (cap crown cut). Measured: card: brow at "
                "about band 2.0, chin at about band 5.2: about 3.2 tenths (one band = "
                "143.9 source px)",
        "read": "2026-11-17",
    },
    # Don Ralph Leonard
    "FEC_H6OH15112": {
        "url": "https://images.squarespace-cdn.com/content/v1/687eb236d4e3d45f11da2aa6/b"
               "53dd593-9c08-4fd4-8192-f41c2b4977cb/DSC02163.jpg?format=1000w",
        "page": "https://donforohio.com/bio",
        "words": "on \"Bio — Don Leonard for US Congress\", under \"Meet Don Leonard\", the "
                 "photograph directly before \"My name is Don Leonard, and I am running "
                 "to represent everyone in Ohio's 15th Congressional District\" (file "
                 "DSC02163.jpg, no alt text; the srcset's 1000w form, on the site "
                 "builder's CDN)",
        "by": "the campaign's website (donforohio.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "donforohio.com, also the site the election page lists), 'paid for by "
               "Don Leonard for Ohio' (the FEC committee exactly), which names this "
               "race in the words beside the photograph; the file carries no name, so "
               "rule 38's reader could not take it unattended",
        "seen": "Looked at the card and the whole file: one man, alone, dark hair, "
                "short beard, navy shirt, one hand in a pocket, looking at the camera "
                "on a wooded path; nobody else anywhere in the frame. The same man as "
                "in the page's 'fatherhood' collage, which the first-person text beside "
                "it ('My daughter was born at OSU Hospital') makes his. Wider than "
                "tall: the card keeps his whole face at its right edge (body and arm "
                "cut there), the rest of the card foliage. Measured: card: brow at "
                "about band 2.2, chin at about band 3.35: about 1.15 tenths (one band = "
                "75 source px; about 87 px brow to chin)",
        "read": "2026-11-17",
    },
    # Chris Gober
    "FEC_H6TX10221": {
        "url": "https://framerusercontent.com/images/qcPVXzbsxz7ZpcrGPh6h7i7N4.jpg?scale"
               "-down-to=512&lossless=1&width=5472&height=3648",
        "page": "https://chrisgober.com/",
        "words": "on \"Chris Gober\" (\"Chris Gober Running for Congress to represent "
                 "Texas's 10th District\"), the photograph directly before the section "
                 "\"Meet Chris Gober\": \"Chris Gober is a seventh-generation Texan, proud "
                 "Texas A&M Aggie, husband of 18 years, and father to two ...\" (its alt "
                 "text is the site template's placeholder \"Photo-of-the-Designer\"; the "
                 "srcset's 512px form)",
        "by": "the campaign's website (chrisgober.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "chrisgober.com), 'Paid for by Chris Gober for Texas' (the FEC "
               "committee exactly), which names this race ('Running for Congress to "
               "represent Texas's 10th District', 'TX-10', 'Election Day Tuesday, "
               "November 3, 2026'); the image carries no name of his, so rule 38's "
               "reader could not take it unattended",
        "seen": "Looked at the card and the whole file: one man, alone, dark maroon "
                "shirt, hands in pockets, smiling at the camera before dark foliage and "
                "yellow wildflowers; nobody else in the frame. DOUBT I CHECKED: the "
                "site is a Framer template that still carries the template's own images "
                "(a robot, a sci-fi astronaut, a 'Supra smart solar energy' phone "
                "mock-up, a laptop) and both photographs of this man keep the "
                "template's placeholder alts ('Photo-of-the-Designer', 'Phiotographer "
                "looking at the camera'), so the man could have been the template's "
                "stock model. He is not: the Federalist Society's bio page for Chris "
                "Gober ('Gober is a 7th-generation Texan', 'General Counsel to the "
                "Republican Party of Texas'; headshot alt 'Chris Gober') shows the same "
                "man - long face, swept dark hair, the same broad smile - and the "
                "campaign's own text beside the photograph calls him a "
                "seventh-generation Texan too. That headshot was downloaded only to "
                "compare faces (img/b01/fec-h6tx10221/11-64732a24c6fc.jpg), never to be "
                "offered. The card keeps his whole face, centred. Measured: card: brow "
                "at about band 1.55, chin at about band 2.95: about 1.4 tenths (one "
                "band = 34.1 source px)",
        "read": "2026-11-17",
    },
    # Paul Barringer
    "FEC_H6NC13228": {
        "url": "https://paulbarringer.com/wp-content/uploads/2026/01/Paul-Barringer2025-"
               "12-23-6360-400x500.webp",
        "page": "https://paulbarringer.com/",
        "words": "the home page's first image, file name "
                 "\"Paul-Barringer2025-12-23-6360.webp\" (srcset 400w form), above the "
                 "heading \"Common sense. North Carolina values. Paul Barringer, Democrat "
                 "for Congress.\"",
        "by": "the campaign's website (paulbarringer.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(www.paulbarringer.com, which redirects to paulbarringer.com); the "
               "page says he is \"running for Congress in NC's 13th Congressional "
               "District\" and its disclaimer reads \"PAID FOR BY PAUL BARRINGER FOR "
               "CONGRESS\", the FEC committee's exact name",
        "seen": "Looked at the file and the card: one man, grey hair, smiling, olive "
                "waxed jacket over a checked shirt, hands in pockets, in a winter field "
                "before bare trees. Nobody else anywhere in the file; the card keeps "
                "the whole file. Measured: On the card picture brow at about band 2.4, "
                "chin at about band 3.7: about 1.3-1.4 tenths (about 68 px of the 500 "
                "px file against a 50 px band).",
        "read": "2026-11-17",
    },
    # Wes Climer
    "FEC_H6SC05202": {
        "url": "https://wesclimer.com/wp-content/uploads/2025/08/P1027884-scaled-e175639"
               "2467361-768x925.jpg",
        "page": "https://wesclimer.com/about/",
        "words": "the About page's only portrait, in the section headed \"Meet wes "
                 "climer\", beside \"Wes Climer is a husband, father of five, business "
                 "owner and public servant ... now representing York County in the State "
                 "Senate\" and \"Now he's running for Congress because the job isn't done\" "
                 "(srcset 768w form)",
        "by": "the campaign's website (wesclimer.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(www.wesclimer.com); its disclaimer reads \"Paid for by Climer for "
               "Congress\", the FEC committee's exact name, and the About page says he "
               "is running \"for the people of South Carolina's 5th Congressional "
               "District\"; the same man stands at the right of the home page's family "
               "photograph under \"About Wes Climer\"",
        "seen": "Looked at both files and both cards: the same photograph pixel for "
                "pixel to the eye - one man in a navy suit, white shirt and red tie "
                "before a red brick wall, smiling; nobody else in the frame. The About "
                "page read fresh still draws this address (renditions 249w, 768w, 850w, "
                "1195w listed; 768w within the caps). Measured: On the card picture "
                "brow at about band 2.0, chin at about band 3.8: about 1.8 tenths "
                "(about 165 px against a 92.5 px band).",
        "read": "2026-11-17",
    },
    # Kristina Knickerbocker
    "FEC_H6OH10121": {
        "url": "https://kristinaknickerbocker.com/wp-content/themes/blueprintinteractive"
               "/images/meet_cutout.png",
        "page": "https://kristinaknickerbocker.com/meet-kristina/",
        "words": "the \"Meet Kristina\" page's hero image (alt text \"Meet Page Hero "
                 "Image\", file \"meet_cutout.png\"), under the heading \"A Life Dedicated "
                 "to Service\" and directly before \"U.S. Air Force Veteran, Oncology "
                 "Nurse Practitioner, and mom of two - Kristina Knickerbocker's life has "
                 "been dedicated to serving our country and our community\"; her white "
                 "coat is embroidered \"Kristina Knickerbocker MS, APRN-CNP\"",
        "by": "the campaign's website (kristinaknickerbocker.com)",
        "tie": "the campaign site her committee filed with the FEC "
               "(kristinaknickerbocker.com); its disclaimer reads \"Paid for By "
               "Knickerbocker for Congress\", the FEC committee's exact name, and it "
               "gives the campaign's Dayton, Ohio address (OH-10); the page is the "
               "site's About page",
        "seen": "Looked at the file and the card: a studio cut-out of one woman, long "
                "fair hair, white coat embroidered 'Kristina Knickerbocker MS, "
                "APRN-CNP' over a navy top, stethoscope round her neck, on a plain "
                "light grey ground. Nobody else anywhere; the card keeps her whole "
                "head. Measured: On the card picture brow at about band 2.0, chin at "
                "about band 3.8: about 1.8 tenths (about 235 px against a 129.6 px "
                "band).",
        "read": "2026-11-17",
    },
    # Ryan Elijah
    "FEC_H6FL07231": {
        "url": "https://www.elijahforcongress.com/assets/img/hero-ryan-headshot.jpg",
        "page": "https://www.elijahforcongress.com",
        "words": "the home page's first image, alt text \"Ryan Elijah, candidate for "
                 "Congress in Florida's 7th District\", file name "
                 "\"hero-ryan-headshot.jpg\"",
        "by": "the campaign's website (elijahforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(www.elijahforcongress.com); titled \"Ryan Elijah for Congress - "
               "Florida's 7th Congressional District\", it says he \"is running for "
               "Congress in Florida's 7th District\" and gives \"Election Day Tuesday, "
               "November 3, 2026\"; its disclaimer reads \"Paid for by Ryan Elijah for "
               "Congress\", the FEC committee's exact name",
        "seen": "Looked at the whole file: one man in a navy suit, striped red and "
                "white tie, flag pin and red pocket square, before two palm trunks, sky "
                "and water. The pale shapes at the lower left are a white railing by "
                "the water, not a person. Nobody else in the frame. Measured: On the "
                "card picture brow at about band 4.5, chin at about band 6.4: about 1.9 "
                "tenths (about 310 px of the file against a 166.8 px band).",
        "read": "2026-11-17",
    },
    # Angela Gonzales-Torres
    "FEC_H6CA34286": {
        "url": "https://run.imgix.net/06be24b2-0f79-4e8b-946c-e788fb89576f/134d35b9-7cff"
               "-4c3f-a6e3-153a3ab62b30/134d35b9-7cff-4c3f-a6e3-153a3ab62b30.jpg?ixlib=j"
               "s-3.8.0&bri=4&con=0&sat=0&high=0&shad=0&usm=25&rect=482%2C0%2C2036%2C203"
               "6&auto=compress%2Cformat&fit=fillmax&w=640&q=75&s=8101cd6eab2cc2f88d70dc"
               "b773dc2841",
        "page": "https://www.angela4congress.com/about",
        "words": "the About page's hero image (alt text \"hero image\", the srcset's 640w "
                 "form, signed by the site's image host), under the heading \"Rooted in "
                 "LA. Ready for change.\" and directly before \"Angela Gonzales-Torres is "
                 "a democratic socialist running to represent California's 34th "
                 "Congressional District.\"",
        "by": "the campaign's website (angela4congress.com)",
        "tie": "the campaign site her committee filed with the FEC "
               "(www.angela4congress.com), titled \"Angela Gonzales-Torres for "
               "Congress\"; its About page names her race, California's 34th "
               "Congressional District (CA-34); disclaimer \"Paid for by Angela for "
               "CA-34\" (the FEC registers \"ANGELA FOR CA34\")",
        "seen": "Looked at the card and whole file: one young woman with long dark "
                "hair, hoop earring, navy crew-neck sweater, shot from below against "
                "blue sky and a white building with barred windows. Nobody else in the "
                "frame. Same woman as the Commons lead File:Angela Gonzales-Torres.jpg "
                "(same hoops and blue sweater), which is a licence doubt and was "
                "rightly not offered. Measured: On the card picture brow at about band "
                "3.7, chin at about band 5.9: about 2.2 tenths.",
        "read": "2026-11-17",
    },
    # Cyril Jefferson
    "FEC_H6NC06164": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/6/61/US_Representative_Cy"
               "ril_Jefferson.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:US_Representative_Cyril_Jefferso"
                "n.jpg",
        "words": "\"US Representative Cyril Jefferson\" (the file page's description), in "
                 "Category:Cyril Jefferson; the lead image of the article Cyril "
                 "Jefferson; author \"Ike Hayman, House Creative Services\", public domain "
                 "(PD-USGov), dated November 9, 2026",
        "tie": "route (c): the article NC-6's election page links for him (Cyril "
               "Jefferson, item Q124332362, wikipediaVia election-page) shows this "
               "file as its lead, and the file is in the person's own Commons category "
               "(the item's Commons sitelink); his campaign site "
               "(cyrilforcongress.com) names him as the NC-6 candidate",
        "seen": "Looked at the file: a studio official portrait of one man, short "
                "beard, dark suit, striped tie, a round lapel pin, before a U.S. flag "
                "and dark blue backdrop. Nobody else. I also fetched his own category's "
                "(Jefferson-cropped) crop of the NC Democratic delegation photograph "
                "(Office of Rep. Deborah Ross, November 2026): the same man, wearing "
                "the same lapel pin. Measured: On the card picture brow at about band "
                "2.7, chin at about band 5.2: about 2.5 tenths.",
        "read": "2026-11-17",
    },
    # Shawn Harris
    "FEC_H4GA14057": {
        "url": "https://www.shawnforgeorgia.com/html/assets/photos/Porch-alone-side.JPG."
               "jpg",
        "page": "https://www.shawnforgeorgia.com/",
        "words": "alt text \"Shawn Harris seated on a porch in Georgia\", file name "
                 "\"Porch-alone-side.JPG.jpg\", on the home page titled \"Shawn Harris for "
                 "Georgia | Democrat for Georgia's 14th District\"",
        "by": "the campaign's website (shawnforgeorgia.com)",
        "tie": "the campaign site GA-14's election page lists for him "
               "(electionPageSite https://www.shawnforgeorgia.com/, the work list's "
               "campaignSite via election-page); the site names him \"Democrat for "
               "Georgia's 14th District\" and \"Retired Brigadier General\", the GA-14 "
               "Democratic nominee; its disclaimer reads \"PAID FOR BY SHAWN FOR "
               "GEORGIA\" (the FEC registers SHAWN HARRIS FOR CONGRESS), so this rests "
               "on the election page's link, not on 1(b)",
        "seen": "Looked at the whole file and a 1:1 crop of the door: one man, bald, "
                "glasses, checked shirt and jeans, seated on stone porch steps, hands "
                "steepled; behind him a front door, sidelights, chairs, a porch swing "
                "and a plant. The door's glass reflects only foliage and sky. Nobody "
                "else anywhere. Wider than tall; the card keeps him whole-faced at its "
                "centre and cuts the chairs. Measured: Brow at about y 415, chin at "
                "about y 590 of the 1333 px file: about 175 px against a 133.3 px band, "
                "about 1.3 tenths (on the card picture band 3.0 to 4.3).",
        "read": "2026-11-17",
    },
    # John Cowan
    "FEC_H0GA14048": {
        "url": "https://cowanforcongress.com/images/Cowanscrubs.png",
        "page": "https://cowanforcongress.com",
        "words": "the home page's first image, alt text \"Dr. John Cowan\", file name "
                 "\"Cowanscrubs.png\", followed by \"I'm Dr. John Cowan - As a doctor and a "
                 "small business owner...\"; his white coat is embroidered \"John A. "
                 "Cowan, Jr. MD Neurosurgery\"",
        "by": "the campaign's website (cowanforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(cowanforcongress.com); its disclaimer reads \"Paid for by Friends of "
               "John Cowan\", the FEC committee's exact name, and the same site's Meet "
               "page (https://cowanforcongress.com/meet-dr-cowan.html) says \"Dr. Cowan "
               "is running for Congress\" and has \"spent decades caring for patients "
               "across Georgia's 11th District\"; the Meet page's own portrait "
               "(cowan12.png, alt \"Dr. John Cowan\") shows the same man",
        "seen": "Looked at the file and card: one man, dark hair, looking off to his "
                "left, white coat embroidered 'John A. Cowan, Jr. MD Neurosurgery' over "
                "teal scrubs, against a pale blurred background. Nobody else in the "
                "frame; the card keeps his whole head. Measured: On the card picture "
                "brow at about band 2.4, chin at about band 4.0: about 1.6 tenths.",
        "read": "2026-11-17",
    },
    # Carlos de la Cruz Jr.
    "FEC_H6TX35087": {
        "url": "https://static.wixstatic.com/media/34bf2f_571e35cfe9664926bcf5582cad2621"
               "e7~mv2.jpg/v1/crop/x_0,y_47,w_1191,h_1097/fill/w_554,h_510,al_c,q_80,usm"
               "_0.66_1.00_0.01,enc_avif,quality_auto/photo%20sep%2025%202025%2C%208%202"
               "1%2046%20am%20(10)_edite.jpg",
        "page": "https://www.carlosforcongress.com",
        "words": "the photograph in the home page's section headed \"Air Force Veteran & "
                 "Political Outsider | CARLOS | DE LA CRUZ\", directly after \"Carlos "
                 "served 20 years in the U.S. Air Force ... Carlos has spent his life "
                 "delivering results\" (file \"photo sep 25 2025, 8 21 46 am "
                 "(10)_edite.jpg\", the rendition the page draws, 554x510)",
        "by": "the campaign's website (carlosforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(www.carlosforcongress.com), titled \"Carlos De La Cruz for Congress\", "
               "\"Support a Texas CONSERVATIVE\", address Universal City, Texas; its "
               "disclaimer reads \"PAID FOR BY CARLOS FOR CONGRESS\", the FEC "
               "committee's exact name; the same man is at the centre of the site's "
               "own banner beside \"CARLOS DE LA CRUZ FOR CONGRESS\" (the site does not "
               "print the district number)",
        "seen": "Looked at the card and whole file: one man, dark short hair, navy "
                "blazer over an open white shirt, before a U.S. flag, trees and roofs. "
                "Nobody else in the frame; slightly wider than tall, the card keeps him "
                "whole. Measured: On the card picture brow at about band 2.0, chin at "
                "about band 3.9: about 1.9 tenths.",
        "read": "2026-11-17",
    },
    # Anthony Lawrence Kozycki
    "FEC_H6GA07221": {
        "url": "https://kozyckiforcongress.com/img/Tony_Kozycki_7115_Wide.jpg",
        "page": "https://kozyckiforcongress.com",
        "words": "alt text \"Tony Kozycki - International Diplomacy\", file name "
                 "\"Tony_Kozycki_7115_Wide.jpg\", in the section \"Service in Defense of "
                 "this Nation\" before \"Working with Allies, Strengthening Security\"",
        "by": "the campaign's website (kozyckiforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(kozyckiforcongress.com), titled \"Tony Kozycki for Congress | "
               "Georgia's 7th District\", which says \"Tony Kozycki is a Democrat "
               "runni[ng]\" for that district; disclaimer \"Paid for by Kozycki for "
               "Congress\", the FEC committee's exact name (the FEC files him as "
               "KOZYCKI, ANTHONY LAWRENCE; the site uses Tony with the same surname)",
        "seen": "Looked at the file and card: a studio portrait of one man in a green "
                "flight jacket with squadron patches over a grey T-shirt, plain grey "
                "backdrop. Nobody else. Measured: On the card picture brow at about "
                "band 1.9, chin at about band 3.7: about 1.8 tenths.",
        "read": "2026-11-17",
    },
    # Kimberly Hardy
    "FEC_H6NC07196": {
        "url": "https://images.squarespace-cdn.com/content/v1/685d6ecae0e5cc62fa1d93ac/1"
               "627beeb-f441-49f8-a735-a35d0e692ba6/Transparent+Background.png?format=50"
               "0w",
        "page": "https://www.kimberlyhardyforcongress.com/",
        "words": "alt text \"Dr. Kimberly Hardy\" (file \"Transparent+Background.png\", "
                 "Squarespace's 500w form) on the home page titled \"Kimberly Hardy for "
                 "US Congress\"",
        "by": "the campaign's website (kimberlyhardyforcongress.com)",
        "tie": "the campaign site her committee filed with the FEC "
               "(kimberlyhardyforcongress.com, now www.); it says \"Kimberly Hardy is "
               "running for Congress in North Carolina\", its About page \"...North "
               "Carolina's 7th district in Congress\", and its disclaimer reads \"Paid "
               "for by Kimberly Hardy for Congress\", the FEC committee's exact name "
               "(the FEC files her as HARDY, KIMBERLY DR.)",
        "seen": "Looked at the file and card: a studio portrait of one woman, long dark "
                "hair, glasses, smiling, patterned keyhole-neck dress, plain light grey "
                "ground. Nobody else. Measured: On the card picture brow at about band "
                "1.8, chin at about band 4.3: about 2.5 tenths.",
        "read": "2026-11-17",
    },
    # Jace Yarbrough
    "FEC_H6TX32225": {
        "url": "https://cdn.prod.website-files.com/693c3a90305739817374e10a/693c42031c56"
               "573a565aaddf_5P7A0044%20(1)-p-800.jpg",
        "page": "https://www.jaceforcongress.com/media-kit",
        "words": "alt text \"Jace Yarbrough wearing blue suit.\" on the campaign's \"Media "
                 "Kit - Jace Yarbrough for Congress\" page (the srcset's 800w form of "
                 "5P7A0044)",
        "by": "the campaign's website (jaceforcongress.com)",
        "tie": "route 1(b): no site is filed in the work list; jaceyarbrough.com "
               "redirects to www.jaceforcongress.com, whose disclaimer reads \"Paid for "
               "by Jace Yarbrough for Congress PO BOX 1102, Rockwall TX 75087\", the "
               "FEC committee's exact name (C00930297), and whose home page says he is "
               "\"fighting for Texas' 32nd district\"",
        "seen": "Looked at the whole file and 3x crops of both sides: one man, beard, "
                "blue blazer, white shirt, flag pin, hands in pockets, on a gravel lane "
                "between wooden fences and trees; the red shape far behind on the right "
                "is a small structure, the lamps are on the gate posts. Nobody else. "
                "Wider than tall; the card keeps him whole-faced at its centre. "
                "Measured: Brow at about y 135, chin at about y 228 of the 578 px file: "
                "about 93 px against a 57.8 px band, about 1.6 tenths.",
        "read": "2026-11-17",
    },
    # Tom Sell
    "FEC_H6TX19206": {
        "url": "https://www.selltexastrue.com/tom-sell-cattle.jpg",
        "page": "https://www.selltexastrue.com/",
        "words": "file name \"tom-sell-cattle.jpg\" (alt text \"West Texas landscape "
                 "background\"), the home page's first image, in the section \"Tom Sell "
                 "for Texas\": \"West Texas is home - it's where my roots run deep\"; the "
                 "page is titled \"Conservative Tom Sell - Standing Up For West Texas "
                 "Values. Running for Congress\"",
        "by": "the campaign's website (selltexastrue.com)",
        "tie": "route 1(b): no site in the work list; a news page (KACU) led to "
               "www.selltexastrue.com, whose disclaimer reads \"Paid for by "
               "Conservative Tom Sell for Congress\", the FEC committee's exact name "
               "(C00926345); it says he is \"Running for Congress\" in West Texas with "
               "\"Election Day: November 3\", and its About page names his work for "
               "\"Congressman Larry Combest (R-TX19)\"; the same man stands at the "
               "centre of the site's family photograph \"Tom Sell and his family\"",
        "seen": "Looked at the whole file: one man in a cream cowboy hat, waxed tan "
                "jacket, green vest and blue shirt among red cattle in haze. No other "
                "person anywhere. He is the man at the centre of the site's 'Tom Sell "
                "and his family' photograph (same hat, jacket and vest). Wider than "
                "tall; the card's crop (x 373-1227) keeps him whole-faced at its left. "
                "Measured: Brow (under the brim) at about y 325, chin at about y 450 of "
                "the 1067 px file: about 125 px against a 106.7 px band, about 1.2 "
                "tenths. It stands ahead of his article's lead, File:Tom Sell "
                "119th-120th Congress Veterans Day tribute (cropped).jpg (207x232), a "
                "crop of a group photograph nobody had looked at.",
        "read": "2026-11-17",
    },
    # Chuck Hubbard
    "FEC_H4NC05294": {
        "url": "https://hubbardforcongress.com/wp-content/uploads/2024/04/chuckatappstat"
               "e-683x1024.webp",
        "page": "https://hubbardforcongress.com/about",
        "words": "the About page's photograph (file \"chuckatappstate-683x1024.webp\"), "
                 "directly above the heading \"About Chuck Hubbard\" and \"Meet your "
                 "candidate for Congress, Chuck Hubbard\", on the page titled \"Meet Chuck "
                 "Hubbard - Chuck Hubbard for Congress\"",
        "by": "the campaign's website (hubbardforcongress.com)",
        "tie": "route 1(b): no site in the work list; a web search led to "
               "hubbardforcongress.com, whose disclaimer reads \"Paid for by Chuck "
               "Hubbard for Congress\", the FEC committee's exact name (C00841874); the "
               "site says \"Chuck is running to represent our community in Congress\", "
               "names \"The 5th District\" and Virginia Foxx (NC-5's incumbent) and "
               "Wilkes County, North Carolina; it prints no year, and its files date "
               "from April 2024 (his first run against Foxx, under the same "
               "committee); the man is the same as in the NC Democratic delegation "
               "crop in his own Commons category",
        "seen": "Looked at the whole file and 2-3x crops of both lower corners: one "
                "bald man in a light blue shirt before trees and the App State clock "
                "tower; at the lower right only benches and steps, at the left a brick "
                "building and shrubs. Nobody else. Same man (same shirt) as the site's "
                "street hero image. Measured: Brow at about y 340, chin at about y 520 "
                "of the 1024 px file: about 180 px against an 85.4 px band, about 2.1 "
                "tenths.",
        "read": "2026-11-17",
    },
    # Maura Keller
    "FEC_H4GA03100": {
        "url": "https://images.squarespace-cdn.com/content/v1/65babf991018d92de237b77e/3"
               "7086b63-ea7e-4136-b2f7-12db3be71528/MK+Homepage+Gold+Border+Square+Heads"
               "hot.jpg?format=500w",
        "page": "https://maurakeller.com/",
        "words": "the file name \"MK Homepage Gold Border Square Headshot.jpg\" (her "
                 "initials and \"Headshot\"; no alt text), on the home page titled \"Maura "
                 "Keller for Congress | US Army Veteran and VA Health Worker\" (the 500w "
                 "rendition its srcset lists)",
        "by": "the campaign's website (maurakeller.com)",
        "tie": "the campaign site her committee filed with the FEC "
               "(www.maurakeller.com, ending at maurakeller.com); the page is \"Paid "
               "for by Maura Keller for Congress\" (the FEC committee exactly) and says "
               "she is \"committed to serving the people of Georgia's 3rd Congressional "
               "District\", running \"first in 2024 and again in 2026\". The file names "
               "her initials, not her surname, so rule 38's reader could not take it "
               "unattended: the same woman, in the same blue blazer, is the site's "
               "file \"Maura Keller 2026 Web Background Homepage.jpg\", and wears a "
               "\"MAURA KELLER US CONGRESS GA CD 3\" shirt in \"Maura Keller Web Square "
               "09.jpg\" on the same page",
        "seen": "Looked at the file and card: one woman, shoulder-length light brown "
                "hair, smiling, grey-blue blazer over white top, blurred US flag left "
                "and grey backdrop, thin gold border; nobody else in the frame, the "
                "card keeps her whole face. Same woman as the site's own named files "
                "'Maura Keller 2026 Web Background Homepage.jpg' (same blue blazer, "
                "seated outdoors) and 'Maura Keller Web Square 09.jpg' (in a 'MAURA "
                "KELLER US CONGRESS GA CD 3' shirt), which I looked at. Measured: On "
                "the card brow at about band 2.6, chin at about band 5.2: about 2.6 "
                "tenths (one band = 50 source px).",
        "read": "2026-11-17",
    },
    # Chris Harden
    "FEC_H6GA11116": {
        "url": "https://static.wixstatic.com/media/17a715_318a9891ee8b44f38b32442ae7bb0b"
               "8e~mv2.jpg/v1/fill/w_440,h_550,al_c,q_80,usm_0.66_1.00_0.01,enc_avif,qua"
               "lity_auto/Chris-Harden-Headshot.jpg",
        "page": "https://www.electharden.com/",
        "words": "the home page's first image, file name \"Chris-Harden-Headshot.jpg\", "
                 "alt text \"Professional headshot of Chris Harden in dark suit and light "
                 "blue tie sitting on stool against dark studio background\" (the page "
                 "draws it at 147x184 through Wix's own resizer, "
                 ".../v1/fill/w_147,h_184,...; this is the same file through the same "
                 "resizer at 440x550, since 147px is too small for the card)",
        "by": "the campaign's website (electharden.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(www.chrishardenforcongress.com) now leads to electharden.com, which "
               "enrich read as still naming him; the page is titled \"Chris Harden for "
               "Congress | Democratic Candidate for GA-11\", says \"Elect Chris Harden "
               "for Congress in Georgia's 11th District\", and carries \"PAID FOR BY "
               "CHRIS HARDEN FOR CONGRESS\" (the FEC committee exactly)",
        "seen": "Looked at the file and card: one man alone, short brown hair, beard, "
                "smiling, dark suit, white shirt, light blue tie, seated on a stool "
                "with hands clasped, plain dark blue-grey studio backdrop; nobody else "
                "in the frame; the card keeps the whole file. Measured: On the card "
                "brow at about band 1.1, chin at about band 2.6: about 1.5 tenths (one "
                "band = 55 source px).",
        "read": "2026-11-17",
    },
    # Lauren B. Pena
    "FEC_H6TX35038": {
        "url": "https://files.manuscdn.com/user_upload_by_module/session_file/3105196634"
               "50394445/BJQRmbhGNXZEirYx.jpg",
        "page": "https://www.lauren4congress.com/",
        "words": "the page's og:image (its own share picture, file name "
                 "\"BJQRmbhGNXZEirYx.jpg\", no alt text), on the page titled \"Lauren B. "
                 "Peña for Congress | Texas CD-37\", whose words read \"Lauren B. Peña — "
                 "Republican nominee for Texas CD-37. Trafficking survivor, mother of "
                 "six, conservative. General Election November 3, 2026.\" The page lists "
                 "no other image and no other rendition; the page's twitter:image:alt "
                 "for this very file is \"Lauren B. Peña — Republican candidate for U.S. "
                 "Congress, Texas CD-37\", and its schema.org Person (\"Lauren B. Peña\", "
                 "\"Congressional Candidate — Texas CD-37\") names it as her image",
        "by": "the campaign's website (lauren4congress.com)",
        "tie": "the campaign site her committee (LAUREN4TEXAS) filed with the FEC, "
               "which names her and this race (\"Republican nominee for Texas CD-37\", "
               "\"General Election November 3, 2026\"); the file names no surname, so "
               "rule 38's reader could not take it unattended. The page's words carry "
               "no \"Paid for by\" line",
        "seen": "Looked at the file and card: one woman alone, long dark hair, "
                "blue-grey eyes, red lipstick, smiling, royal blue jacket, before a US "
                "flag; nobody else anywhere in the frame; the card keeps her whole "
                "face. Measured: On the card brow at about band 2.9, chin at about band "
                "6.9: about 4.0 tenths (one band = 131 source px).",
        "read": "2026-11-17",
    },
    # Tessa Lynn Hodge
    "FEC_H6CA23230": {
        "url": "https://run.imgix.net/3d168e21-fedf-4224-a39e-27cd57192ee3/76d9d749-bb4a"
               "-445f-a579-23e30c082a3f/76d9d749-bb4a-445f-a579-23e30c082a3f.png?ixlib=j"
               "s-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=0%2C0%2C1000%2C667&au"
               "to=compress%2Cformat&fit=fillmax&w=640&q=75&s=4e1bdbad5673669dac2ae99e4b"
               "cd078e",
        "page": "https://www.tessaforca.com/",
        "words": "the home page's opening photograph (alt text \"hero image\", the 640w "
                 "rendition its srcset lists, signed by the site), directly under the "
                 "site's logo (alt \"Tessa for CA\") on the page titled \"Tessa Lynn Hodge "
                 "for Congress\", whose words open \"Tessa is fighting to lower the cost "
                 "of living\". No alt text or caption names her: the same woman is at the "
                 "centre of the About page's photographs under the heading \"About Tessa "
                 "Lynn Hodge\" and \"Tessa's Story\". A person should weigh that before "
                 "showing it",
        "by": "the campaign's website (tessaforca.com)",
        "tie": "route 1(b): no campaign site is on file for her; a web search led to "
               "tessaforca.com, whose disclaimer \"Paid for by Tessa Lynn Hodge for "
               "Congress\" names her principal campaign committee exactly as the FEC "
               "registers it (TESSA LYNN HODGE FOR CONGRESS, C00899138), and whose "
               "About page names this race: \"Tessa Lynn Hodge for Congress, CA-23\", \"I "
               "am Tessa Lynn Hodge, and I'm running for Congress to represent "
               "California's 23rd Congressional District in the 2026 election\"",
        "seen": "Looked at the file and card: one woman alone, long dark brown hair, "
                "smiling, black cardigan over a dark floral top, tattooed forearms, "
                "hands folded on a table with a tablet on a stand, before shelves of "
                "pottery and a window with blinds; a hanging dreamcatcher-like ornament "
                "and paper prints on the left, no person anywhere in the frame (whole "
                "file checked, not only the card's crop). The card (x 149-491) keeps "
                "her whole and alone. The same woman, in the same cardigan and floral "
                "top, is at the centre of the About page's photograph under 'About "
                "Tessa Lynn Hodge' (with others round a table; not offered) and alone "
                "with a dog in another of the site's photographs. Measured: On the card "
                "brow at about band 2.8, chin at about band 4.4: about 1.6 tenths (one "
                "band = 42.7 source px); the face is small but over a tenth.",
        "read": "2026-11-17",
    },
    # Pamela Delancy
    "FEC_H6GA10183": {
        "url": "https://content.campaignpartner.net/images/149430/Candidate.png",
        "page": "https://votepamdelancy.com",
        "words": "the page's og:image, file name \"Candidate.png\", on the page titled "
                 "\"Pamela DeLancy for Congress District 10 | Georgia\" (\"Pamela DeLancy "
                 "is running for Congress District 10 in Georgia\"); the same photograph "
                 "is the home page's opening background picture, file name "
                 "\"candidate_90388824d65a4c65accefc4557e331ba_PD_Campaign_Photo.png\" "
                 "(her initials), at 3.3 MB; this is the lighter of the two the page "
                 "lists",
        "by": "the campaign's website (votepamdelancy.com)",
        "tie": "the campaign site her committee filed with the FEC; \"Paid for by "
               "Committee to Elect Pamela DeLancy for Congress\" (the FEC committee "
               "exactly), naming this race: \"Pamela DeLancy, candidate for Congress, "
               "Georgia District 10\". The files carry no surname, so rule 38's reader "
               "could not take them unattended",
        "seen": "Looked at the file and card: one woman alone, dark shoulder-length "
                "curly hair, pearl earrings, smiling, navy blazer with a US flag pin, "
                "white open-collared blouse, before two blurred US flags; nobody else "
                "in the frame; the card keeps her whole face. The same woman stands "
                "beside a man under the McDonough arch in the Meet Pam page's "
                "photograph 'Barnes_and_Pam2.jpg' (not offered: two people), which ties "
                "the face to 'Pam' on her own site. Measured: On the card brow at about "
                "band 2.6, chin at about band 5.0: about 2.4 tenths (one band = 150 "
                "source px).",
        "read": "2026-11-17",
    },
    # Kevin Eugene Martin
    "FEC_H6GA06181": {
        "url": "https://kevinmartinforcongress.com/assets/kevin-hero.jpg",
        "page": "https://kevinmartinforcongress.com/",
        "words": "the image's alt text \"Kevin Martin, candidate for Congress in "
                 "Georgia's 6th District\", file name \"kevin-hero.jpg\", under the heading "
                 "\"We Work for You, So It's Time We Start Listening\"",
        "by": "the campaign's website (kevinmartinforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC "
               "(kevinmartinforcongress.org) now leads to kevinmartinforcongress.com, "
               "which enrich read as still naming him; \"PAID FOR BY COMMITTEE TO ELECT "
               "KEVIN E MARTIN\" (the FEC committee exactly), titled \"Kevin Martin for "
               "Congress | Georgia's 6th District, 2026\"",
        "seen": "Looked at the file and card: one man alone, receding brown hair, "
                "smiling, navy suit, white shirt, gold tie, before a US flag and a "
                "mottled grey studio backdrop; nobody else in the frame; the card keeps "
                "the whole file. Measured: On the card brow at about band 3.0, chin at "
                "about band 5.6: about 2.6 tenths (one band = 100 source px).",
        "read": "2026-11-17",
    },
    # Blake Miguez
    "FEC_H6LA05234": {
        "url": "https://senate.la.gov/SenPics/Sen22.jpg",
        "page": "https://senate.la.gov/smembers?ID=22",
        "words": "the page's only portrait, directly before \"State Senator Blake Miguez "
                 "Republican District 22\" (no alt text)",
        "by": "Louisiana State Senate",
        "tie": "route (d): the campaign site his committee filed with the FEC (\"Paid "
               "for and authorized by Blake Miguez for Louisiana\", the FEC committee "
               "exactly; \"Louisiana's 6th District\") says in its own words that he is "
               "\"a small business owner in the oil and gas industry, and a State "
               "Senator\" and \"Blake was elected to the Louisiana State Senate in "
               "2023\"; the Louisiana Senate's page for district 22 names him beside "
               "the photograph",
        "seen": "Looked at the file and card: one man alone, dark hair greying at the "
                "sides, beard, smiling, blue suit, white shirt, red tie and red pocket "
                "square, legislative lapel pin, plain grey studio backdrop; nobody else "
                "in the frame; the card keeps the whole file. Same face as his "
                "campaign's own 'blake-miguez-hero.jpg' (alt 'Blake Miguez'), which I "
                "looked at, so the seat file shows him and not his predecessor, "
                "whatever the batch date (which, being a copy's, proves nothing by "
                "itself, rule 100). Measured: On the card brow at about band 2.2, chin "
                "at about band 5.2: about 3.0 tenths (one band = 32.5 source px).",
        "read": "2026-11-17",
        # Sen22.jpg shows whoever holds Senate District 22 (rule 100).
        "seat": {"state": "LA", "chamber": "upper", "district": "22",
                 "legislator": "ocd-person/8574f94d-93ed-49b0-a5f6-aa1832b5542a",
                 "name": "Blake Miguez"},
    },
    # Michael Charles Echols
    "FEC_H6LA05242": {
        "url": "https://www.michaelechols.com/wp-content/uploads/2026/02/MECHOLS52-768x9"
               "72.png",
        "page": "https://www.michaelechols.com",
        "words": "the image's alt text \"Michael Echols in a professional suit, candidate "
                 "for Congress.\", file name \"MECHOLS52-809x1024.png\", the page's first "
                 "image, followed by \"Michael Echols State Representative | Business "
                 "Leader | Conservative Reformer\" (the 768w rendition its srcset lists, "
                 "within the caps)",
        "by": "the campaign's website (michaelechols.com)",
        "tie": "the campaign site his committee filed with the FEC; \"Paid for by "
               "Echols for Congress\" (the FEC committee exactly), titled \"Michael "
               "Echols for Congress\", \"Michael Echols represents North Louisiana "
               "(District 14) in the Louisiana House of Representatives\". The page's "
               "words name no district of the U.S. House and no year; the site is the "
               "one ECHOLS FOR CONGRESS (registered for 2026) filed",
        "seen": "Looked at the file and card: one man alone, short dark hair, smiling "
                "slightly, blue suit, white shirt, red tie, arms folded, plain light "
                "grey backdrop; nobody else in the frame; the card keeps the whole "
                "file. Measured: On the card brow at about band 1.7, chin at about band "
                "3.9: about 2.2 tenths (one band = 96 source px).",
        "read": "2026-11-17",
    },
    # Stephen Wagley
    "FEC_H6LA06182": {
        "url": "https://static.wixstatic.com/media/70755c_c916a22f8a07481d8a86cc21bf72c2"
               "7d~mv2.jpg/v1/fill/w_323,h_484,al_c,q_80,usm_0.66_1.00_0.01,enc_avif,qua"
               "lity_auto/70755c_c916a22f8a07481d8a86cc21bf72c27d~mv2.jpg",
        "page": "https://www.wagleyforcongress.com/",
        "words": "the image's alt text \"Stephen-Wagley-Headshot-Tie.jpg\", after the "
                 "heading \"Meet Stephen Wagley\" on the home page titled \"HOME | Stephen "
                 "Wagley for Congress\"; the page declares it 323x484 and its static "
                 "markup draws an 81x54 placeholder through Wix's own resizer "
                 "(.../v1/fill/w_81,h_54,...): this is the same file through the same "
                 "resizer at the declared 323x484",
        "by": "the campaign's website (wagleyforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (stephenwagley.com) "
               "now leads to wagleyforcongress.com, which enrich read as still naming "
               "him: \"Official website for Stephen Wagley for Congress in Louisiana, "
               "US\", \"Meet Stephen Wagley\". The page's words give no \"Paid for by\" "
               "line, no district number and no year; WAGLEY FOR CONGRESS is the "
               "committee the work list gives for LA-6",
        "seen": "Looked at the file and card: one man alone, dark swept-back hair, full "
                "beard, smiling, navy suit, light blue shirt, red and blue paisley tie, "
                "a lapel pin, before blurred trees; nobody else in the frame; the card "
                "keeps him whole. Measured: On the card brow at about band 3.1, chin at "
                "about band 5.9: about 2.8 tenths (one band = 40.4 source px).",
        "read": "2026-11-17",
    },
    # Conrad Roberts Cable
    "FEC_H6LA04187": {
        "url": "https://images.squarespace-cdn.com/content/v1/68a876e549ee746bc353d307/7"
               "633d1e3-dad7-477f-8abf-e808f346560c/07292025-ConradCable-Portrait-007.jp"
               "g?format=1000w",
        "page": "https://www.conrad4congress2026.com/meet-conrad",
        "words": "the image's alt text \"Louisiana 4th District congressional candidate "
                 "Conrad Cable smiling outdoors in a straw hat, blue checkered shirt, "
                 "and brown overalls, standing in a green rural landscape.\", file name "
                 "\"07292025-ConradCable-Portrait-007.jpg\", the first image of the page "
                 "titled \"Meet Conrad | Conrad 4 Congress\" (the 1000w rendition its "
                 "srcset lists)",
        "by": "the campaign's website (conrad4congress2026.com)",
        "tie": "route 1(b): no campaign site is on file for him; a web search led to "
               "conrad4congress2026.com, whose disclaimer \"Paid for by Committee to "
               "Elect Conrad Cable\" names his principal campaign committee exactly as "
               "the FEC registers it (COMMITTEE TO ELECT CONRAD CABLE, C00909762), and "
               "which names this race: \"Conrad Cable for Congress 2026 | Louisiana's "
               "4th District\", \"running for Congress in LA-04 in 2026\"",
        "seen": "Looked at the whole file and the card: one man alone, beard, glasses, "
                "straw hat, blue gingham shirt, brown work overalls, smiling, looking "
                "to his right, before blurred greenery and a lawn; nobody else anywhere "
                "in the frame. The frame is wider than tall, but the card (x 233-767) "
                "keeps his whole head, hat and face well inside its edges. Measured: On "
                "the card brow at about band 2.8, chin (under the beard) at about band "
                "4.6, beard's end about 5.0: about 1.8-2.2 tenths (one band = 66.7 "
                "source px).",
        "read": "2026-11-17",
    },
    # Lauren Jewett
    "FEC_H6LA01258": {
        "url": "https://www.laurenjewett.com/_next/image?url=%2Fimages%2Fportraits%2F07_"
               "Jewett_Headshots_2026.jpg&w=640&q=75&dpl=dpl_H3ozFSWCbechM5W34THw1ybmrQo"
               "5",
        "page": "https://www.laurenjewett.com/about",
        "words": "the image's alt text \"Lauren Jewett\", file name "
                 "\"07_Jewett_Headshots_2026.jpg\", on the page titled \"Meet Lauren Jewett "
                 "| Congressional Candidate LA-01 | Lauren Jewett for Congress\" (the "
                 "site's own 640px rendition through its image optimizer, as its srcset "
                 "lists)",
        "by": "the campaign's website (laurenjewett.com)",
        "tie": "the campaign site her committee filed with the FEC; \"Paid for by the "
               "Committee to Elect Lauren Jewett for Congress\" (the FEC committee "
               "exactly); \"running for Congress in Louisiana's 1st Congressional "
               "District\", \"November 3, 2026\"",
        "seen": "Looked at the file and card: one woman alone, shoulder-length brown "
                "hair, smiling, chin resting on her hand, black sleeveless top, elbows "
                "on a white table, plain light grey-white backdrop; nobody else in the "
                "frame; the card keeps her whole face. Note: the address carries the "
                "site's Next.js deployment id (dpl=...), which may stop answering after "
                "a redeploy. Measured: On the card brow at about band 3.0, chin at "
                "about band 4.5: about 1.5 tenths (one band = 80 source px).",
        "read": "2026-11-17",
    },
    # Matthew Gromlich
    "FEC_H6LA04195": {
        "url": "https://images.squarespace-cdn.com/content/v1/69df20822a2d50664859f4d7/a"
               "e16ec47-1b70-4b45-997c-42bf157356ab/Profile+Pic+-+MGFC+-+March+2026+-+00"
               "9.jpg?format=750w",
        "page": "https://www.mattgromlichforcongress.com/",
        "words": "alt text \"Matt Gromlich, running for congress in Louisiana's 4th "
                 "district, wearing a black blazer with a small American flag pin, a "
                 "white textured sweater, and dark pants. He is outdoors with a modern "
                 "building and trees in the background.\"; file \"Profile Pic - MGFC - "
                 "March 2026 - 009.jpg\", above the heading \"Matt Gromlich\" (the srcset's "
                 "750w form)",
        "by": "the campaign's website (mattgromlichforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "fightersforourfuture.com, safe, titled 'Matt Gromlich | Louisiana "
               "Congressional District 4') shows only a banner 'OUR NEW WEBSITE IS "
               "LIVE ... Click below to visit the updated official campaign site' "
               "naming 'MattGromlichForCongress.com'; that site's disclaimer reads "
               "'Paid for by the Committee to Elect Matt Gromlich' (the FEC committee "
               "exactly) and its title names the race: 'Matt Gromlich | Candidate for "
               "Congress, Louisiana's 4th District', 'running for Congress in LA-04 "
               "against Mike Johnson', '(c)2026 Committee to Elect Matt Gromlich'. The "
               "pipeline's reader passed the file over for the word 'flag' (his flag "
               "pin) in its alt text",
        "seen": "Looked at the file and card: one man, short brown hair and beard, "
                "smiling, black blazer with a flag pin over a white ribbed sweater, "
                "leaning on a low wall before a pale multi-storey building, palm trees "
                "and a tree branch; every window and balcony empty, nobody else "
                "anywhere in the frame. Tie read fresh: the filed site "
                "fightersforourfuture.com (titled 'Matt Gromlich | Louisiana "
                "Congressional District 4') shows only a banner sending readers to "
                "MattGromlichForCongress.com; that site's disclaimer reads 'Paid for by "
                "the Committee to Elect Matt Gromlich' (the FEC committee exactly), "
                "title 'Matt Gromlich | Candidate for Congress, Louisiana's 4th "
                "District', 'running for Congress in LA-04 against Mike Johnson', "
                "'(c)2026 Committee to Elect Matt Gromlich'. Measured: face brow to "
                "chin about 2.1 tenths of the card (brow at band 2.4, chin at band 4.4 "
                "on the card picture; about 210 of the file's px against a 93.8px band)",
        "read": "2026-11-17",
    },
    # John David Day
    "FEC_H6LA03205": {
        "url": "https://johndayforcongress.com/wp-content/uploads/2026/03/John-Day-for-C"
               "ongress-ProfileImage-Hereo.png",
        "page": "https://johndayforcongress.com/about-john-day-for-congress/",
        "words": "alt text \"John Day for Congress\", file "
                 "\"John-Day-for-Congress-ProfileImage-Hereo.png\", directly above the "
                 "heading \"About John Day\" and \"Meet your candidate! Steady. Principled. "
                 "Present. John Day was born in Shreveport, raised in Lake Charles\"; the "
                 "home page draws the same file above \"I'm John Day, a Veteran running "
                 "for Congress in the 3rd District of Louisiana.\"",
        "by": "the campaign's website (johndayforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "johndayforcongress.com, safe): 'I'm John Day, a Veteran running for "
               "Congress in the 3rd District of Louisiana', '(c) 2026 John Day for "
               "Congress'. Its disclaimer reads 'Paid for by John Day for Congress', "
               "not the registered 'COMMITEE TO ELECT JOHN DAY', but this is the site "
               "the committee filed (route 1(a)), not one found another way",
        "seen": "Looked at the file and card: a studio cut-out on a transparent "
                "background (grey on the card) of one man in glasses, grey hair and "
                "beard, blue suit, red tie, beaded necklace and flag pin; nobody else "
                "in the frame. The filed site (campaignSite johndayforcongress.com) "
                "names LA-3: 'Louisiana's 3rd Congressional District', '(c) 2026 John "
                "Day for Congress'; its disclaimer 'Paid for by John Day for Congress' "
                "is not letter for letter the registered COMMITEE TO ELECT JOHN DAY, "
                "which route 1(a) does not need. Measured: face brow to chin about 2.6 "
                "tenths of the card (brow at band 2.0, chin at band 4.6; about 260 of "
                "the file's px against a 96.1px band)",
        "read": "2026-11-17",
    },
    # Patrick Wayne Forbes
    "FEC_H6LA06190": {
        "url": "https://static.wixstatic.com/media/637d7a_8cc2a2562383408f9ba5064535a3f4"
               "12~mv2.jpg/v1/fill/w_2048,h_1365,al_c,q_90,enc_auto/637d7a_8cc2a25623834"
               "08f9ba5064535a3f412~mv2.jpg",
        "page": "https://www.patforbes.com/",
        "words": "the home page's Wix image record for it: name "
                 "\"Pat_Forbes_WEB_Shoot-9.jpg\", alt \"Pat Forbes smiling in park with "
                 "trees in background\", on \"Pat Forbes for U.S. Congress | Louisiana | "
                 "Official Campaign Site\" beside \"Meet Pat Forbes, running for US "
                 "Congress in Louisiana's 6th District\"",
        "by": "the campaign's website (patforbes.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "patforbes.com, safe): 'Paid for by Committee to Elect Pat Forbes' (the "
               "FEC committee exactly), 'Meet Pat Forbes, running for US Congress in "
               "Louisiana's 6th District'. The site is Wix: its images are drawn by "
               "script from records in the markup (wow-image data-image-info), which "
               "is why rule 38's reader listed only the og:image banner",
        "seen": "Looked at the file, the card and zooms of both edges: one man, grey "
                "hair and beard, dark suit, blue tie, arms folded, under trees by "
                "water; the blurred left edge (outside the card's crop) holds a lamp "
                "post, a red shape like a parked car and a pale post, no person that "
                "can be made out; the right edge is water and path. Tie read fresh: "
                "'Paid for by Committee to Elect Pat Forbes' (the FEC committee "
                "exactly), title 'Pat Forbes for U.S. Congress | Louisiana | Official "
                "Campaign Site', 'Meet Pat Forbes, running for US Congress in "
                "Louisiana's 6th District', 'Election Day: Tuesday, Nov. 3'. Measured: "
                "face brow to chin about 2.7 tenths of the card (brow at band 2.6, chin "
                "at band 5.3; one band = 136.5 source px)",
        "read": "2026-11-17",
    },
    # Gordon Brian Heslop
    "FEC_H6LA04229": {
        "url": "https://assets.zyrosite.com/cdn-cgi/image/format=auto,w=768,h=1037,fit=c"
               "rop/7nq3YslSVIcSZlff/gordon-3-30-1NNSewD4szHQgvdn.png",
        "page": "https://heslopforcongress.com",
        "words": "the home page's only photograph, file \"gordon-3-30-...png\" (no alt "
                 "text), in the section under the headings \"Gordon Heslop\" / \"Republican "
                 "Candidate 4th Congressional District of Louisiana\" and \"I'M AN ANTI "
                 "TRUMP REPUBLICAN\" (the srcset's w=768 form; the file's full resolution "
                 "is 221x301, which the host serves at that request)",
        "by": "the campaign's website (heslopforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "heslopforcongress.com, safe): 'Gordon Heslop Republican Candidate 4th "
               "Congressional District of Louisiana', 'Paid for by Heslop for "
               "Congress' (not letter for letter the registered 'HESLOP FOR CONGRESS "
               "COMMITTEE', but this is the filed site, route 1(a)); the file names "
               "only his first name, so rule 38's reader could not take it unattended",
        "seen": "Looked at the file and card: a plain head-and-shoulders photograph of "
                "one older man, white hair, rimless glasses, dark jacket, light-blue "
                "shirt, striped tie, against a cream wall; nobody else in the frame. "
                "Small and a little soft but a clear likeness. Filed site (campaignSite "
                "heslopforcongress.com): 'Republican Candidate 4th Congressional "
                "District of Louisiana', 'towards the end of this year (2026)'; "
                "disclaimer 'Paid for by Heslop for Congress', not letter for letter "
                "HESLOP FOR CONGRESS COMMITTEE, which route 1(a) does not need. "
                "Measured: face brow to chin about 3.5 tenths of the card (brow at band "
                "3.5, chin at band 7.0; one band = 27.6 source px)",
        "read": "2026-11-17",
    },
    # Lindsay Garcia
    "FEC_H6LA05309": {
        "url": "https://static.wixstatic.com/media/efbd32_e67486738c5642dcbde522b7c787cd"
               "5c~mv2.jpg/v1/fill/w_453,h_556,al_c,q_80,usm_0.66_1.00_0.01,enc_avif,qua"
               "lity_auto/SV-0092.jpg",
        "page": "https://www.rubiagarcia.com/meet-lindsay",
        "words": "the Meet page's first photograph (file and alt text \"SV-0092.jpg\"), on "
                 "\"Meet Rubia | Rubia Garcia For Congress | Louisiana 6th District\", "
                 "directly above the heading \"Meet Rubia\" and \"Lindsay “Rubia” Garcia "
                 "isn’t a career politician. She’s a daughter of Louisiana\"",
        "by": "the campaign's website (rubiagarcia.com)",
        "tie": "the campaign site her committee filed with the FEC (campaignSite "
               "rubiagarcia.com, safe): 'Paid for and Authorized by Lindsay Rubia "
               "Garcia For Congress' (the FEC committee exactly), 'Lindsay “Rubia” "
               "Garcia for Congress in Louisiana’s 6th District', 'Tuesday, November "
               "3rd, 2026'; the file names no one, so rule 38's reader could not take "
               "it unattended",
        "seen": "Looked at the file and card: a studio portrait of one woman, long wavy "
                "brown and blonde hair over one shoulder, white blazer, navy shirt, "
                "plain light-grey backdrop; nobody else in the frame. Measured: face "
                "brow to chin about 1.7 tenths of the card (brow at band 2.4, chin at "
                "band 4.1; one band = 55.6 source px)",
        "read": "2026-11-17",
    },
    # Vincent Matrisciano
    "FEC_H6NJ11336": {
        "url": "https://vincentmatriscianoforcongress.com/wp-content/uploads/2026/05/260"
               "420-Cuppek-018-scaled-e1779207272511-768x832.jpg",
        "page": "https://vincentmatriscianoforcongress.com/about/",
        "words": "the About page's first photograph (file 260420-Cuppek-018..., no alt "
                 "text; the srcset's 768w form, and the page's og:image), under \"About "
                 "Vincent\" / \"Who is Vincent Matrisciano?\" and \"Vincent brings a career "
                 "of public service and real-world problem-solving to his campaign for "
                 "New Jersey's 11th Congressional District\", on \"About - Vincent "
                 "Matrisciano\"",
        "by": "the campaign's website (vincentmatriscianoforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "vincentmatriscianoforcongress.com, safe): 'Paid for by the Vincent "
               "Matrisciano for Congress Committee' (the FEC committee 'VINCENT "
               "MATRISCIANO FOR CONGRESS'), 'Vincent MATRISCIANO FOR CONGRESS Write-in "
               "candidate for NJ-11', '(c) 2026'; the file names no one (a "
               "photographer's shoot number), so rule 38's reader could not take it "
               "unattended. The home page's family photograph 'Meet your future "
               "Congressman' shows the same man",
        "seen": "Looked at the file, card and zooms of both edges: one bald man in "
                "glasses, blue suit, striped tie, flag pin and pocket square, hands "
                "clasped, in a bright lobby; shelves with ornaments and a plant behind, "
                "sofas at right; nobody else in the frame. Measured: face brow to chin "
                "about 1.3 tenths of the card (brow at band 1.9, chin at band 3.2; "
                "about 105 of the file's px against an 83.2px band)",
        "read": "2026-11-17",
    },
    # Michael Thurow
    "FEC_H6WI06233": {
        "url": "https://images.squarespace-cdn.com/content/v1/6949e25a449b6734bccf9382/e"
               "2370e3b-a273-437e-8d01-64e4efe74564/ThurowforCongress_HeroPhoto.jpg?form"
               "at=1000w",
        "page": "https://www.thurowforcongress.com/about",
        "words": "alt text \"A portrait of Mike Thurow, Independent candidate for "
                 "Wisconsin's Sixth Congressional District.\", file "
                 "\"ThurowforCongress_HeroPhoto.jpg\" (the srcset's 1000w form), the About "
                 "page's opening photograph above \"Meet Mike Thurow\" / \"Mike Thurow grew "
                 "up in Mequon, Wi\"",
        "by": "the campaign's website (thurowforcongress.com)",
        "tie": "the campaign site his committee filed with the FEC (campaignSite "
               "thurowforcongress.com, safe): 'PAID FOR BY MIKE THUROW FOR CONGRESS' "
               "(the FEC committee exactly), 'Mike Thurow is the Independent candidate "
               "for Wisconsin's 6th Congressional District', '(c)2026 Mike Thurow for "
               "Congress'",
        "seen": "Looked at the file and card: one man, short dark hair, smiling, olive "
                "jacket over a grey henley, before a snowy creek with bare trees and "
                "orange leaves; nobody else anywhere in the frame. Wider than tall; the "
                "card's centre crop keeps him whole-faced. Measured: face brow to chin "
                "about 2.5 tenths of the card (brow at band 2.3, chin at band 4.8; "
                "about 142 of the file's px against a 56.3px band)",
        "read": "2026-11-17",
    },
    # Austin Magee
    "FEC_H6LA05283": {
        "url": "https://images.squarespace-cdn.com/content/v1/699c7b79fe93a070441bd9b0/f"
               "b6a9c08-7817-446e-a48e-6f636730d574/IMG_6622.jpg?format=1000w",
        "page": "https://www.austinmageeforcongress.com/",
        "words": "the background photograph (file \"IMG_6622.jpg\", no alt text; the "
                 "page's 1000w rendition) of the home page section whose headings read "
                 "\"Austin Magee\" and \"Candidate for Louisiana’s Congressional District "
                 "5\", under the banner \"I can't do any worse than the rest of 'em!\"",
        "by": "the campaign's website (austinmageeforcongress.com)",
        "tie": "route 1(b): a web search (Ballotpedia/BallotReady, leads only) named "
               "austinmageeforcongress.com; the site's own disclaimer reads 'Paid for "
               "by Austin Magee for Congress' (the FEC committee AUSTIN MAGEE FOR "
               "CONGRESS exactly) and it names the race: 'Austin Magee's congressional "
               "campaign for Louisiana's District 5', 'Candidate for Louisiana’s "
               "Congressional District 5'; its yard-sign graphic reads 'Vote May 16 "
               "Dist 5'. The about page's family photograph shows the same red-bearded "
               "man",
        "seen": "Looked at the file, card and a zoom of the woods behind: one man with "
                "a long red beard, red plaid shirt over a white T-shirt, jeans, two "
                "books on his knee, sitting against a large tree trunk in leafy woods; "
                "nobody else in the frame. Wider than tall; the card's centre crop "
                "keeps him whole-faced. Measured: face brow to chin about 1.6 tenths of "
                "the card, the chin taken at the jaw line under the beard (brow at band "
                "1.5, chin at band 3.2; about 90 of the file's px against a 56.2px "
                "band); to the beard's end far more",
        "read": "2026-11-17",
    },
    # Elizabeth Fitzgibbon
    "FEC_H6WI06241": {
        "url": "https://static.wixstatic.com/media/821665_f849b4f500f24015b5b657d7e07a1d"
               "58~mv2.png/v1/fill/w_426,h_559,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,qua"
               "lity_auto/bcfdfe36-8d58-49c1-8608-ac840758886a.png",
        "page": "https://www.fitzgibbonforcongress.com/",
        "words": "the home page's opening photograph (its only portrait; file and alt "
                 "text a generated name, 'bcfdfe36-8d58-49c1-8608-ac840758886a.png'), in "
                 "the hero of the page titled \"Elizabeth Fitzgibbon for Congress | "
                 "Wisconsin Congressional District 6\", beside \"Elizabeth is a mother, "
                 "advocate, and independent candidate for Wisconsin's 6th Congressional "
                 "District\" (the page's 1x rendition, 426x559; its srcset's 2x is "
                 "852x1118)",
        "by": "the campaign's website (fitzgibbonforcongress.com)",
        "tie": "her filed campaign site "
               "(elizabethfitzgibbonforglenngrothmansseatincongress.org, no longer in "
               "DNS) moved to fitzgibbonforcongress.com, which enrichment.json read as "
               "still naming her; its footer 'Paid for by Friends for Fitzgibbon' "
               "names her FEC principal committee (FRIENDS FOR FITZGIBBON, C00946673) "
               "exactly, and the page names this race (Wisconsin's 6th Congressional "
               "District, independent). The file names no one, so rule 38's reader "
               "cannot take it unattended: like CAND_9 (Brad Lander), the page's "
               "opening photograph beside the words naming her",
        "seen": "Looked at the card, the 2x rendition (852x1118, 49,032 bytes) and a "
                "full-resolution face crop of the 1632x2111 original: a retouched "
                "studio headshot of one woman, background removed (transparent PNG, "
                "grey on the page), dark blazer, white blouse, hoop earrings; "
                "photographic skin texture, no sign of generation; nobody else, no arm, "
                "shoulder or face anywhere in the frame. Not a namesake: the site is "
                "her committee's and names WI-6 and her independent run, as the work "
                "list does. The site's other person images are named "
                "'Gemini_Generated_Image' (a woman with a child, AI-edited) and are "
                "rightly not offered. The page lists only the 1x (426x559, the "
                "lightest) and 2x (852x1118, also within the caps; sharper on a 2x "
                "screen) renditions; the 1x offered passes over nothing lighter. "
                "Measured: card picture 500px tall, 50px a band: brow at about 2.9 "
                "tenths from the top, chin at about 5.3: about 2.3-2.4 tenths of the "
                "card (first reader said 2.7); well over a tenth",
        "read": "2026-11-17",
    },
}

# There is no list of members to leave out. Whoever has left is decided by
# bioguide id from Congress's own records (legislators.departures) and moved
# to Former_Members.csv by `congress --apply`. The name list that stood here
# matched on names (rules 3 and 17), and all three of its names had already
# left the roster.

# Where the Senate notes below were checked (2026-10-02). Each is the section
# that states the fact, read from the live article, never from memory.
_SENATE_2026 = "https://en.wikipedia.org/wiki/2026_United_States_Senate_elections"

# Seat-status notes keyed on bioguide id, the only safe key for a person
# (rules 3 and 17). These used to sit in a second table matched as a
# case-insensitive substring of the member's name, which only worked while the
# roster spelled every name the way the table did. Each value is (status line,
# source). A member who is leaving the seat needs a NOT_SEEKING_MARKERS phrase
# in the status line; the two special-election notes are for members who are
# on the ballot.
MEMBER_STATUS_BY_ID = {
    # Interim appointees running in the specials (the article's seat count
    # footnote: "the interim appointees from Florida and Ohio running").
    "M001244": ("2026 special election for final two years of Marco Rubio's term",
                _SENATE_2026 + "#Seats"),                                   # Ashley Moody, FL
    "H001104": ("2026 special election for final two years of JD Vance's term",
                _SENATE_2026 + "#Seats"),                                   # Jon Husted, OH
    # Listed in the article's Retirements table.
    "T000278": ("Retiring to run for governor",
                _SENATE_2026 + "#Retirements"),                             # Tommy Tuberville, AL
    "E000295": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Joni Ernst, IA
    # The rosters use his legal name; he is usually reported as "Dick Durbin".
    # Keyed on the id, the spelling no longer matters.
    "D000563": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Richard Durbin, IL
    "M000355": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Mitch McConnell, KY
    "S001181": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Jeanne Shaheen, NH
    "L000571": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Retirements"),                             # Cynthia Lummis, WY
    # "where incumbent Gary Peters is not running for reelection".
    "P000595": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Democratic_incumbents"),                   # Gary Peters, MI
    # Marked "(retiring)" in the article's ratings table.
    "D000618": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026 + "#Predictions"),                             # Steve Daines, MT
    # "Republican Thom Tillis of North Carolina is retiring from the Senate".
    "T000476": ("Incumbent not running for re-election in 2026.",
                _SENATE_2026),                                              # Thom Tillis, NC
    # "Democratic incumbent Tina Smith is not seeking a second full term."
    "S001203": ("Incumbent not running for re-election in 2026.",
                "https://en.wikipedia.org/wiki/"
                "2026_United_States_Senate_election_in_Minnesota"),         # Tina Smith, MN
    # The article's Defeats section: both lost renomination in their primaries.
    "C001056": ("Incumbent defeated in primary for 2026 election.",
                _SENATE_2026 + "#Defeats"),                                 # John Cornyn, TX
    "C001075": ("Incumbent defeated in primary for 2026 election.",
                _SENATE_2026 + "#Defeats"),                                 # Bill Cassidy, LA
    # "Armstrong was sworn in on March 24 and was required to sign an oath
    # stating that he would not run in the 2026 election."
    "A000383": ("Not running in 2026: appointed in March 2026 on an oath not to seek the seat.",
                _SENATE_2026 + "#Oklahoma"),                                # Alan Armstrong, OK
    # The DC article is titled "... election in the District of Columbia",
    # which results.page_titles never asks for, so no outcome was ever read.
    "N000147": ("Not running for re-election in 2026 (announced January 2026).",
                "https://en.wikipedia.org/wiki/2026_United_States_House_of_Representatives_"
                "election_in_the_District_of_Columbia"),
    # Same title problem: "... election in the United States Virgin Islands".
    "P000610": ("Retiring to run for governor of the U.S. Virgin Islands.",
                "https://en.wikipedia.org/wiki/2026_United_States_House_of_Representatives_"
                "elections#Non-voting_delegates"),
    # Withdrew 2026-07-21, before Wikipedia's LA-6 box existed to say so.
    "F000110": ("Not running for re-election in 2026; running for the Louisiana State Senate.",
                "https://www.thegreenpapers.com/G26/LA"),
}

# Two cards an evidenced entry settles (kyc/identity.py, rule 105):
# keyed on both cards' keys exactly as the build's identity warnings name
# them ("officer:MI:sos", "candidate:gov-MI-jocelyn-benson",
# "profile:FEC_...", "legislator:GA:ocd-person/..."), each {"same": True
# where they are one person, False where they are namesakes, "evidence":
# the pages that tie or part them - the office's own page naming the person
# beside the other role, never a news story - and "read": the day}. An id
# and a second source join people without an entry; an entry is for a pair
# no record ties (identity-look-alike, identity-legislator-look-alike) or
# whose names an id cannot settle (identity-names-disagree). The build
# warns on an entry naming a card it no longer makes, one the records now
# join themselves, and a "two people" entry the records join
# (stale-identity-join, identity-join-contradicted). "behind" beside "same":
# True says the legislator card of the pair is no current role - the
# legislature's own pages seat someone else while Open States still seats
# them - in the legislature's words: the pair joins nothing and is said in
# identity-legislator-roster-behind until the roster drops the card, when
# the entry is stale. Each source below was opened by this project's reader
# (its agents, kyc/agent.py's USER_AGENT) on the day given, a second read of
# the research of 2026-11-15; no person has yet looked at these entries, and
# one a person has read says so. A page that refused the reader concludes
# nothing (rule 8) and is named as such. No telephone number or mailing
# address is copied.
IDENTITY_JOINS = {
    ("officer:MI:sos", "candidate:gov-MI-jocelyn-benson"): {
        "same": True,
        "evidence": (
            "The candidate card's own Wikidata item, Q13562375 (its record's item; enwiki "
            "\"Jocelyn Benson\", the article Michigan's race article links for the list's "
            "name: \"| nominee1 = '''[[Jocelyn Benson]]'''\"), holds P39 Q16147324, series "
            "ordinal 43, start 2019-01-01, replaces Q7383055 (Ruth Johnson); Q16147324 is "
            "labelled \"Michigan Department of State\", alias \"Michigan Secretary of "
            "State\", \"elected office and department within the government of the State of "
            "Michigan\". The article's infobox: \"office1 = 43rd [[Michigan Secretary of "
            "State|Secretary of State of Michigan]]\", \"term_start1 = January 1, 2019\", "
            "term_end1 blank, \"predecessor1 = [[Ruth Johnson]]\": rule 69's two sources, "
            "which the build withheld only for the item's label. The campaign site the item "
            "gives (P856), https://www.jocelynbenson.com/ : \"Secretary of State and "
            "Democratic nominee for Governor Jocelyn Benson joined the rest of the Democratic "
            "ticket\". The office's own page, "
            "https://www.michigan.gov/sos/resources/the-secretary-of-state, answered this "
            "reader 403 \"Access Denied\" and concludes nothing."),
        "read": "2026-11-17",
    },
    ("officer:MT:sos", "profile:FEC_H6MT01160"): {
        "same": True,
        "evidence": (
            "The profile's FEC id H6MT01160 has the principal campaign committee C00941583 "
            "\"CHRISTI JACOBSEN FOR CONGRESS\" (OpenFEC /candidate/H6MT01160/committees/, first "
            "filed 2026-03-03). The Montana Secretary of State's \"FEDERAL PRIMARY 2026 "
            "Candidate List\", https://candidatefiling.mt.gov/candidatefiling/CandidateList."
            "aspx?e=450002928 , prints for \"1ST CONGRESSIONAL UNITED STATES REPRESENTATIVE "
            "... CHRISTI JACOBSEN\" the website \"CHRISTIJACOBSEN.COM\", filed \"3/3/2026 "
            "11:23:45 AM REP\" (its post office box, the committee's too, is not copied). "
            "That site, https://christijacobsen.com/about/ : \"Christi Jacobsen is running "
            "for Congress ... She currently serves as Montana’s Secretary of State\", and "
            "\"PAID FOR BY CHRISTI JACOBSEN FOR CONGRESS\", the committee's name. The "
            "office's own site, https://sosmt.gov/, answered this reader 403 \"Just a "
            "moment...\", a challenge page that concludes nothing."),
        "read": "2026-11-17",
    },
    ("officer:SD:ag", "profile:FEC_H6SD01109"): {
        "same": True,
        "evidence": (
            "The profile's FEC id H6SD01109 has the principal campaign committee C00909689 "
            "\"MARTY JACKLEY FOR CONGRESS\", whose filed website is WWW.MARTYJACKLEY.COM "
            "(data/campaigns.json; rule 32). https://martyjackley.com/about : \"2009–2019, "
            "2023–PRESENT Attorney General of South Dakota Appointed in 2009, then reelected "
            "three times.\", the photograph captioned \"Attorney General Marty Jackley\", "
            "\"Paid for by Marty Jackley for Congress\". The office's own page, the officer "
            "card's, https://atg.sd.gov/OurOffice/bio.aspx : \"Attorney General Marty J. "
            "Jackley Marty was raised in Sturgis and graduated from the South Dakota School of "
            "Mines ...\", \"In 2022 Marty was elected for a fourth term as the South Dakota "
            "Attorney General.\" - the life the campaign's About page tells."),
        "read": "2026-11-17",
    },
    ("profile:FEC_H6IL09293", "legislator:IL:ocd-person/0125b0ac-65ba-443e-b418-53cdf42b9f85"): {
        "same": True,
        "evidence": (
            "The profile's FEC id H6IL09293 has the principal campaign committee C00910976 "
            "\"MIKE SIMMONS FOR CONGRESS\", website WWW.MIKESIMMONS.ORG (OpenFEC "
            "/candidate/H6IL09293/committees/). https://www.mikesimmons.org (\"Mike Simmons | "
            "Illinois State Senator | District 7\"): \"state Senator for the 7th Senate "
            "District of Illinois ... On February 6, 2021, Mike was sworn in to represent the "
            "7th District\". The General Assembly's own page for the member the card links, "
            "https://www.ilga.gov/Senate/Members/Details/3398 : \"Senate Member Mike Simmons "
            "(D) - 104th General Assembly (2025-2026) Mike Simmons (D) Senator 2021 - Present "
            "7th District\". The card's \"Mike Simmons-Gessesse\" is Open States' form; the "
            "legislature writes \"Mike Simmons\"."),
        "read": "2026-11-17",
    },
    ("profile:FEC_H6FL24087", "legislator:FL:ocd-person/a8a2eaa4-449b-441f-96bb-d8a3e8191479"): {
        "same": True,
        "behind": ("the Florida Senate's own page for District 34, "
                   "https://www.flsenate.gov/Senators/S34, names \"2026-2028 Senator Ashley "
                   "Viola Gantt ... District 34\", \"Elected to the Senate in 2026\"; its list "
                   "of 2026-2028 senators holds no Jones"),
        "evidence": (
            "The Florida Senate's page for the last term, "
            "https://www.flsenate.gov/Senators/2024-2026/S34 : \"2024-2026 Senator Shevrin D. "
            "\"Shev\" Jones Party: Democrat District 34\". The profile's FEC id H6FL24087 has "
            "the principal campaign committee C00952556 \"SHEVRIN FOR CONGRESS\", website "
            "WWW.SHEVRINJONES.COM (OpenFEC). That site's https://shevrinjones.com/about/ was "
            "read on 2026-11-15 (\"Florida State Senator Shevrin “Shev” Jones\", \"Today, Jones "
            "proudly serves Florida’s 34th Senate District\", \"Paid for by Shevrin Jones for "
            "Congress\"), and on 2026-11-17 answered 404 (\"404 — Shevrin Jones for State "
            "Senate\"); its front page, https://shevrinjones.com/ , now titled \"Shevrin Jones "
            "for State Senate\": \"Shevrin “Shev” Jones is an educator ... Elected to the "
            "Florida House in 2012 and the Florida Senate in 2020, he is running to bring that "
            "record to District 37\", \"paid for and approved by Shevrin Jones, Democrat, for "
            "State Senate, District 37\" - the same person, on the site his FEC committee "
            "filed. One person; the card's seat is now Senator Gantt's (\"behind\")."),
        "read": "2026-11-17",
    },
    ("profile:FEC_S6FL00830", "legislator:FL:ocd-person/66c3a112-3008-4332-a6b0-8990a7d992d5"): {
        "same": True,
        "behind": ("the Florida House's \"Representatives for 2026 - 2028\", "
                   "https://www.flhouse.gov/Sections/Representatives/representatives.aspx, "
                   "lists \"Gibson, Audrey Democrat — District: 13 ... 11/04/26 - 11/07/28\" "
                   "and no Nixon"),
        "evidence": (
            "The profile's FEC id S6FL00830 has the committee \"ANGIE FOR FLORIDA\", whose "
            "filed website is ANGIENIXON.COM (data/campaigns.json; rule 32). "
            "https://angienixon.com : \"Angie is a former Florida State Representative, union "
            "organizer, and mother born and raised in Jacksonville\", \"Paid for by Angie for "
            "Florida\". The profile's record of offices (Wikidata Q98690818) gives \"Member of "
            "the Florida House of Representatives\", 2020 to 2026. One person; the card's "
            "seat, District 13, is now Representative Gibson's (\"behind\")."),
        "read": "2026-11-17",
    },
    ("profile:J000299", "legislator:LA:ocd-person/0e901294-3718-49df-9922-0ac4503acee2"): {
        "same": False,
        "evidence": (
            "Two people. The Louisiana House's own page for the district, "
            "https://house.louisiana.gov/H_Reps/members?ID=27 : \"State Representative Michael "
            "T. Johnson Republican District 27\", \"Representing Parishes: Rapides\", \"Year "
            "Elected: 2019\", \"Education: Pineville High School, 1977; B.A., Public "
            "Administration, Louisiana College, 1981; J.D., Southern University Law Center, "
            "1984\". The profile is the Speaker, Mike Johnson, who sits in Congress for LA-4 "
            "on the term 2025-01-03 to 2027-01-03 (congress-legislators, bioguide J000299), "
            "born 1972-01-30."),
        "read": "2026-11-17",
    },
    ("profile:G000598", "legislator:CA:ocd-person/8b2f37bc-65b7-40ed-af14-5d93cb765a5d"): {
        "same": False,
        "evidence": (
            "Two people. The California State Assembly's own page for the district, "
            "https://www.assembly.ca.gov/assemblymembers/50 (\"Assembly Member Garcia | "
            "California State Assembly\"): \"Robert Garcia District: 50 Party: Democrat "
            "Counties: san bernardino\", a sitting Assemblymember. The profile is the member "
            "of Congress Robert Garcia, who sits for CA-42 on the term 2025-01-03 to "
            "2027-01-03 (congress-legislators, bioguide G000598): one person does not hold "
            "both seats at once."),
        "read": "2026-11-17",
    },
}


# Members who are on the November ballot for an office this site does not
# cover, keyed on bioguide id: {bioguide: (what they are, source, checked)}.
# Without it Byron Donalds, Florida's Republican nominee for governor, read
# only "Not running for this seat in 2026", and Tommy Tuberville "Withdrew".
# Each entry is the winner the results page marks with its `winning
# candidate` template (rule 29), read from the article's wikitext on the day
# given, never from memory; a nominee who later withdraws is taken out.
# The profile drops an entry once its member starts a new term, `validate`
# reports one whose member has gone (stale-other-office), and after Election
# Day it reports them all, for the result to be read from the same page.
# Until then the page says it in the past tense from the day after Election
# Day ("Was the ..."), so a stale entry never reads as a race still to come.
_GOV = "https://en.wikipedia.org/wiki/2026_{}_gubernatorial_election"
OTHER_OFFICE_NOMINEES = {
    # Republican primary results, May 19: Tuberville 85.4%.
    "T000278": ("Republican nominee for Governor of Alabama",
                _GOV.format("Alabama"), "2026-10-17"),
    # Republican primary results, July 21: Biggs 74.0%.
    "B001302": ("Republican nominee for Governor of Arizona",
                _GOV.format("Arizona"), "2026-10-17"),
    # Republican primary results, August 18: Donalds 47.8%.
    "D000032": ("Republican nominee for Governor of Florida",
                _GOV.format("Florida"), "2026-10-17"),
    # Republican primary results, August 4: James 50.05%.
    "J000307": ("Republican nominee for Governor of Michigan",
                _GOV.format("Michigan"), "2026-10-17"),
    # Democratic primary results, August 11: Klobuchar 89.7% ("Election box
    # winning candidate ... [[Amy Klobuchar]] ... 615,041", read 2026-10-18;
    # the article: "Democratic senator Amy Klobuchar ... launched a campaign
    # for the governor's office on January 29, 2026"). The Secretary of
    # State's sample ballot prints "Amy Klobuchar and Ben Schierer
    # Democratic-Farmer-Labor" (data/statewide_candidates.json). Her Senate
    # seat is not up, so only her profile says it (PR #109 review).
    "K000367": ("Democratic-Farmer-Labor nominee for Governor of Minnesota",
                _GOV.format("Minnesota"), "2026-10-18"),
    # Republican primary results, August 6: Blackburn 43.6%. Her Senate
    # seat is not up, so only her profile says it.
    "B001243": ("Republican nominee for Governor of Tennessee",
                _GOV.format("Tennessee"), "2026-10-17"),
    # Republican primary results, August 11: Tiffany 95.32%.
    "T000165": ("Republican nominee for Governor of Wisconsin",
                _GOV.format("Wisconsin"), "2026-10-17"),
    # Democratic primary results, August 1 (the Elections System of the
    # Virgin Islands' territorial summary): Plaskett and Potter 46.99%.
    "P000610": ("Democratic nominee for Governor of the U.S. Virgin Islands",
                _GOV.format("United_States_Virgin_Islands"), "2026-10-17"),
}

# FEC registrations that are one person although their totals differ, so the
# exact same-committee signal (candidates.same_committee) cannot see it. Each
# entry maps the registration folded away to (the one kept, the evidence).
# Rule 25 still holds: a shared name alone never earns an entry here.
# A member's own FEC candidate id that congress-legislators does not list,
# keyed on bioguide id: {bioguide: (candidate id, evidence)}. Merged into the
# snapshot's `fecAll` (and `fec` once they sit in that chamber) when it is
# built, so a member elected to the other chamber is linked to that
# candidacy - and their money looked up - by its id, never by a name search.
# Rule 17; validate's member-candidacy-id-missing lists any further gap.
MEMBER_FEC_IDS = {
    # Ashley Hinson, IA-2, running for Iowa's Senate seat: S6IA00314 is
    # filed as "ARENHOLZ, ASHLEY HINSON" (Iowa, Senate, Republican), her
    # legal name, and is the FEC Candidate ID of the curated row for her
    # Senate candidacy; congress-legislators lists only her House id,
    # H0IA01174. Checked 2026-10-16.
    "H001091": ("S6IA00314", "the curated row for her Iowa Senate candidacy; filed under "
                             "her legal name, Arenholz"),
}

# Names a reader searches a member by that congress-legislators does not
# record (its name.nickname covers "Jim Clyburn"), keyed on bioguide id
# (rules 3 and 17), each with where the name is given as theirs. Search
# only: never displayed as the person's name. "AOC" found only a candidate
# whose text said "endorsed by AOC" (audit 2026-10-17, GRID-05); "MTG" found
# nobody (GRID-08). validate reports a key that is neither a profile nor a
# departed member the page lists.
SEARCH_ALIASES = {
    "O000172": (("AOC", "Wikipedia, Alexandria Ocasio-Cortez, first sentence: \"also known as "
                        "AOC\"; read 2026-10-18"),),
    "G000596": (("MTG", "Wikipedia, Marjorie Taylor Greene, first sentence: \"also known by her "
                        "initials MTG\"; read 2026-10-18"),),
}

SAME_PERSON_FILINGS = {
    # NV-3: the results page links both registrations to one article,
    # [[Martin O'Donnell]], and their receipts and disbursements differ by the
    # same $28,832.67 - one transfer counted under one id only. Checked
    # 2026-10-02.
    "H6NV03204": ("H4NV03225", "one article on the results page; totals differ by "
                               "a single $28,832.67 transfer"),
    # Each pair below is one principal campaign committee whose Form 1 lists
    # both ids, as the FEC's /candidate/{id}/committees/ gave it on
    # 2026-10-17. They are off every ballot, so the campaigns cache (which
    # reads committees only for people still running) does not hold the
    # committee that rule 72 joins them on; the money is equal to the cent.
    "H6FL01440": ("H6FL01457", "FL-1: committee C00894337 BRODEN FOR HOUSE lists both; "
                               "$19,541.21 in and out on each"),
    "H6TX38107": ("H6TX38099", "TX-38: committee C00928077 WILLIAM TAGGART FOR CONGRESS "
                               "lists both; $9,995.08 in and out on each"),
    "S6ME00316": ("S6ME00324", "Maine Senate: committee C00902759 CARMEN4SENATE.COM lists "
                               "both ('Carmem' is a misspelling); $17,759.71 on each"),
    # VA-11: committee C00959106 PURVES FOR CONGRESS lists all three, filed as
    # "PURVES, ARTHUR GRAHAME MR."; the same name and committee fold them
    # (rule 72). H6VA11249 is the one kept: its totals also count his second
    # committee, C00951277, and run to 2026-09-30, where H6VA11256's stop at
    # 2026-08-27 - so the race shows his current money, not a stale $5,142.86.
    "H6VA11256": ("H6VA11249", "VA-11: committee C00959106 lists H6VA11249, H6VA11256 and "
                               "H6VA11264, all filed as PURVES, ARTHUR GRAHAME MR."),
    # A second registration with no money and no committee in the campaigns
    # cache, under the campaign's very filed name, party and seat: nothing
    # joins it automatically (rule 72), and a results page's one name matched
    # both ids, so KY-4 read "Jeremy Ryan Todd (Libertarian): Lost the November
    # election" and "with no FEC filing over $5,000 and so no profile here:
    # Jeremy Todd (Libertarian)" (results night, 2026-11-04). Read from
    # data/fec_field.json that day; validate's second-registration warning
    # names the next one for a person.
    "H6KY04213": ("H6KY04205", "KY-4: both filed as TODD, JEREMY RYAN, Libertarian; H6KY04205 "
                               "has $30,837.92 and committee C00954834 JEREMY TODD FOR KENTUCKY, "
                               "H6KY04213 $0 and no committee"),
    "H6NJ06278": ("H6NJ06286", "NJ-6: both filed as HERZIG, HILLARY, Republican; H6NJ06286 has "
                               "$11,766.00 and committee C00927335 HERZIG FOR CONGRESS, H6NJ06278 "
                               "$0 and no committee"),
    "S6TX00503": ("S6TX00495", "Texas Senate: both filed as SIMMONS, JADE, Independent; S6TX00495 "
                               "has $9,324.49 and committee C00923201 JADE SIMMONS FOR SENATE, "
                               "S6TX00503 $0 and no committee"),
    "H6FL12215": ("H6FL12207", "FL-12 and FL-14: all filed as WILLIAMS, SHAY, Republican; "
                               "H6FL12207 (registered in district 14) has $23,443.03, as does "
                               "H6FL12223 (district 12, already folded under it, one committee's "
                               "money), H6FL12215 (district 12) $0"),
    "H6GA03170": ("H6GA11231", "GA-11: both filed as EKPETE KAMA, ULOMA, Republican; H6GA11231 "
                               "has $12,011.00, H6GA03170 $0"),
    "H8TX29102": ("H2TX18207", "TX-38: both filed as MONTIEL, CARMEN, Republican; H2TX18207 has "
                               "$147,355.21, H8TX29102 $0"),
}

# The name a results page uses for a filing the matcher cannot connect to it:
# a nickname the FEC filing does not carry. Keyed on the FEC candidate id;
# each entry is (the name exactly as the race's results page writes it, the
# evidence), and the evidence is the candidate's own principal campaign
# committee at the FEC (its name or its registered website), so the alias
# is the campaign's word, not a guess about a nickname (rule 17). Where the
# committee's register entry does not carry the name, the home page of the
# website that entry registers may, in its own title. Applied only inside
# the filing's own race (results.apply_cache). Checked 2026-10-14, the
# committees read from the FEC's /candidate/{id}/committees/ that day.
# Not settled, for want of such evidence: Rakhi Israni Singh (CA-14; her
# site says "Rakhi Israni"), Sonia Kacker (CA-26) and J. D. Scholten (Iowa
# Senate; both sites draw themselves with script), Daira Smith-Rodriguez
# (Maine Senate; no site registered).
RESULT_NAMES = {
    "S6GA00374": ("Buddy Carter", "committee C00543967 BUDDY CARTER FOR SENATE"),
    "S6IL00482": ("Raja Krishnamoorthi", "committee C00904466 RAJA FOR ILLINOIS; "
                                         "filed as KRISHNAMOORTHI, S"),
    "S6SC04452": ("Mark Sanford", "committee C00285254 SANFORD FOR SENATE, "
                                  "website marksanford.com"),
    "H6TN06205": ("Van Hilleary", "committee C00909838 VAN FOR TENNESSEE; "
                                  "filed as HILLEARY, WILLIAM V."),
    "H6WV02150": ("Ace Parsi", "committee C00927723 ACE PARSI FOR CONGRESS"),
    "H4NC02150": ("Max Ganorkar", "committee C00769463 GANORKAR FOR CONGRESS, "
                                  "website maxforcongress.com"),
    "H6MS04259": ("Carl Boyanton", "committee C00937136 CARL4CONGRESS; filed with "
                                   "the names reversed, CARL, BOYANTON LESTER"),
    "H6TX34098": ("Fred Hinojosa", "committee C00917724 FRED HINOJOSA FOR CONGRESS"),
    "H6VA01232": ("Salaam Bhatti", "committee C00912287 SALAAM BHATTI FOR CONGRESS"),
    "H6CO06157": ("Mel Tewahade", "committee C00944173 MEL FOR COLORADO, website "
                                  "melforcolorado.com; filed as TEWAHADE, BEMELEKOT W"),
    "S6IL00466": ("Casey Chlebek", "committee C00903823 CASEY CHLEBEK FOR US SENATE"),
    "H6NJ05239": ("Sandy Gajapathy", "committee C00920066 SANDY GAJAPATHY FOR CONGRESS"),
    "H4TX27105": ("Scott Mandel", "authorized committee C00862946 SCOTT MANDEL FOR "
                                  "CONGRESS; filed as MANDEL, CHARLES"),
    "H6TX09199": ("Crystal DeLeon-Sarmiento", "committee C00926535 CRYSTAL FOR US CONGRESS, "
                  "website crystalforuscongress.com titled \"Crystal De Leon Sarmiento for "
                  "US Congress\""),
    "H6IL09210": ("Mark Su", "committee C00904680 MARK SU FOR CONGRESS; filed as SU, DONGBO"),
    "H6OH14222": ("Nicole Frenchko", "committee C00935023 NIKI FRENCHKO FOR CONGRESS; "
                                     "filed reversed as NICOLE, FRENCHKO MICHELE"),
    "H6MI10300": ("Tripp Adams", "committee C00908293 TRIPP ADAMS FOR CONGRESS"),
    "H6FL22164": ("Herbie Wertheim", "committee C00945014 DR. HERBIE WERTHEIM FOR CONGRESS"),
    "H4FL02138": ("Yen Bailey", "committee C00882886 YEN BAILEY FOR CONGRESS"),
    "H6TX21376": ("Trey Trainor", "committee C00922344 TREY TRAINOR FOR TEXAS"),
    "H4OR01121": ("Jamil Ahmad", "committee C00870303 CHAUDHRY-AHMAD FOR CONGRESS, "
                                 "website jamilahmadforcongress.com"),
    "H6VA00028": ("J.P. Cooney", "committee C00938670 COONEY FOR CONGRESS, website "
                                 "cooneyforcongress.com titled \"J.P. Cooney for Congress\""),
    "H6IL09285": ("Hoan Huynh", "committee C00909903 HOAN FOR 9, website hoanfor9.com; "
                                "filed as HUYNH, KHAI-HOAN"),
    "H6CA30219": ("Pini Herman", "committee C00917641 PINI HERMAN FOR HOUSE CA30"),
    "H2CA18171": ("Luis Arregu\u00edn", "committee C00805770 LUIS ARREGUIN FOR CONGRESS CA-18"),
    "H6NC11222": ("Moe Davis", "committee C00906081 MOE DAVIS FOR CONGRESS COMMITTEE"),
    "H6NM01129": ("Didi Okpareke", "committee C00908509 NDIDIAMAKA OKPAREKE FOR CONGRESS, "
                                   "website didiforcongress.com"),
    "S6FL00863": ("Neil J. Gillespie", "committee C00943399 NEIL J GILLESPIE FOR US SENATE; "
                                       "filed as GILESPIE, NEIL JOSEPH"),
    "H6WI07256": ("Niina Baum", "committee C00938019 BAUM FOR CONGRESS, website "
                                "baumforwisconsin.com; filed as THRELFALL-BAUM, NIINA"),
    "H6TX31151": ("Vince Offer", "committee C00928614 OFFER VINCE SHAMWOW SHLOMI FOR CONGRESS"),
    "H6TX35111": ("Randy Adams", "committee C00929570 RANDY ADAMS FOR CONGRESS"),
    "H6GA01208": ("Sharon Williamson", "committee C00931949 SHARON STOKES-WILLIAMSON FOR "
                                       "CONGRESS, website sswilliamsonforcongress.com"),
    "H6TX24180": ("TJ Ware", "committee C00907527 TJ WARE FOR CONGRESS"),
}

# Official voting pages that replace what NASS's "Can I Vote" lists for a
# state, keyed (state, kind) - kind is status, polling, absentee or register,
# or a kind kyc/voting.py curates itself (results; see the entries' note).
# Each is (the URL NASS lists, the state's own page that replaces it or None
# to show no button, a label or None for the usual one, the evidence). The
# NASS URL is kept so validate warns once NASS changes its entry and the
# override can go. Checked 2026-10-14, every replacement found on the
# state's own election site and answering 200.
VOTING_LINKS = {
    ("IA", "absentee"): (
        "https://sos.iowa.gov/elections/electioninfo/absenteeinfo.html",
        "https://sos.iowa.gov/voters/absentee-voting", None,
        "NASS's page answers 404 'Page not found'; sos.iowa.gov links Absentee Voting here"),
    ("IN", "absentee"): (
        "http://www.in.gov/sos/elections/2402.htm",
        "https://www.in.gov/sos/elections/voter-information/ways-to-vote/absentee-voting", None,
        "NASS's page answers 404; in.gov/sos/elections links absentee voting here"),
    ("MD", "polling"): (
        "http://www.elections.state.md.us/voting/where.html",
        "https://voterservices.elections.maryland.gov/VoterSearch", None,
        "the old domain now redirects to the board's home page. The Board's 'Voting in "
        "Maryland' page (https://elections.maryland.gov/voting/index.html) says 'On "
        "election day, you must vote at your assigned polling place' and links 'assigned "
        "polling place' here: its Voter Services 'Voter Lookup', 'You can use this tool "
        "to: ... Find out where to vote.' (opened by hand 2026-10-26; the pages read do "
        "not link the board's voting/where.html look-up, shown here until then)"),
    ("CO", "absentee"): (
        "https://www.sos.state.co.us/pubs/elections/FAQs/ElectionDay.html",
        "https://www.sos.state.co.us/pubs/elections/FAQs/mailBallotsFAQ.html", None,
        "NASS links the Election Day FAQ; Colorado mails every voter a ballot, and this "
        "is the Secretary of State's 'Mail-in Ballots FAQs', linked from its 'Elections & "
        "Voting Frequently Asked Questions (FAQs)' page "
        "(https://www.sos.state.co.us/pubs/elections/FAQs/FAQsMain.html, itself linked as "
        "'FAQs' from the Elections page) as 'Mail-in ballots' (read by hand 2026-10-26)"),
    ("ND", "register"): (
        "https://www.sos.nd.gov/elections/voter",
        "https://www.sos.nd.gov/elections/voter", "Voting in North Dakota",
        "North Dakota does not register voters; NASS lists its general voter page "
        "under 'register', which the page labelled 'Register to vote'"),
    ("ND", "status"): (
        "https://www.sos.nd.gov/elections", None, None,
        "no registration to check; NASS lists the general Elections page"),
    # Audit 2026-10-17, STATEGOV-10. NASS lists Nevada's absentee page for
    # voters with disabilities, though every Nevada voter is mailed a
    # ballot. Held at first (a 403 to a plain request, a blank page in
    # headless Chrome: rule 8), then read by a person (research/by-hand-
    # 2026-10-26/NOTES.md, "Nevada's absentee link").
    ("NV", "absentee"): (
        "https://www.nvsos.gov/sos/elections/voters/voters-with-disabilities/absentee-voting",
        "https://www.nvsos.gov/elections/voters/mail-ballot-voting", None,
        "NASS links the Secretary of State's absentee-voting page for voters with "
        "disabilities; Nevada mails every registered voter a ballot, and this is the "
        "Secretary of State's 'Mail Ballot Voting | Nevada Secretary of State': 'With the "
        "passage of Assembly Bill 321 during the 2021 Legislative Session, all registered "
        "voters will receive a ballot by mail. You can request to opt-out by submitting "
        "this form [English], [Spanish], or [Filipino] to your county clerk.' It is linked "
        "from the office's '2026 Election Information' page (https://www.nvsos.gov/elections/"
        "election-information/2026-election-information) as 'Mail Ballot Voting' (that "
        "page's links read 2026-10-25; the page opened by hand 2026-10-26)"),
    ("DC", "absentee"): (
        "https://www.dcboe.org/voters/casting-your-vote/voting-by-special-ballot",
        "https://www.dcboe.org/voters/casting-your-vote/mail-ballot-instructions", None,
        "NASS links 'Voting by Special Ballot', a ballot cast at the polls when a voter's "
        "eligibility is in question; D.C. mails every voter a ballot, and this is the Board's "
        "'Mail Ballot Instructions', linked from dcboe.org (title read 2026-10-17)"),
    ("WY", "status"): (
        "https://sos.wyo.gov/Elections/State/RegisteringToVote.aspx", None, None,
        "NASS lists 'Registering to Vote in Wyoming' - the same page as 'register', with no "
        "lookup on it - so 'Check your registration' led to no check (read 2026-10-17)"),
    # The lookup itself is not dead: it sits behind a bot wall that answered
    # a captcha page ("Oregon Secretary of State Captcha/Support ID") to a
    # browser-like request on 2026-10-19 and 404 to GitHub's runner twice on
    # 2026-10-18, after reading live on 2026-10-17. A wall concludes nothing
    # (rule 8), and its 404 stopped the daily refresh; the Secretary of
    # State's own My Vote page, which a script can read, links the lookup.
    ("OR", "status"): (
        "https://secure.sos.state.or.us/orestar/vr/showVoterSearch.do?lang=eng",
        "https://sos.oregon.gov/elections/pages/myvote.aspx", None,
        "NASS links the ORESTAR voter lookup, behind a bot wall a script cannot pass; "
        "'Oregon Secretary of State : My Vote' on sos.oregon.gov links it as 'Go to My Vote "
        "Now' (read 2026-10-19)"),
    # The results pages kyc/voting.py lists (voting.RESULTS) are replaced the
    # same way: the first field is then the address that table gives, and
    # the entry stops applying once the table changes. Both opened by hand
    # in a person's Chrome on 2026-10-26 (research/by-hand-2026-10-26/
    # NOTES.md, round three): the old addresses showed readers an error.
    # Oklahoma's first replacement, results.okelections.gov/OKER/, was only
    # where the old address redirected: no page of the Board's site was seen
    # to link it, and the page says the office's site links what it shows
    # (voting.site_linked). The Board's own 2026 page, reached by its links,
    # replaces it (NOTES.md, "Oklahoma's results link").
    ("OK", "results"): (
        "https://results.okelections.us/",
        "https://oklahoma.gov/elections/elections-results/election-results/"
        "2026-election-results.html", None,
        "results.okelections.us answers '403 - Forbidden: Access is denied.' in a person's "
        "browser; the State Election Board's site (oklahoma.gov/elections.html, 'Oklahoma "
        "State Election Board (0270)') links 'Election Results' (oklahoma.gov/elections/"
        "elections-results/election-results.html, 'Election Results'), which links '2026' "
        "here: '2026 Election Results', listing 'November 3 General Elections' (not yet a "
        "link) and each earlier 2026 election's results page (opened by hand 2026-10-26)"),
    ("NH", "results"): (
        "https://www.sos.nh.gov/elections/elections/election-results",
        "https://www.sos.nh.gov/2026-election-results", None,
        "the old address redirects to /node/281/election-results, 'Forbidden' in a person's "
        "browser; the Secretary of State's Elections page (sos.nh.gov/elections, 'Elections | "
        "New Hampshire Secretary of State') links '2026 Election Results' here, titled '2026 "
        "Election Results | New Hampshire Secretary of State' (both opened by hand 2026-10-26)"),
    # Ohio's address is kept, labelled for what it reached: the office now
    # sends it to its data portal, not a results page as such (NOTES.md,
    # round three), so "Official results" would promise a count the page
    # was not seen to hold. Look again once the office posts November's.
    ("OH", "results"): (
        "https://www.ohiosos.gov/elections/election-results-and-data/",
        "https://www.ohiosos.gov/elections/election-results-and-data/",
        "Election data portal",
        "the address redirects to ohiosos.gov/data, 'Ohio Secretary of State Data Portal | "
        "Interactive Dashboards & Public Information' (opened by hand 2026-10-26)"),
}

# Voting links the weekly check could not open (a bot wall, a reset: rule 8
# concludes nothing), opened by hand in a person's Chrome. Keyed (state,
# kind) as VOTING_LINKS; each is (the address shown, the day, what was seen,
# the address it ended on or "" and the page's title, or why it was not
# opened). What was seen is
#
# - "opened": the state's own page opened; the page counts the link as
#   opened, on this day, as it counts the weekly check's;
# - "human-check": the state's portal first asked the person to show they
#   are a person, and opened only after that (the check cleared without
#   Claude acting on it; nothing is got past a check), so the page says the
#   portal asks visitors to show they are people and this site cannot open
#   it itself. The last two fields say what the check was, then what opened.
#
# An entry counts only while that link is the one shown and the weekly check
# has not found it live or dead, and only for voting.BY_HAND_DAYS from its
# day on the reader's calendar, so a later failure is seen again
# (validate: voting-by-hand-stale). Read on 2026-10-26 (research/by-hand-
# 2026-10-26/NOTES.md), in two rounds: the second once PK had allowed the
# remaining sites in the browser extension (New York's, Georgia's,
# Michigan's, Ohio's registration and lookup, New Hampshire's registration
# page, Kentucky's registration and polling, Alaska's voter portal and
# registration page). All 34 links a page showed as unconfirmed opened.
# A third round the same day opened the curated pages (results, sample
# ballots, Guam's information page, Iowa's absentee page, vote.gov's
# registration pages): every one but Alabama's results, which did not load.
_BY_HAND_DAY = "2026-10-26"
VOTING_LINKS_BY_HAND = {
    ("MT", "absentee"): ("http://sos.mt.gov/elections/absentee", _BY_HAND_DAY, "opened",
                         "https://sosmt.gov/elections/absentee",
                         "Voting by Absentee Ballot - Official Montana Secretary of State "
                         "Website - Christi Jacobsen"),
    ("ME", "absentee"): ("http://www.maine.gov/sos/cec/elec/voter-info/absent.html", _BY_HAND_DAY,
                         "opened", "https://www.maine.gov/sos/elections-voting/absentee-voting",
                         "Absentee Voting | SOS"),
    ("WI", "absentee"): ("https://elections.wi.gov/node/1103", _BY_HAND_DAY, "opened",
                         "https://elections.wi.gov/i-want-vote-absentee",
                         "I want to vote absentee | Wisconsin Elections Commission"),
    ("AZ", "polling"): ("https://my.arizona.vote/WhereToVote.aspx?s=address", _BY_HAND_DAY,
                        "opened", "", "Search by address"),
    ("AZ", "status"): ("https://my.arizona.vote/WhereToVote.aspx?s=individual", _BY_HAND_DAY,
                       "opened", "", "Voter Registration Search"),
    ("AZ", "absentee"): ("https://my.arizona.vote/Early/ApplicationLogin.aspx", _BY_HAND_DAY,
                         "opened", "", "Ballot-by-Mail Login"),
    ("OH", "polling"): ("https://www.ohiosos.gov/directories/find-my-polling-location",
                        _BY_HAND_DAY, "opened", "", "Find My Polling Location"),
    ("IA", "register"): ("https://sos.iowa.gov/voters/voter-registration", _BY_HAND_DAY, "opened",
                         "", "Voter Registration | Iowa Secretary of State - Paul D. Pate"),
    ("IA", "polling"): ("https://sos.iowa.gov/elections/voterreg/pollingplace/search.aspx",
                        _BY_HAND_DAY, "opened",
                        "https://apps.sos.iowa.gov/elections/voterreg/pollingplace/search.aspx",
                        "Find Your Polling Place"),
    ("IA", "status"): ("https://sos.iowa.gov/elections/voterreg/regtovote/search.aspx",
                       _BY_HAND_DAY, "opened",
                       "https://apps.sos.iowa.gov/elections/voterreg/regtovote/search.aspx",
                       "Am I Registered to Vote | Iowa Secretary of State - Paul D. Pate"),
    ("NH", "absentee"): ("https://sos.nh.gov/elections/voters/absentee-ballots/", _BY_HAND_DAY,
                         "opened", "https://www.sos.nh.gov/elections/absentee-ballots",
                         "Absentee Ballots | New Hampshire Secretary of State"),
    ("RI", "polling"): ("https://vote.sos.ri.gov/Home/PollingPlaces?ActiveFlag=2", _BY_HAND_DAY,
                        "opened", "", "Welcome to your Voter Information Center"),
    ("RI", "register"): ("https://vote.sos.ri.gov/Home/RegistertoVote?ActiveFlag=1", _BY_HAND_DAY,
                         "opened", "", "Welcome to your Voter Information Center"),
    ("RI", "status"): ("https://vote.sos.ri.gov/Home/UpdateVoterRecord?ActiveFlag=0", _BY_HAND_DAY,
                       "opened", "", "Welcome to your Voter Information Center"),
    ("RI", "absentee"): ("https://vote.sos.ri.gov/Voter/VotebyMail?ActiveFlag=4", _BY_HAND_DAY,
                         "opened", "", "Welcome to your Voter Information Center"),
    ("KY", "status"): ("https://vrsws.sos.ky.gov/VIC/", _BY_HAND_DAY, "opened", "",
                       "Voter Information Center"),
    # Second round, after PK allowed the remaining sites in the extension.
    ("NY", "absentee"): ("http://www.elections.ny.gov/VotingAbsentee.html", _BY_HAND_DAY,
                         "opened", "https://elections.ny.gov/request-ballot",
                         "Request a Ballot | New York State Board of Elections"),
    ("NY", "polling"): ("https://voterlookup.elections.ny.gov/", _BY_HAND_DAY, "opened", "",
                        "Voter Search Screen for VoterLookUp"),
    ("NY", "status"): ("https://voterlookup.elections.ny.gov/", _BY_HAND_DAY, "opened", "",
                       "Voter Search Screen for VoterLookUp"),
    ("GA", "polling"): ("http://www.mvp.sos.ga.gov/", _BY_HAND_DAY, "opened",
                        "https://mvp.sos.ga.gov/s/", "GA My Voter Page"),
    ("GA", "absentee"): ("https://www.mvp.sos.ga.gov/MVP/mvp.do", _BY_HAND_DAY, "opened",
                         "https://mvp.sos.ga.gov/s/", "GA My Voter Page"),
    ("GA", "status"): ("https://www.mvp.sos.ga.gov/MVP/mvp.do", _BY_HAND_DAY, "opened",
                       "https://mvp.sos.ga.gov/s/", "GA My Voter Page"),
    ("GA", "register"): ("https://mvp.sos.ga.gov/s/olvr-home", _BY_HAND_DAY, "opened", "",
                         "Home | GA SOS VR"),
    ("MI", "status"): ("https://mvic.sos.state.mi.us/Voter/Index", _BY_HAND_DAY, "opened", "",
                       "Your voter information"),
    ("MI", "polling"): ("https://mvic.sos.state.mi.us/Voter/index", _BY_HAND_DAY, "opened", "",
                        "Your voter information"),
    ("OH", "register"): ("https://olvr.ohiosos.gov/", _BY_HAND_DAY, "opened", "",
                         "Welcome – Online Voter Registration – Ohio Secretary of State"),
    ("OH", "absentee"): ("https://www.ohiosos.gov/elections/frequently-asked-questions"
                         "#absentee-voting", _BY_HAND_DAY, "opened", "",
                         "Ohio Election FAQ | Voter Registration, Absentee Voting & Election Day "
                         "Information"),
    ("OH", "status"): ("https://voterlookup.ohiosos.gov/voterlookup.aspx", _BY_HAND_DAY, "opened",
                       "", "My Voter Information - Voter Search"),
    ("NH", "register"): ("https://www.sos.nh.gov/elections/voters/register-vote", _BY_HAND_DAY,
                         "opened", "https://www.sos.nh.gov/elections/register-vote",
                         "Register to Vote | New Hampshire Secretary of State"),
    ("KY", "register"): ("https://vrsws.sos.ky.gov/ovrweb/", _BY_HAND_DAY, "opened", "",
                         "Welcome - Kentucky State Board of Elections"),
    ("KY", "polling"): ("https://vrsws.sos.ky.gov/ovrweb/govoteky", _BY_HAND_DAY, "opened",
                        "https://vrsws.sos.ky.gov/ovrweb/govoteky/",
                        "Voter Information Guide - Kentucky State Board of Elections"),
    ("AK", "status"): ("https://myvoterportal.alaska.gov/", _BY_HAND_DAY, "opened", "",
                       "Voter Information Lookup - Division of Elections"),
    ("AK", "register"): ("https://www.elections.alaska.gov/voter-information/#Reg", _BY_HAND_DAY,
                         "opened", "", "Voter Information - Division of Elections"),
    # The portal asked first that the visitor show they are a person.
    ("AK", "absentee"): ("http://www.elections.alaska.gov/Core/AKVoteEarly.php", _BY_HAND_DAY,
                         "human-check", "https://www.elections.alaska.gov/absentee-and-early-voting/",
                         "'Human Verification', then 'Absentee and Early Voting - Division of "
                         "Elections'"),
    ("NH", "polling"): ("https://app.sos.nh.gov/viphome", _BY_HAND_DAY, "human-check",
                        "https://app.sos.nh.gov/captcha/challenge",
                        "'Verification', then 'Home'"),
    ("NH", "status"): ("https://app.sos.nh.gov/voterinformation", _BY_HAND_DAY, "human-check", "",
                       "'Verification', then 'Voter Information'"),
    # Round three, the links the pages still called unconfirmed after #142
    # (NOTES.md, "Round three" and "Round three, continued"): the curated
    # results, sample-ballot and information pages.
    ("AK", "results"): ("https://www.elections.alaska.gov/election-results/", _BY_HAND_DAY,
                        "opened", "", "Election Results - Division of Elections"),
    ("AK", "sample"): ("https://www.elections.alaska.gov/sample-ballots/", _BY_HAND_DAY,
                       "opened", "", "Sample Ballots - Division of Elections"),
    ("AZ", "results"): ("https://results.arizona.vote/", _BY_HAND_DAY, "opened",
                        "https://results.arizona.vote/default.html", "Arizona Election Results"),
    ("IA", "absentee"): ("https://sos.iowa.gov/voters/absentee-voting", _BY_HAND_DAY, "opened",
                         "", "Absentee Voting | Iowa Secretary of State - Paul D. Pate"),
    ("MT", "results"): ("https://sosmt.gov/elections/results/", _BY_HAND_DAY, "opened", "",
                        "Official Election Results - Official Montana Secretary of State "
                        "Website - Christi Jacobsen"),
    ("NY", "results"): ("https://nyenr.elections.ny.gov/", _BY_HAND_DAY, "opened", "",
                        "NYS Board of Elections Unofficial Election Night Results"),
    ("WI", "results"): ("https://elections.wi.gov/elections/election-results", _BY_HAND_DAY,
                        "opened", "", "Election Results | Wisconsin Elections Commission"),
    # The office now sends its results address to its data portal: it opened,
    # and the portal is the Secretary of State's, but it is not a results page
    # as such. The reading names no other results page, so the link stays,
    # labelled for the portal in VOTING_LINKS; look again once the office
    # posts November's count.
    ("OH", "results"): ("https://www.ohiosos.gov/elections/election-results-and-data/",
                        _BY_HAND_DAY, "opened", "https://www.ohiosos.gov/data",
                        "Ohio Secretary of State Data Portal | Interactive Dashboards & Public "
                        "Information"),
    ("GU", "info"): ("https://gec.guam.gov/2026-general-election-info/", _BY_HAND_DAY, "opened",
                     "", "2026 GENERAL ELECTION INFO – GUAM ELECTION COMMISSION"),
    ("MI", "sample"): ("https://mvic.sos.state.mi.us/PublicBallot/Index", _BY_HAND_DAY, "opened",
                       "", "What's on the ballot?"),
    # The two replacements in VOTING_LINKS, each opened that day: Oklahoma's
    # reached from the State Election Board's home page through its
    # "Election Results" and "2026" links (NOTES.md, "Oklahoma's results
    # link"), which replaced results.okelections.gov/OKER/, a page no link
    # shows now.
    ("OK", "results"): ("https://oklahoma.gov/elections/elections-results/election-results/"
                        "2026-election-results.html", _BY_HAND_DAY, "opened", "",
                        "2026 Election Results"),
    ("NH", "results"): ("https://www.sos.nh.gov/2026-election-results", _BY_HAND_DAY, "opened",
                        "", "2026 Election Results | New Hampshire Secretary of State"),
    # Nevada's mail-ballot page, the replacement for NASS's absentee link
    # (STATEGOV-10; NOTES.md, "Nevada's absentee link"). nvsos.gov does not
    # answer a script alike each time: a plain request had a 403 and
    # headless Chrome a blank page, and on 2026-10-26 one request with the
    # weekly check's headers had the page and one without them a 403. The
    # weekly check has not opened this address yet, so the person's reading
    # stands until it does (rule 8); once it does, validate says the entry
    # may go (voting-by-hand-stale).
    ("NV", "absentee"): ("https://www.nvsos.gov/elections/voters/mail-ballot-voting",
                         _BY_HAND_DAY, "opened", "",
                         "Mail Ballot Voting | Nevada Secretary of State"),
    # Alabama's results page (www2.alabamavotes.gov) was still loading after
    # 45 seconds in a person's browser, as judicial.alabama.gov resets this
    # network's connections: nothing concluded (rule 8), and no entry.
}

# vote.gov's "How to register in <place> | Vote.gov" page for each
# jurisdiction (voting.DEADLINES), all 56 opened by hand on 2026-10-26
# (NOTES.md, "Round three, continued"), each under that title. A page shows
# one only where the jurisdiction's own record gives no deadline
# (voting.for_page), so most entries wait unused until a record changes.
# {code: (the address, the place as the title names it)}
_VOTE_GOV_OPENED = {
    "AK": ("https://vote.gov/register/alaska", "Alaska"),
    "AL": ("https://vote.gov/register/alabama", "Alabama"),
    "AR": ("https://vote.gov/register/arkansas", "Arkansas"),
    "AS": ("https://vote.gov/register/american-samoa", "American Samoa"),
    "AZ": ("https://vote.gov/register/arizona", "Arizona"),
    "CA": ("https://vote.gov/register/california", "California"),
    "CO": ("https://vote.gov/register/colorado", "Colorado"),
    "CT": ("https://vote.gov/register/connecticut", "Connecticut"),
    "DC": ("https://vote.gov/register/district-of-columbia", "District of Columbia"),
    "DE": ("https://vote.gov/register/delaware", "Delaware"),
    "FL": ("https://vote.gov/register/florida", "Florida"),
    "GA": ("https://vote.gov/register/georgia", "Georgia"),
    "GU": ("https://vote.gov/register/guam", "Guam"),
    "HI": ("https://vote.gov/register/hawaii", "Hawaii"),
    "IA": ("https://vote.gov/register/iowa", "Iowa"),
    "ID": ("https://vote.gov/register/idaho", "Idaho"),
    "IL": ("https://vote.gov/register/illinois", "Illinois"),
    "IN": ("https://vote.gov/register/indiana", "Indiana"),
    "KS": ("https://vote.gov/register/kansas", "Kansas"),
    "KY": ("https://vote.gov/register/kentucky", "Kentucky"),
    "LA": ("https://vote.gov/register/louisiana", "Louisiana"),
    "MA": ("https://vote.gov/register/massachusetts", "Massachusetts"),
    "MD": ("https://vote.gov/register/maryland", "Maryland"),
    "ME": ("https://vote.gov/register/maine", "Maine"),
    "MI": ("https://vote.gov/register/michigan", "Michigan"),
    "MN": ("https://vote.gov/register/minnesota", "Minnesota"),
    "MO": ("https://vote.gov/register/missouri", "Missouri"),
    "MP": ("https://vote.gov/register/northern-mariana-islands", "Northern Mariana Islands"),
    "MS": ("https://vote.gov/register/mississippi", "Mississippi"),
    "MT": ("https://vote.gov/register/montana", "Montana"),
    "NC": ("https://vote.gov/register/north-carolina", "North Carolina"),
    "ND": ("https://vote.gov/register/north-dakota", "North Dakota"),
    "NE": ("https://vote.gov/register/nebraska", "Nebraska"),
    "NH": ("https://vote.gov/register/new-hampshire", "New Hampshire"),
    "NJ": ("https://vote.gov/register/new-jersey", "New Jersey"),
    "NM": ("https://vote.gov/register/new-mexico", "New Mexico"),
    "NV": ("https://vote.gov/register/nevada", "Nevada"),
    "NY": ("https://vote.gov/register/new-york", "New York"),
    "OH": ("https://vote.gov/register/ohio", "Ohio"),
    "OK": ("https://vote.gov/register/oklahoma", "Oklahoma"),
    "OR": ("https://vote.gov/register/oregon", "Oregon"),
    "PA": ("https://vote.gov/register/pennsylvania", "Pennsylvania"),
    "PR": ("https://vote.gov/register/puerto-rico", "Puerto Rico"),
    "RI": ("https://vote.gov/register/rhode-island", "Rhode Island"),
    "SC": ("https://vote.gov/register/south-carolina", "South Carolina"),
    "SD": ("https://vote.gov/register/south-dakota", "South Dakota"),
    "TN": ("https://vote.gov/register/tennessee", "Tennessee"),
    "TX": ("https://vote.gov/register/texas", "Texas"),
    "UT": ("https://vote.gov/register/utah", "Utah"),
    "VA": ("https://vote.gov/register/virginia", "Virginia"),
    "VI": ("https://vote.gov/register/us-virgin-islands", "U.S. Virgin Islands"),
    "VT": ("https://vote.gov/register/vermont", "Vermont"),
    "WA": ("https://vote.gov/register/washington", "Washington"),
    "WI": ("https://vote.gov/register/wisconsin", "Wisconsin"),
    "WV": ("https://vote.gov/register/west-virginia", "West Virginia"),
    "WY": ("https://vote.gov/register/wyoming", "Wyoming"),
}
VOTING_LINKS_BY_HAND.update({
    (code, "deadlines"): (url, _BY_HAND_DAY, "opened", "", f"How to register in {place} | Vote.gov")
    for code, (url, place) in _VOTE_GOV_OPENED.items()})

# Links on a state's government block that the rosters give wrongly, each
# opened on 2026-10-17 (audit 2026-10-17, LINKS-08, LINKS-09):
# {(state, office, field): (what the roster lists, or None for nothing;
# what to show instead, or None to show nothing; evidence)}. office is
# "governor", "lt", "ag" or "sos"; field is "website" or "bio". A dead
# biography is dropped, never guessed at: the office's own home page is
# already linked beside it ("Office"). An entry applies only while the
# roster still lists what it replaces, and stategov reports one that no
# longer matches, so the next refresh cannot put a dead link back silently.
OFFICE_LINKS = {
    ("ME", "sos", "bio"): ("https://www.maine.gov/sos/about/bio.html", None,
                           "404 'Sorry, but I can't find that page'"),
    ("LA", "sos", "bio"): ("https://www.sos.la.gov/OurOffice/LearnAboutNancyLandry/Pages/default.aspx",
                           None, "404 'Oops! Page not found'"),
    ("WV", "sos", "bio"): ("https://sos.wv.gov/about/Pages/KWBio.aspx", None,
                           "404 'Page not found | WV Secretary of State'"),
    ("VT", "sos", "bio"): ("https://sos.vermont.gov/secretary-s-desk/secretary-copeland-hanzas/", None,
                           "404 'Page not found | Secretary of State'"),
    ("KS", "sos", "bio"): ("https://sos.ks.gov/about-the-office/schwab-biography.html", None,
                           "redirects to /messages/page404.html, 'Page Not Found', with status 200"),
    ("AZ", "sos", "bio"): ("https://azsos.gov/about-office/about-secretary", None,
                           "404 'Page not found | Arizona Secretary of State'"),
    ("IN", "governor", "website"): ("https://www.in.gov/gov/index.htm", "https://www.in.gov/gov/",
                                    "the NGA's link answers 404 'Governor Braun: Error - Page Not "
                                    "Found'; /gov/ is 'Governor Braun: Governor Home'"),
    # The NGA's pages for the two governors sworn in in January 2026 carry no
    # website; each is the office's own, titled with the governor's office.
    ("NJ", "governor", "website"): (None, "https://nj.gov/governor/",
                                    "'Office of New Jersey Governor Mikie Sherrill'"),
    ("VA", "governor", "website"): (None, "https://www.governor.virginia.gov/",
                                    "'Governor of Virginia'"),
}


# Photographs of state officers whose roster has none (STATEGOV-13), each looked at on the day given: {(state, office):
# {name, photo, page, by, weight, checked, evidence}}. office is "governor",
# "lt", "ag" or "sos". An entry is shown only while the roster names that
# very person as the holder (stategov.officer_photos): once the office
# changes hands the build says so and shows nothing, never a predecessor's
# face (rule 87). Never from a search - the office's own page, or the
# association whose roster names them.
def _officer_photo(name, photo, page, by, weight, evidence, checked="2026-10-18"):
    return {"name": name, "photo": photo, "page": page, "by": by,
            "weight": dict(zip(("bytes", "width", "height"), weight)),
            "checked": checked, "evidence": evidence}


_NASS = "https://www.nass.org/sites/default/files/styles/secretary/public/"
_NASS_BY = "National Association of Secretaries of State"
# NASS files its members' photographs under the state's code, which
# officers._surname_in cannot tie to a person; each of these was looked at
# and was uploaded after its holder took office, so it cannot be a
# predecessor's.
_NASS_CARD = ("NASS's roster card names {} beside this photograph, filed as {} in {}, after "
              "they took office ({}); a head-and-shoulders portrait. {}")


# An attorney general's photograph is read by the pipeline from the
# office's own pages (officers.add_ag_photos). Where those show none, or one
# offered only above the caps that no resizer serves smaller (rule 87: the
# office's file is then kept, heavy, and this lighter card goes first), it is
# the National Association of Attorneys General's: its "Find
# my AG" roster puts each attorney general's name and state on a card beside
# the photograph. naag.org answers a script and a headless browser with a
# Cloudflare challenge, so the roster was read by a person in a windowed
# Chrome (tools/read_naag_cards.mjs), each photograph at the size the card
# itself offers (WordPress's 225x300), weighed there; a windowed Chrome with
# a fresh profile loads these files from another site, and a row whose
# photograph fails to load keeps its empty circle (kyc-stategov.js). Matched
# on the card's state and full name, never on the file's name: NAAG filed
# West Virginia's as "ag-WA-McCusker". NAAG publishes no licence ("(c) 2026
# National Association of Attorneys General"): the credit says whose it is,
# as the NGA's and NASS's do. Read again when the build says one has gone
# stale (a new holder) - never carried to someone else. Massachusetts's and
# New Hampshire's cards are not recorded: their offices' pages have not
# confirmed the holder's name (rule 56), and a photograph is given only to a
# confirmed one. Maryland's, Michigan's, Tennessee's and Texas's offices'
# own pages give theirs (officers.BIO_PAGES and the page the front page
# links). So, since 2026-10-25, do Arizona's, California's, Hawaii's, New
# Jersey's, Pennsylvania's, South Dakota's and West Virginia's: each offers
# its photograph only above the caps, and Photon serves the same file
# smaller (rule 87), so their cards were dropped. Florida's and Washington's
# offices' files are served no smaller, so the cards below go first there.
_NAAG_ROSTER = "https://www.naag.org/find-my-ag/"
_NAAG_BY = "National Association of Attorneys General"


def _naag_card(name, path, weight, evidence, checked="2026-10-25"):
    return _officer_photo(name, "https://www.naag.org/wp-content/uploads/" + path, _NAAG_ROSTER,
                          _NAAG_BY, weight, evidence + " Read in a windowed Chrome on 2026-10-20"
                          " and again on " + checked + ", the same file, bytes and size both "
                          "times; naag.org challenges a script.", checked)


OFFICER_PHOTOS = {
    ("AZ", "sos"): _officer_photo(
        "Adrian Fontes", _NASS + "2024-07/AZ.jpg?itok=-XCD586X", "https://www.nass.org/membership",
        _NASS_BY, (24106, 355, 450), _NASS_CARD.format(
            "Adrian Fontes", "AZ.jpg", "July 2024", "January 2023",
            "azsos.gov refuses a script (HTTP 403).")),
    ("MN", "sos"): _officer_photo(
        "Steve Simon", _NASS + "2024-07/MN.jpg?itok=eqzGnPsy", "https://www.nass.org/membership",
        _NASS_BY, (18126, 355, 450), _NASS_CARD.format(
            "Steve Simon", "MN.jpg", "July 2024", "January 2015",
            "sos.mn.gov answers a script with a bot check.")),
    ("VT", "sos"): _officer_photo(
        "Sarah Copeland Hanzas", _NASS + "2023-07/VT.jpg?itok=OT3AvScG",
        "https://www.nass.org/membership", _NASS_BY, (23856, 355, 450), _NASS_CARD.format(
            "Sarah Copeland Hanzas", "VT.jpg", "July 2023", "January 2023",
            "sos.vermont.gov shows no photograph of her a script can find.")),
    ("MS", "sos"): _officer_photo(
        "Michael Watson", _NASS + "2022-07/MS.jpg?itok=3rNYOJpS", "https://www.nass.org/membership",
        _NASS_BY, (22287, 355, 450), _NASS_CARD.format(
            "Michael Watson", "MS.jpg", "July 2022", "January 2020",
            "The same man as the office's own headshot on sos.ms.gov/about-us/biography, which is "
            "2.9 MB.")),
    ("NY", "sos"): _officer_photo(
        "Walter Mosley", _NASS + "2024-06/NY.jpg?itok=Jors_L6r", "https://www.nass.org/membership",
        _NASS_BY, (17599, 355, 450),
        "NASS's roster card names Walter Mosley beside this photograph, filed as NY.jpg in June "
        "2024; a head-and-shoulders portrait, the same photograph as the department's own "
        "'Walter T. Mosley Headshot' on dos.ny.gov/about-our-executive-team. dos.ny.gov answers "
        "a script and a headless browser with a Cloudflare challenge, so a reader's browser may "
        "be refused it too: NASS's copy is linked."),
    ("SD", "sos"): _officer_photo(
        "Monae Johnson",
        "https://sdsos.gov/general-information/assets/Secretary%20Johnson_Pic2024.5.jpg",
        "https://sdsos.gov/about-the-office/about-secretary-johnson.aspx",
        "South Dakota Secretary of State", (16591, 310, 431),
        "The office's 'About Secretary Johnson' page; the same photograph as NASS's card for "
        "South Dakota."),
    ("AR", "ag"): _naag_card(
        "Tim Griffin", "2022/11/ag-AG-Griffin-1-225x300.png", (105306, 225, 300),
        "NAAG's Find my AG card reads \"Tim Griffin Arkansas\" beside this photograph, the "
        "card's own 225x300 size (ag-AG-Griffin-1-225x300.png, uploaded 2022-11); a single "
        "head-and-shoulders portrait."),
    ("DE", "ag"): _naag_card(
        "Kathy Jennings", "2020/09/ag-DE-jennings-225x300.jpg", (11201, 225, 300),
        "NAAG's Find my AG card reads \"Kathy Jennings Delaware\" beside this photograph, the "
        "card's own 225x300 size (ag-DE-jennings-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("FL", "ag"): _naag_card(
        "James Uthmeier", "2025/01/ag-FL-Uthmeier-James-225x300.png", (32592, 225, 300),
        "NAAG's Find my AG card reads \"James Uthmeier Florida\" beside this photograph, the "
        "card's own 225x300 size (ag-FL-Uthmeier-James-225x300.png, uploaded 2025-01); a "
        "single head-and-shoulders portrait."),
    ("IA", "ag"): _naag_card(
        "Brenna Bird", "2022/11/ag-IA-Bird-225x300.png", (95965, 225, 300),
        "NAAG's Find my AG card reads \"Brenna Bird Iowa\" beside this photograph, the card's "
        "own 225x300 size (ag-IA-Bird-225x300.png, uploaded 2022-11); a single head-and-"
        "shoulders portrait."),
    ("ID", "ag"): _naag_card(
        "Raúl Labrador", "2022/11/ag-ID-Labrador-225x300.png", (102503, 225, 300),
        "NAAG's Find my AG card reads \"Raúl Labrador Idaho\" beside this photograph, the "
        "card's own 225x300 size (ag-ID-Labrador-225x300.png, uploaded 2022-11); a single "
        "head-and-shoulders portrait."),
    ("IL", "ag"): _naag_card(
        "Kwame Raoul", "2020/09/ag-IL-raoul-2-225x300.jpg", (10604, 225, 300),
        "NAAG's Find my AG card reads \"Kwame Raoul Illinois\" beside this photograph, the "
        "card's own 225x300 size (ag-IL-raoul-2-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("KS", "ag"): _naag_card(
        "Kris Kobach", "2022/11/ag-KS-Kobach-225x300.png", (30604, 225, 300),
        "NAAG's Find my AG card reads \"Kris Kobach Kansas\" beside this photograph, the card's"
        " own 225x300 size (ag-KS-Kobach-225x300.png, uploaded 2022-11); a single head-and-"
        "shoulders portrait."),
    ("ME", "ag"): _naag_card(
        "Aaron Frey", "2020/09/ag-ME-Frey-Aaron-2025-225x300.png", (20774, 225, 300),
        "NAAG's Find my AG card reads \"Aaron Frey Maine\" beside this photograph, the card's "
        "own 225x300 size (ag-ME-Frey-Aaron-2025-225x300.png, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("MS", "ag"): _naag_card(
        "Lynn Fitch", "2020/09/ag-MS-Fitch-2024-225x300.jpg", (17333, 225, 300),
        "NAAG's Find my AG card reads \"Lynn Fitch Mississippi\" beside this photograph, the "
        "card's own 225x300 size (ag-MS-Fitch-2024-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait."),
    ("NC", "ag"): _naag_card(
        "Jeff Jackson", "2025/01/ag-NC-Jackson-Jeff-2025-225x300.png", (24212, 225, 300),
        "NAAG's Find my AG card reads \"Jeff Jackson North Carolina\" beside this photograph, "
        "the card's own 225x300 size (ag-NC-Jackson-Jeff-2025-225x300.png, uploaded 2025-01);"
        " a single head-and-shoulders portrait."),
    ("NE", "ag"): _naag_card(
        "Mike Hilgers", "2022/11/Mike-Hilgers-AG-600px-headshot-300x298.png", (26792, 300, 298),
        "NAAG's Find my AG card reads \"Mike Hilgers Nebraska\" beside this photograph, the "
        "card's own 300x298 size (Mike-Hilgers-AG-600px-headshot-300x298.png, uploaded "
        "2022-11); a single head-and-shoulders portrait."),
    ("NY", "ag"): _naag_card(
        "Letitia James", "2020/09/ag-NY-james2-225x300.jpg", (7901, 225, 300),
        "NAAG's Find my AG card reads \"Letitia A. James New York\" beside this photograph, the"
        " card's own 225x300 size (ag-NY-james2-225x300.jpg, uploaded 2020-09); a single "
        "head-and-shoulders portrait. The card's 'Letitia A. James' is the office's 'Letitia "
        "James' with her middle initial."),
    ("OK", "ag"): _naag_card(
        "Gentner Drummond", "2022/11/ag-OK-Drummond-225x300.png", (118321, 225, 300),
        "NAAG's Find my AG card reads \"Gentner Drummond Oklahoma\" beside this photograph, the"
        " card's own 225x300 size (ag-OK-Drummond-225x300.png, uploaded 2022-11); a single "
        "head-and-shoulders portrait."),
    ("SC", "ag"): _naag_card(
        "Alan Wilson", "2020/09/ag-SC-Wilson_new-225x300.jpg", (6382, 225, 300),
        "NAAG's Find my AG card reads \"Alan Wilson South Carolina\" beside this photograph, "
        "the card's own 225x300 size (ag-SC-Wilson_new-225x300.jpg, uploaded 2020-09); a "
        "single head-and-shoulders portrait."),
    ("UT", "ag"): _naag_card(
        "Derek Brown", "2025/01/ag-UT-Brown-Derek-225x300.png", (30412, 225, 300),
        "NAAG's Find my AG card reads \"Derek Brown Utah\" beside this photograph, the card's "
        "own 225x300 size (ag-UT-Brown-Derek-225x300.png, uploaded 2025-01); a single head-"
        "and-shoulders portrait."),
    ("VA", "ag"): _naag_card(
        "Jay Jones", "2026/01/ag-VA-jones-jay-225x300.png", (31065, 225, 300),
        "NAAG's Find my AG card reads \"Jay Jones Virginia\" beside this photograph, the card's"
        " own 225x300 size (ag-VA-jones-jay-225x300.png, uploaded 2026-01); a single head-"
        "and-shoulders portrait."),
    ("WA", "ag"): _naag_card(
        "Nick Brown", "2025/01/ag-WA-Brown-Nick-225x300.png", (19311, 225, 300),
        "NAAG's Find my AG card reads \"Nick Brown Washington\" beside this photograph, the "
        "card's own 225x300 size (ag-WA-Brown-Nick-225x300.png, uploaded 2025-01); a single "
        "head-and-shoulders portrait."),
    ("WI", "ag"): _naag_card(
        "Josh Kaul", "2020/09/ag-WI-kaul-225x300.jpg", (8850, 225, 300),
        "NAAG's Find my AG card reads \"Josh Kaul Wisconsin\" beside this photograph, the "
        "card's own 225x300 size (ag-WI-kaul-225x300.jpg, uploaded 2020-09); a single head-"
        "and-shoulders portrait."),
    ("WY", "ag"): _naag_card(
        "Keith Kautz", "2025/07/ag-WY-Kautz-Keith-2025-225x300.png", (29024, 225, 300),
        "NAAG's Find my AG card reads \"Keith Kautz Wyoming\" beside this photograph, the "
        "card's own 225x300 size (ag-WY-Kautz-Keith-2025-225x300.png, uploaded 2025-07); a "
        "single head-and-shoulders portrait."),
}

# Campaign websites that must never be linked, keyed on the host the FEC
# committee registered (lower case; a key without "www." also covers the
# "www." form). The FEC keeps whatever site a committee once filed, and a
# lapsed campaign domain gets bought: on 2026-10-01 seven served gambling pages
# under a candidate's name. Each value is (kind, date checked, what was seen).
# "hijacked" entries must never come back. "dead" entries - the host does not
# exist in DNS, the hosting platform says the site is gone, or the domain is
# parked - and "unrelated" ones - it answers, with a site that is not a
# campaign - may be removed once the committee files a working address;
# validate reports any entry that no longer matches a cached site.
BLOCKED_CAMPAIGN_HOSTS = {
    "maxinewatersforcongress.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "tedlieu.com": ("hijacked", "2026-10-01", "serves a gambling page"),
    "electjimbaird.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "troycarter4congress.com": ("hijacked", "2026-10-01", "serves an online-casino page"),
    "suozziforcongress2024.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "votemikefrance.com": ("hijacked", "2026-10-01", "serves a gambling page under his name"),
    "lukebronin.com": ("hijacked", "2026-10-01", "redirects to a gambling site"),
    "benniegthompson.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.plaskettforcongress.org": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.steilforwisconsin.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "cleofields.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.shreveforcongress.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "davetaylorforcongrss.com": ("dead", "2026-10-01", "NXDOMAIN; the filing misspells it"),
    "capitolforsenate.com": ("dead", "2026-10-01", "NXDOMAIN; the filing misspells it"),
    "www.hallieforarkansas.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "lanciaforcongress2026.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "infoforpurviforcongress.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.raymondesmithjr.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "www.tonyguyforcongress.com": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "johndeatonforsenate.co": ("dead", "2026-10-01", "NXDOMAIN at two resolvers"),
    "burbridgeforri.com": ("dead", "2026-10-01", "Squarespace 'Website Expired' page"),
    "tanianymanforcongress.com": ("dead", "2026-10-01", "Wix 'domain not connected' page"),
    # Found by `enrich`, which reads every linked committee site, and each
    # confirmed by hand on 2026-10-02.
    "joshweil.us": ("hijacked", "2026-10-02",
                    "www and bare both 301 through other domains to an Indonesian "
                    "slot-gambling page"),
    "dannymintonfortexas.com": ("dead", "2026-10-02",
                                "parked: a script sends visitors to a registrar's parking lander"),
    "marklambforcongress.com": ("dead", "2026-10-02",
                                "parked: a script sends visitors to a registrar's parking lander"),
    "angusformaine.com": ("dead", "2026-10-02", "every form of the address answers HTTP 404"),
    "jakeforma.com": ("dead", "2026-10-02", "every form of the address answers HTTP 404"),
    "drkumar4congress.com": ("dead", "2026-10-02", "every form of the address answers HTTP 404"),
    "abudahbisa.org": ("unrelated", "2026-10-02",
                       "an electronics shop's page; nothing about a campaign"),
    # From the 2026-10-17 reader audit, each confirmed that day at 1.1.1.1
    # and 8.8.8.8 and fetched again by hand.
    "trevordforme.com": ("hijacked", "2026-10-17",
                         "www and bare 302 to ww38.trevordforme.com on a parking network "
                         "(103.224.212.210); one browser was sent to a 'Security Check' "
                         "software download, another saw 'This domain may be for sale'"),
    "rickwallenforcongress.com": ("hijacked", "2026-10-17",
                                  "301 to www.leopard-outpost.com, an unrelated domain that "
                                  "does not exist in DNS (NXDOMAIN at both resolvers)"),
    "zabelforcongress.com": ("dead", "2026-10-17", "www and bare NXDOMAIN at two resolvers"),
    "johnmcbride4congress.com": ("dead", "2026-10-17",
                                 "www and bare SERVFAIL at two resolvers: nobody can reach it"),
    "drkednermaximeforcongress.com": ("dead", "2026-10-17",
                                      "the domain is registered but neither www nor bare has "
                                      "an address record at two resolvers"),
    "gordonchaffin.com": ("unrelated", "2026-10-17",
                          "'High Skill Dog Care', a business page; nothing about a campaign"),
    # Found by `enrich` on 2026-11-01 and fetched again by hand that day.
    "danielbutierez4congress2024.com": ("dead", "2026-11-01",
                                        "parked: www and bare serve only a script sending "
                                        "visitors to /lander, GoDaddy's parking lander"),
}

# Local governments' websites, as the Census Bureau's 2022 listing gives them,
# that must not be linked, keyed on the host (lower case; a key without
# "www." also covers the "www." form). `localgov --check-sites` withdraws
# what it finds on its own (data/local_sites.json, kyc/localsites.py); an
# entry here is a person's look, which no later check undoes - the kind is
# one of the check's withdrawn verdicts, or "unrelated", which only a look
# gives (localsites.UNRELATED). The first were opened in headless Chrome on
# 2026-10-17 by the reader-side audit and again by its verifier (LINKS-07,
# TRUST-07); each later group says who read it and when. The build warns
# about an entry no listed address matches.
BLOCKED_LOCAL_HOSTS = {
    "clintonct.com": ("gambling", "2026-10-17",
                      "Town of Clinton, CT: redirects to id-pgdemoslot.com, 'Demo Slot'"),
    "corralesnm.org": ("gambling", "2026-10-17",
                       "Village of Corrales, NM: redirects to a 'Salju4d: Link Slot' page"),
    "alvaok.org": ("gambling", "2026-10-17", "City of Alva, OK: a 'Sweepstakes Casinos' page"),
    "mcgrathalaska.net": ("gambling", "2026-10-17",
                          "City of McGrath, AK: redirects through two domains to laskar138, 'SLOT88'"),
    "vermilionparishpolicejury.com": ("gambling", "2026-10-17",
                                      "Parish of Vermilion, LA: an 'SBOBET88 ... Judi Bola' page"),
    "haccga.com": ("gambling", "2026-10-17",
                   "Clayton County Housing Authority, GA: redirects to qh88, a betting site"),
    "bismarck.org": ("parked", "2026-10-17", "City of Bismarck, ND: an empty Sedo-parked page"),
    "rutlandcity.com": ("expired", "2026-10-17",
                        "City of Rutland, VT: 'This domain is expired'; a parking page of links"),
    "northcodorustwp.com": ("for-sale", "2026-10-17",
                            "Township of North Codorus, PA: a HugeDomains for-sale page"),
    "imperialne.com": ("for-sale", "2026-10-17", "City of Imperial, NE: a HugeDomains for-sale page"),
    "switzerlandcounty.com": ("for-sale", "2026-10-17",
                              "County of Switzerland, IN: redirects to forsale.godaddy.com"),
    "townofprovidencevillage.com": ("parked", "2026-10-17",
                                    "Town of Providence Village, TX: a script sends visitors to "
                                    "/lander, a registrar's parking page"),
    # Gambling seen in one passage of the page's text, which the check
    # leaves for a person (localsites.STICKY); each looked at on 2026-10-18
    # and its title or visible text read.
    "ci.yorba-linda.ca.us": ("gambling", "2026-10-18",
                             "City of Yorba Linda, CA: titled 'Bundaslot', Indonesian text offering "
                             "'Kasino Live & Dealer Togel' and a 'Sportsbook'"),
    "cityofpevely.org": ("gambling", "2026-10-18",
                         "City of Pevely, MO: titled 'MANTIS88: inovasi baru! kapten game online', "
                         "a product card reading 'Material: Slot Gacor'"),
    "kennedale.net": ("gambling", "2026-10-18",
                      "Kennedale ISD, TX: titled 'ZUMA78: Daftar sekarang', a login for 'RTP Slot'"),
    "mooresvillealabama.com": ("gambling", "2026-10-18",
                               "Town of Mooresville, AL: Indonesian text inserted in the page about "
                               "'platform togel online'"),
    "simontontexas.org": ("gambling", "2026-10-18",
                          "City of Simonton, TX: posts headed 'Slot Naga Mahjong: Sensasi Bermain "
                          "Game Slot Online'"),
    "whitehallcitygov.com": ("gambling", "2026-10-18",
                             "City of White Hall, IL: titled 'tiger227 ini sebuah permainan games "
                             "online', 'Min Depo 20.000 ... Maxwin'"),
    # Read on 2026-11-14 by this project's reader, an agent, as the project
    # (agent.USER_AGENT), at the review of the guide's source check: the
    # check called the first "ok" and could not name the second, and each
    # plainly is not the body's site. Every redirect is written without its
    # query.
    "roselandgov.org": ("unrelated", "2026-11-14",
                        "Town of Roseland, IN: read by this project's reader (an agent) on "
                        "2026-11-14: http://www.roselandgov.org/ redirects to "
                        "https://roselandgov.org/, HTTP 200, titled 'Roselandgov - All About "
                        "Everything', described as 'a blog that shares useful knowledge and "
                        "insights for everyone about Everything', its posts on films and national "
                        "news ('The Complicated Legacy of 'Forgetting Sarah Marshall' in the Age "
                        "of #MeToo'); no word of Indiana, the town, its council or its clerk"),
    "yellowstonecountry.org": ("elsewhere", "2026-11-14",
                               "Park County Travel Council Joint Powers Board, WY: read by this "
                               "project's reader (an agent) on 2026-11-14: "
                               "http://www.yellowstonecountry.org redirects through "
                               "https://dltracking.com/r, a tracking redirector, to "
                               "https://everydayconsumers.org/travel/national-parks-made-simple-a-"
                               "no-jargon-breakdown, HTTP 200, titled 'National Parks Travel Guide: "
                               "Simple Tips for Visitors', an article on national parks in general; "
                               "no word of Park County, Cody, Yellowstone Country or a travel "
                               "council"),
}

# A member's contact-form address that congress-legislators holds in a form
# no browser can open, keyed on bioguide id: {bioguide: (the source's value,
# the address used instead, evidence)}. Applied only while the source still
# holds exactly that value; validate reports an entry that no longer matches.
MEMBER_CONTACT_FORMS = {
    "F000484": ("hhttps://fine.house.gov/address_authentication?form=/contact/email-me",
                "https://fine.house.gov/contact/",
                "2026-10-17: the scheme 'hhttps' is a typo upstream, and the address "
                "with it corrected answers HTTP 404; the office's contact page answers 200"),
}

# YouTube names in congress-legislators that are neither a channel id (UC...)
# nor an @handle: legacy usernames, which youtube.com/user/<name> served.
# Most no longer do. Each was fetched on 2026-10-17, both as /user/<name>
# and as /@<name>, and an @handle kept only where its channel's own title
# names the member: {bioguide: (the source's value, "user" | "handle" |
# None, what was seen)}. None drops the link: neither form exists, or the
# value is not a name at all. validate lists any legacy name not here.
YOUTUBE_LEGACY_NAMES = {
    "A000148": ("RepAuchincloss", "handle", "/user/ 404; /@ is 'Rep. Auchincloss'"),
    "B001301": ("RepJackBergman", None, "/user/ and /@ both 404"),
    "B001318": ("YouTubeChannelID", None, "placeholder text upstream, not a channel"),
    "C001055": ("RepEdCase", "handle", "/user/ 404; /@ is 'Congressman Ed Case'"),
    "C001112": ("repcarbajal", "handle", "/user/ 404; /@ is 'Congressman Salud Carbajal'"),
    "C001115": ("RepCloudTX", "handle", "/user/ 404; /@ is 'Rep. Michael Cloud'"),
    "E000294": ("RepTomEmmer", "handle", "/user/ 404; /@ is 'Rep. Tom Emmer'"),
    "F000246": ("RepPatFallon", "handle", "/user/ 404; /@ is 'Rep. Pat Fallon'"),
    "K000377": ("SenMarkKelly", "handle", "/user/ 404; /@ is 'Senator Mark Kelly'"),
    "M001199": ("repbrianmast", "handle", "/user/ 404; /@ is 'Congressman Brian Mast'"),
    "R000609": ("Reprutherfordfl", "handle", "/user/ 404; /@ is 'Rep. John H. Rutherford'"),
    "R000610": ("RepGuyReschenthaler", None, "/user/ and /@ both 404"),
    "S001150": ("adamschiff", "user", "/user/ is 'Sen. Adam Schiff'; /@ 404"),
    "S001190": ("RepBradSchneider", "user", "/user/ is 'Rep. Brad Schneider'"),
    "S001200": ("repdarrensoto", "handle", "/user/ 404; /@ is 'Rep. Darren Soto'"),
    "W000790": ("senatorwarnock", "handle",
                "/user/ 404; /@ is 'Senator Reverend Raphael Warnock'"),
}

# YouTube @handles in congress-legislators that YouTube answers 404 for,
# with the handle the member's own House or Senate site links instead (None
# drops the link when the office links none). {bioguide: (the source's
# value, the handle the office links or None, date, what was seen)}. Applied
# only while the source holds exactly that value; validate reports an entry
# the source has moved past.
YOUTUBE_HANDLE_CORRECTIONS = {
    "H001100": ("@RepJeffHurd03", "@RepJeffHurd", "2026-10-17",
                "youtube.com/@RepJeffHurd03 answers 404; hurd.house.gov links "
                "youtube.com/@RepJeffHurd, which answers 200 with his floor speeches"),
}

# X handles in congress-legislators that X answers "User Profile Not Found"
# for, where the file holds no twitter_id to link the account by instead
# (an id follows a rename: x.com/i/user/827279765287559171 is Speaker
# Johnson's, 307 to SpeakerJohnson, where his RepMikeJohnson is 404).
# {bioguide: (the handle, date, what was seen)}. The handle is dropped while
# the source still holds exactly it with no id; validate reports an entry
# that no longer matches.
DEAD_X_HANDLES = {
    "M001219": ("JMoylanforGuam", "2026-10-17",
                "x.com/JMoylanforGuam answers 404 'User Profile Not Found', as a "
                "nonsense handle does, while x.com/SpeakerJohnson answers 200; "
                "congress-legislators lists no twitter_id for him"),
}

# A ballot page's link that redirects to the person's own article under a
# title without their surname (rule 33). Without an entry here such a link is
# withheld: "any living person's article" would also let a redirect to a
# spouse or a namesake through, and its infobox be quoted onto this profile.
# {profile id: (the title the link must land on, date, evidence)}.
ARTICLE_UNDER_ANOTHER_NAME = {
    "FEC_H4FL20098": ("Uncle Luke", "2026-10-17",
                      "FL-20's 2026 election page links 'Luther Campbell', which redirects to "
                      "'Uncle Luke'; that article (Q3267867) opens 'Luther Roderick Campbell "
                      "(born December 22, 1960), also known by his stage names Luke or "
                      "Uncle Luke'"),
}


def article_alias(profile_id):
    """The title a ballot link is known to land on for this profile, or None."""
    entry = ARTICLE_UNDER_ANOTHER_NAME.get(profile_id)
    return entry[0] if entry else None


# A portrait a person looked at on a campaign's own page, which the reader's
# words test cannot take (rule 38), keyed on the profile id: {"url": the file
# the page draws, "page", "read": the day it was looked at, "evidence": what
# the page says beside it}. The reader still takes it only from that
# campaign's site read as theirs (rules 38, 39), only while the page draws
# that very file, and only portrait-shaped; one over the caps is shown all
# the same, lighter where it can be (rule 87); validate reports an entry no
# read site offers.
# The 2026-10-19 photo research's check found two genuine likenesses refused:
# Brian James Miller's, whose alt text runs his names together
# ("BrianMiller-5.jpg"), which the reader now reads, and Justin Murphy's,
# whose alt text names the campaign ("for senate") as a wordmark's does.
CAMPAIGN_PORTRAITS = {
    "CAND_40": {
        "url": "https://jerseyjustin4senate.org/wp-content/uploads/2024/02/D70_8732-Web-684x1024.webp",
        "page": "https://jerseyjustin4senate.org/",
        "read": "2026-10-25",
        "evidence": "alt text \"justin murphy for senate\" on the campaign's home page; one man in "
                    "a suit, 684x1024, 43 KB (looked at 2026-10-25)"},
}


# A Wikidata item's label that names a nominee by a nickname their profile
# and filing do not write (kyc/nominee_photos.py), keyed on the profile id:
# {"label": the label exactly as the item writes it, "evidence": where the
# person uses that name - their campaign's own site or ballot listing - and
# the day it was read}. Without one, "Drew Williams" is not "WILLIAMS, JOHN
# ANDREW": the label is all that ties an item to a person besides the id
# (rule 82), and a nickname table would let "Bob" stand for any Robert.
# An entry may also carry "first": a short form of the first name the
# campaign's own site writes ("Alex" for a filed "Alexander"), with that
# site's page and the day in its "evidence"; the narrow first-name route of
# a campaign's site (enrich.first_names, rule 38) reads it beside the
# profile's and the filing's own first names, and reads no other.
PORTRAIT_NAME_FORMS = {}


# An election office's guide that prints a candidate under a short form of
# the name their filing, profile or the office's list writes
# (kyc/guide_photos.py), keyed on (state, the guide's name exactly as
# printed): (the person it stands for - "person:<profile id>" or
# "candidate:<state>:<office>:<name shown>" - and the evidence tying the
# two, with the day it was read). Without one, a guide's name joins only
# where its words are the person's (rule 62). "David Russ" was not "RUSS,
# DAVID HONORABLE" until "Honorable" was read as the honorific it is
# (candidates._HONORIFICS, 2026-10-25); the evidence below stays, read.
GUIDE_NAME_FORMS = {
    ("OR", "David Russ"): (
        "person:FEC_H2OR01240",
        "the State Voters' Pamphlet's statement for David Russ, Republican, US "
        "Representative, 6th District (VP_G26-Book12 page 35, read 2026-10-25), prints "
        "'RussIsForUS.com' and is 'furnished by David Russ Is For US'; the filing RUSS, DAVID "
        "HONORABLE (H2OR01240) names that site, russisforus.com, as its campaign's (FEC "
        "Form 1)"),
    ("UT", "Riley Owen"): (
        "person:FEC_H6UT01244",
        "Utah's Voter Information Pamphlet, page 9 (read 2026-11-01), headed 'Congressional "
        "District 1' and 'Riley Owen', prints 'info@utahriley.com' and 'utahriley.com'; the "
        "filing OWEN, RILEY MONTGOMERY (H6UT01244) is the only Owen in UT-1, and its own "
        "committee, C00940411, is 'RILEY OWEN FOR UTAH' (FEC Form 1)"),
    ("UT", "Kent S. Udell"): (
        "person:FEC_H6UT03182",
        "Utah's Voter Information Pamphlet, page 16 (read 2026-11-01), headed 'Congressional "
        "District 3' and 'Kent S. Udell', prints 'kentudell.com'; the filing UDELL, KENT DR. "
        "(H6UT03182) names that site, KENTUDELL.COM, as its campaign's, and its committee "
        "C00938811 is 'KENT STEWART UDELL FOR CONGRESS' (FEC Form 1)"),
    ("AZ", "Monica Alponte"): (
        "person:FEC_H6AZ01488",
        "the Citizens Clean Elections Commission's candidate list (read 2026-11-01) prints "
        "'Monica Alponte', Libertarian, under 'U.S. House of Rep. - District 1'; the filing "
        "ALPONTE, MONICA MARIA (H6AZ01488) is the only Alponte in AZ-1, and its own committee, "
        "C00945287, is 'MONICA ALPONTE FOR CONGRESS' (FEC Form 1)"),
    ("UT", "Robert Moesinger"): (
        "person:FEC_H6UT02531",
        "Utah's Voter Information Pamphlet, page 13 (read 2026-11-01), headed 'Congressional "
        "District 2' and 'Robert Moesinger', prints 'https://www.improveourelections.org/'; "
        "the filing MOESINGER, ROBERT MICHAEL (H6UT02531) names that site as its campaign's, "
        "and its committee C00944306 is 'ROBERT MOESINGER FOR CONGRESS' (FEC Form 1)"),
}


# The mark on a NOT_A_PORTRAIT entry whose only finding is other people in
# the frame - behind, beside or in part (photos.others_only). The owner's
# background-people rule (2026-10-25: "probably better to leave out
# background people") is for candidates' and officials' photographs; asked
# the same day about the federal judges' Senate Judiciary hearing stills, he
# said "keep": the judge is plainly the subject. So such an entry does not
# withhold a judge's portrait - a federal judge's (judge_links) or a state
# justice's from the court's own roster (court_photos), a judge as well -
# and every other entry, and every other check, still does
# (photos.applies). A picture of a person - a framed photograph on a shelf
# or a wall, a poster, a book jacket - is not a person in the frame and
# refuses nothing (decided for the owner, 2026-10-25). A screen showing a
# face is refused like a person in the frame (the owner's decision of
# 2026-11-01): a rally's screen is usually a live feed of someone there, so
# Donna Miller's stays refused.
OTHERS_IN_FRAME = "others in the frame"

# Images that a route would take as a person's portrait but that are not one,
# keyed on the image URL: (date checked, what it shows), with OTHERS_IN_FRAME
# third where other people in the frame are all it shows. One list for every
# route (rule 38): a campaign's own site (`enrich`), a nominee's Wikidata item
# or legislature card (nominee_photos), an attorney general's office
# (officers.add_ag_photos), a court's page (court_photos), a statewide
# candidate's guide or Commons file (statewide_photos, keyed on the Commons
# upload address), a judge's Commons file (judge_links); every route asks it,
# of a record kept from an earlier read as well as of one read now. The
# rules turn away logos, share cards, merchandise and most group shots by
# file name and shape; these passed both, and only a look tells. The
# refreshes re-read every source, so a correction made by editing a cache
# would not last. validate reports an entry no cached route offers.
#
# One test for every image a person looks at (rule 38, the review of PR
# #134): a photograph of the candidate alone - nobody else in the frame, even
# in the background or in part (the owner, 2026-10-25: "probably better to
# leave out background people") - whose face, brow to chin, is at
# least a tenth of the height of the 4:5 card that crops it from the top -
# 6.5px of the state pages' 65px phone card, where eyes and a mouth can be
# made out - is a likeness and is shown ("more content", the owner's
# decision of 2026-10-25). Anything else is here, with what was seen and
# measured: another person in the frame, a scene, a full-length figure. A
# picture of a person behind them (a framed photograph, a poster, a book
# jacket) is not another person: John Giles's and Dave Sunday's
# photographs, refused for one on 2026-10-25, are shown again. For a judge,
# the background-people rule does not apply (OTHERS_IN_FRAME above).
# Measured on 2026-10-25, Brian Bengs's park photograph (a seventh and a
# half) and Jena Nelson's street portrait (a ninth) pass; Jamie Davis by his
# tractor (an eleventh), Lauren Jewett by a seal (a fifteenth) and Jordan
# Herrera in a vehicle's hatch (a thirteenth) do not.
NOT_A_PORTRAIT = {
    # Utah's Voter Information Pamphlet, page 13 (read 2026-11-01), hosted
    # here as the guide's file (guide_photos, rule 101).
    "photos/090c1a605a8a18bd1456.jpg":
        ("2026-11-01", "Robert Moesinger (UT-2): another person's long hair at the lower left "
                       "edge, cropped from a group photograph", OTHERS_IN_FRAME),
    # Offered by the narrow first-name route (enrich.first_name_portraits,
    # read 2026-11-01): "bethany-portrait.jpg" on her campaign's home page.
    "https://www.bethanymannforcongress.com/assets/bethany-portrait.jpg":
        ("2026-11-01", "Bethany Mann (MO-3): a close selfie outdoors; two other people, one in a "
                       "sun hat, behind her at the right edge", OTHERS_IN_FRAME),
    "https://tomsmithformi.com/assets/IMG_0051_1786034274828-B2BJy3rU.jpg":
        ("2026-11-01", "Tom Smith (MI-8): standing full length before flags on a stage, his "
                       "face brow to chin about a fifteenth of the card's height"),
    # The Clean Elections Commission's candidate list (guide_photos, read
    # 2026-11-01).
    "https://www.azcleanelections.gov/Custom/Picture/2556":
        ("2026-11-01", "JoAnna Mendoza (AZ-6): a bearded man in a white shirt behind her at "
                       "the upper left", OTHERS_IN_FRAME),
    "https://kaileebuller.com/wp-content/uploads/2026/03/Buller.jpg":
        ("2026-10-02", "a family photograph: four people in the snow"),
    "https://rickbrattin.com/wp-content/uploads/2026/02/Brattin-extended-scaled.png":
        ("2026-10-02", "a hunting scene; no face at card size"),
    "https://run.imgix.net/f9df0b31-2ce0-4b8a-9a5d-4765b3afb86b/ab4b5c88-afea-4c83-9eb7-311e7cead6a6/ab4b5c88-afea-4c83-9eb7-311e7cead6a6.jpg?ixlib=js-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=0%2C777%2C3648%2C3648&auto=compress%2Cformat&fit=fillmax&w=2048&q=75&s=cb469615bb857ebbc21f8c8780cda69b":
        ("2026-10-25", "Elizabeth Lee: a rally - speaking through a megaphone, other people "
                       "behind her"),
    "https://run.imgix.net/744b9e51-6fcd-4260-a2b5-35da9e4ad0b4/19462903-8b50-4a50-9e43-b99bb2febeed/19462903-8b50-4a50-9e43-b99bb2febeed.jpg?ixlib=js-3.8.0&bri=0&con=0&sat=0&high=0&shad=0&usm=0&rect=0%2C0%2C4024%2C6048&auto=compress%2Cformat&fit=fillmax&w=2048&q=75&s=0c9c30e09b5531bbdff48c00dd0dfda7":
        ("2026-10-25", "Michaela Barnett: a festival stall - holding up a T-shirt under a county "
                       "party's banner, another person behind her and one seated"),
    "https://shaunfinnieforcongress.com/wp-content/uploads/2026/05/Selme-Finnie-img.jpg":
        ("2026-10-25", "two people: Shaun Finnie with someone else ('Selme-Finnie')"),
    "https://jordanjherrera.com/wp-content/uploads/2025/05/Jordan_Herrera_IMG_9126-768x1024.jpeg":
        ("2026-10-25", "Jordan Herrera: seated in a military vehicle's hatch, his face a "
                       "thirteenth of the card's height"),
    # Found once heavy portraits were shown again (PR #134 review), and looked at.
    "https://samgallucci.com/assets/samfamily-BetoMA7c.webp":
        ("2026-10-25", "Sam Gallucci: a family photograph, seventeen people on a beach"),
    "https://irp.cdn-website.com/a2163ddd/dms3rep/multi/opt/MCGOWAN-BIO-1406h.png":
        ("2026-10-25", "Chris McGowan: a page of biography text under the campaign's logo"),
    "https://assets.nationbuilder.com/themes/69d46ee99be3286671f3d5a8/attachments/original/1776836856/11089a203ea7bb260717a77ab963cb40942791be.png?1776836856":
        ("2026-10-25", "Greg Stoker: a halftone street scene, several people holding signs"),
    # Judged by the one test above (the review of PR #134).
    "https://jamieforlouisiana.com/assets/general/tractor-portrait.jpg":
        ("2026-10-25", "Jamie Davis: a full-length figure leaning on a tractor, his face an "
                       "eleventh of the card's height"),
    "https://laurenjewett.com/images/campaign/lauren-jewett-jefferson.png":
        ("2026-10-25", "Lauren Jewett: a full-length figure beside the Clerk of Court's seal, her "
                       "face a fifteenth of the card's height"),
    # The owner, 2026-10-25: "probably better to leave out background people".
    # Every photograph shown by the routes the owner's brief named that can
    # take a picture not made in a studio was looked at on 2026-10-25 (701
    # of them; not the judges' item route, CLAUDE.md rule 38); these show
    # someone else, in the background or in part. The 48 judges' hearing
    # stills refused that day are shown again by the owner's "keep" (above),
    # as are Judges Orso's and Powell's, refused in the review that followed.
    # Keyed as each route asks: a
    # campaign's or an office's file by its address, a Commons file by its
    # upload address.
    # a campaign's own site (enrich): 1.
    "https://raw.githubusercontent.com/dpconway4-bot/pat-moore-for-congress/main/assets/pat-moore-headshot.jpg":
        ("2026-10-25", "Patricia Ann Moore (LA): the House chamber behind her, with members seated",
         OTHERS_IN_FRAME),
    # the article a profile's bioguide id or ballot page links (portraits): 33.
    "https://upload.wikimedia.org/wikipedia/commons/7/7e/Adam_Hollier_at_Whitmer's_inauguration_(January_1,_2023)_(cropped).jpg":
        ("2026-10-25", "Adam Hollier (MI): a person standing by the tents at the right",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/7/79/2025_Virginia_State_of_the_Commonwealth,_Youngkin_procession_(cropped).jpg":
        ("2026-10-25", "Adele McClure (VA): people behind her", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/0/09/Adrian_Boafo_Feb2023.jpg":
        ("2026-10-25", "Adrian Boafo (MD): another person's arm raised at the left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/6/6a/Amy_McGrath_Event-_(49220643717)_1.jpg":
        ("2026-10-25", "Amy McGrath (KY): another person's hair at the left edge",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/2/26/Brad_Lander.jpg":
        ("2026-10-25", "Brad Lander (NY): a person behind him at the left", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/d/d8/Brent_Taylor_(Tennessee_politician).jpg":
        ("2026-10-25", "Brent Taylor (TN): people at the stalls behind him at the left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/8/82/Cameron_Kasky_3.jpg":
        ("2026-10-25", "Cameron Kasky (NY): a crowd around him", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/0/0f/Chris_Stigall_2017_(cropped).jpg":
        ("2026-10-25", "Chris Stigall (MO): people behind him at the left, one with a camera",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/9/92/Dale_Romans.jpg":
        ("2026-10-25", "Dale Romans (KY): people on the track behind him", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/e/e0/Emanuel_Jones_(46948866015).jpg":
        ("2026-10-25", "Emanuel Jones (GA): people in purple shirts behind him",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/9/90/Heather_Keeler_at_DFL_post-Roe_Agenda_Press_Conference_(cropped).jpg":
        ("2026-10-25", "Heather Keeler (MN): another person's hair at the foot of the frame",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/7/74/JD_Ford,_Indy_Pride_Parade_2023_(2)_(cropped).jpg":
        ("2026-10-25", "J.D. Ford (IN): a crowd at a parade around him", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/7/70/James_Talarico_Press_Conference_(cropped).jpg":
        ("2026-10-25", "James Talarico (TX): a person at the right edge", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/0/0f/Jay_Feely_by_Gage_Skidmore.jpg":
        ("2026-10-25", "Jay Feely (AZ): audience heads at the foot of the frame",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/2/22/Michigan_Senator_Jeremy_Moss_2019.jpg":
        ("2026-10-25", "Jeremy Moss (MI): people behind him in the room", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/8/8c/JillianGilchrestFebruary2026Cropped.jpg":
        ("2026-10-25", "Jillian Gilchrest (CT): people standing behind her in the chamber",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/6/60/Colorado_State_Senator_Julie_Gonzales_2025_(cropped).jpg":
        ("2026-10-25", "Julie Gonzales (CO): a person standing in the chamber behind her, right",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/f/f3/Julie_Won_(54199169237)_(cropped).jpg":
        ("2026-10-25", "Julie Jaehee Won (NY): a man standing behind her", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/2/23/Justin_J_Pearson_August_2023.jpg":
        ("2026-10-25", "Justin J. Pearson (TN): a man's shoulder behind him at the left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/0/06/Ken_Paxton_(54816860552)_(cropped).jpg":
        ("2026-10-25", "Ken Paxton (TX): a crowd behind him", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/a/a3/La_Shawn_K._Ford_on_11_December_2023_-_8_(cropped).jpg":
        ("2026-10-25", "La Shawn K Ford (IL): people standing behind him, a woman's hand on his "
                       "shoulder", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/c/ca/Luke_Bronin_(42831415392).jpg":
        ("2026-10-25", "Luke Bronin (CT): a man in a blue shirt behind him, left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/4/47/Mallory_McMorrow_in_2023_-_8R4A5252_(cropped).jpg":
        ("2026-10-25", "Mallory McMorrow (MI): a person in blue behind her at the top left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/f/f2/Mark_Teixeira_basepaths_2011.jpg":
        ("2026-10-25", "Mark Charles Teixeira (TX): spectators in the stands behind him",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/e/ec/Matt_Strickler,_ribbon_cutting.jpg":
        ("2026-10-25", "Matt Strickler (VA): another person's shoulder at the left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/3/35/Mike_LiPetri_(2024_Italian_Heritage_Street_Festival)_(cropped).jpg":
        ("2026-10-25", "Mike Lipetri (NY): people behind him at the foot of the frame",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/0/06/William_V_Bill_Bell_Way_Dedication_Ceremony_Nida_Allam.jpg":
        ("2026-10-25", "Nida Allam (NC): people behind her at the left", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/b/bf/Phil_Lyman_at_Riley_Gaines_Speech_(cropped).jpg":
        ("2026-10-25", "Phil Lyman (UT): another person at the right edge", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/6/6d/Unveiling_the_NYS_Historic_Marker_Robert_Smullen.jpg":
        ("2026-10-25", "Robert Smullen (NY): another man's shoulder at the right",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/0/09/Robin_Ficker_(35598540490).jpg":
        ("2026-10-25", "Robin Ficker (MD): another man's shoulder at the left, and a person behind",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/b/b3/Rushern_Baker,_May_2017.jpg":
        ("2026-10-25", "Rushern L Baker III (MD): a man behind him at the left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/e/ea/Sharif_Street_-_18901_gov_minwage_dz_030_(cropped).jpg":
        ("2026-10-25", "Sharif Street (PA): a white-haired man behind him at the left",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/0/00/(03-12-24)_Taylor_Darling.jpg":
        ("2026-10-25", "Taylor R Darling (NY): people in white shirts behind her",
         OTHERS_IN_FRAME),
    # a statewide candidate's guide or Commons file (statewide_photos): 4
    # (John Giles's, refused for framed photographs, is shown again).
    "https://www.azcleanelections.gov/Custom/Picture/2469":
        ("2026-10-25", "Duwayne Collier (AZ secretary of state candidate): a child's face and "
                       "another person's arm (the Clean Elections guide photograph, cropped from a "
                       "family snapshot)", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/7/7d/Heather_Baxter_by_Gage_Skidmore.jpg":
        ("2026-10-25", "Heather Baxter (SD secretary of state candidate): a person seated behind her "
                       "at the right", OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/2/23/Mayes_Middleton_by_Gage_Skidmore_(cropped).jpg":
        ("2026-10-25", "Mayes Middleton (TX attorney general candidate): people behind him at the "
                       "left and right", OTHERS_IN_FRAME),
    "https://www.nass.org/sites/default/files/styles/secretary/public/2023-03/MA-Galvin-2023.jpg?itok=7JV1GBsz":
        ("2026-10-25", "William Francis Galvin (MA secretary of state candidate): people walking on "
                       "the path behind him", OTHERS_IN_FRAME),
    # an attorney general's office (officers.add_ag_photos): none (Dave
    # Sunday's, refused for a framed snapshot on his bookcase, is shown again).
    # A legislator's card (Open States's file or the legislature's,
    # legislature.photo_kind): the 267 cards credited to a caucus were looked
    # at on 2026-10-25, when the owner allowed caucus credits, and these two
    # refused. The live check after PR #139 found more at full size (the
    # sweep had looked at the cards), so each of Connecticut's House
    # Democrats' 65 files was opened at full size on 2026-10-25; these 8 show
    # someone else. Blurred shapes at the chamber's desks in Kate Farrar's,
    # Robin Comey's and Maryam Khan's are the desks' flags and microphones (as
    # Hubert Delany's sharp chamber shows them), not people.
    "https://www2.housedems.ct.gov/Genga/images/Genga_HS.jpg":
        ("2026-10-25", "Henry Genga (CT House): at his desk in the chamber, Rep. Conway seated "
                       "behind him", OTHERS_IN_FRAME),
    "https://www2.housedems.ct.gov/Haddad/images/Haddad_19.jpg":
        ("2026-10-25", "Gregg Haddad (CT House): at his desk in the chamber, two colleagues "
                       "beside and behind him", OTHERS_IN_FRAME),
    "https://www2.housedems.ct.gov/Gonzalez/images/Gonzalez_HS.jpg":
        ("2026-10-25", "Minnie Gonzalez (CT House): at her desk in the chamber, members seated "
                       "and standing behind her", OTHERS_IN_FRAME),
    "https://www2.housedems.ct.gov/SanchezM/images/SanchezM_HS.jpg":
        ("2026-10-25", "Manny Sanchez (CT House): two people standing in the hall behind him, at "
                       "the left", OTHERS_IN_FRAME),
    "https://www2.housedems.ct.gov/MorrinBello/images/MorrinBello_HS.jpg":
        ("2026-10-25", "Amy Morrin Bello (CT House): in the Legislative Office Building's atrium, "
                       "a person walking on the balcony behind her at the left and another at the "
                       "right", OTHERS_IN_FRAME),
    "https://www2.housedems.ct.gov/Garibay/images/Garibay_HS.jpg":
        ("2026-10-25", "Jane Garibay (CT House): in the atrium, two people's legs on the balcony "
                       "at the top of the frame", OTHERS_IN_FRAME),
    "https://www2.housedems.ct.gov/Elliott/images/Elliott_HS.jpg":
        ("2026-10-25", "Josh Elliott (CT House): in the atrium, a person in a blue shirt on the "
                       "floor below at the lower right", OTHERS_IN_FRAME),
    "https://www2.housedems.ct.gov/Gresko/images/gresko_HS.jpg":
        ("2026-10-25", "Joe Gresko (CT House): on a beach, a person walking at the water's edge "
                       "behind him at the left", OTHERS_IN_FRAME),
    # The PR #139 review, looked at again on 2026-10-25. A refusal promoted
    # James Talarico's campaign photograph, which nobody had looked at, in
    # place of his Commons one (validate's portrait-fallback-unseen now
    # names any such photograph); and the sweep missed JoCasta Zamarripa's.
    # (Two judges' hearing stills and a framed photograph behind Adam Hamawy,
    # refused in that review too, are shown again: a judge by the owner's
    # "keep", a picture as no person. Hamawy's was not among the two the
    # brief named; looked at again, it shows him alone before a framed
    # photograph on the wall.)
    "https://jamestalarico.com/wp-content/uploads/2025/09/james-talarico-texas-education-819x1024.webp":
        ("2026-10-25", "James Talarico (TX): bent over a desk helping a child in a classroom, "
                       "two more children in the frame, his face turned down"),
    # The uncut file the refused crop came from, which his Wikidata item
    # carries (nominee_photos' Wikidata route then offered it).
    "https://upload.wikimedia.org/wikipedia/commons/8/8b/James_Talarico_Press_Conference.jpg":
        ("2026-10-25", "James Talarico (TX): another person's shoulder at the right edge",
         OTHERS_IN_FRAME),
    "https://upload.wikimedia.org/wikipedia/commons/f/f0/JoCasta_Zamarripa_(51017746066).jpg":
        ("2026-10-25", "JoCasta Zamarripa (WI secretary of state candidate): another person's "
                       "hand and fingers at the left edge", OTHERS_IN_FRAME),
    # A screen is not a framed picture: at a rally it is usually a live feed
    # of a person there, and the owner ruled on 2026-11-01 that a face on one
    # is refused like a person in the frame. Her shown portrait is the
    # county's (portraits.json, curated).
    "https://upload.wikimedia.org/wikipedia/commons/a/a1/Cook_County_Commissioner_Donna_Miller_at_May_Day_2025.jpg":
        ("2026-10-25", "Donna Miller (IL): a person's face on the rally's LED screen behind her, "
                       "at the upper right", OTHERS_IN_FRAME),
    # The same California National Guard photograph under its new name (the
    # old one answered 404 and was never looked at by the sweep), offered
    # again when her portrait was resolved anew.
    "https://upload.wikimedia.org/wikipedia/commons/6/62/Jacqui_Irwin_(cropped)_150302-Z-WQ610-_(16698067641).jpg":
        ("2026-10-25", "Jacqui V Irwin (CA): another woman seated at the right edge, and another "
                       "person's hair at the left", OTHERS_IN_FRAME),
}

# Photographs that came forward when a person refused the one before them
# (NOT_A_PORTRAIT), from a route that can take a picture not made in a
# studio, each looked at and found to be of the person alone, keyed on the
# address shown: (date, what was seen). validate names any other such
# photograph (portrait-fallback-unseen) - a refusal must never put a
# photograph nobody has looked at in front of readers (the PR #139 review:
# James Talarico's classroom photograph).
SEEN_AFTER_A_REFUSAL = {
}

# A statewide candidate's own article's lead image that came forward when
# the reader refused the image the race's infobox sets beside the nominee -
# for its name (a scene, no surname), its licence or its shape
# (statewide_photos.wiki_photo; the record says what it stands in place of,
# ``inPlaceOf``). Nobody has seen such a file when the Monday read takes it,
# and the refresh publishes without a person (the PR #213 review: Wes
# Moore's and Bruce Blakeman's would have been shown unlooked), so it waits
# off the page, named by the build, until a person has looked at it and
# recorded it here, keyed on the Commons upload address as its file page
# reads: (the day, the cache's key for the candidate, what was seen - the
# candidate alone, nobody else in the frame, and the face, brow to chin, as
# a share of the 4:5 card that crops it from the top, as rule 38 measures it
# - and the file's own pixel size as Commons gives it, which ties the look
# to the picture: another photograph saved over the name goes back behind
# the gate). One that fails the look goes in NOT_A_PORTRAIT instead. The
# build reports an entry whose race has been read again since and no longer
# brings the file forward (statewide_photos.stale_looks).
SEEN_ARTICLE_LEADS = {
    "https://upload.wikimedia.org/wikipedia/commons/b/b8/"
    "Governor_Ned_Lamont_of_Connecticut,_official_portrait.jpg":
        ("2026-11-10", "CT|governor|Ned Lamont",
         "The lead image of the article 'Ned Lamont': one man alone, head and shoulders, in a "
         "grey suit, a light blue shirt and a patterned tie, before a wall with a plaque and a "
         "piece of ironwork; nobody else in the frame; his face about a fifth of the card's "
         "height (about 130 of the 500x685 rendition's 685px, the card its top 625px). In "
         "place of the race's infobox's 'Gold Star Bridge Visit with ... Pete Buttigieg "
         "(cropped).jpg', refused by its name.", {"width": 1453, "height": 1990}),
    "https://upload.wikimedia.org/wikipedia/commons/c/c3/Wes_Moore_Official_Governor_Portrait.jpg":
        ("2026-11-10", "MD|governor|Wes Moore",
         "The lead image of the article 'Wes Moore': one man alone, head and shoulders, in a "
         "dark suit, a white shirt and a red tie, before a blue backdrop and Maryland's flag; "
         "nobody else in the frame; his face about a fifth of the card's height (about 130 of "
         "the 500x625 rendition's 625px). In place of the race's infobox's 'Governor Kuroiwa "
         "and Japanese Delegation (cropped2).jpg', refused by its name.",
         {"width": 1638, "height": 2048}),
    "https://upload.wikimedia.org/wikipedia/commons/f/fe/Blakeman_Profile_Picture.jpg":
        ("2026-11-10", "NY|governor|Bruce A. Blakeman",
         "The lead image of the article 'Bruce Blakeman': one man alone, head and shoulders, "
         "in a blue suit and a striped tie, the top of a microphone at the bottom edge, a "
         "blurred building behind; nobody else in the frame; his face about a quarter of the "
         "card's height (about 160 of the 500x578 rendition's 578px, all of which the card "
         "shows). In place of the race's infobox's 'Donald J. Trump delivers remarks on the "
         "economy at Rockland Community College ... (cropped).jpg', refused by its name.",
         {"width": 675, "height": 780}),
}

# A photograph a person chose for a candidate on a statewide ballot
# (kyc/statewide_photos.py, rule 91's fifth route: the owner's request of
# 2026-11-15, "lets try and fill those photos and any other missing from non
# eliminated canidates"), as CANDIDATE_PHOTOS is for a profile (rule 24).
# Keyed on the cache's own key for the candidate, "ST|office|name" with the
# name as the election office's list prints it (statewide_photos.key), never
# a name typed another way. Each entry has the same fields as a
# CANDIDATE_PHOTOS entry (photos.curated_problems): the file (url), the page
# that names them beside it, its words, whose it is (by; a Commons file's
# author and licence are read from its own page, never typed), why that page
# is this candidate's (tie), what a person saw (the candidate alone, nobody
# else in the frame, the face measured on the card), the day read, and for a
# file a legislature keys by its seat, the seat and the member it was read
# for (withheld once the roster seats someone else). ballotphotos reads
# each into data/statewide_photos.json as route "curated" (--curated-only
# reads these alone), weighed, and a Commons file credited from its file page
# and held to the licence test (statewide_photos.licence_doubt); NOT_A_PORTRAIT
# and PORTRAIT_LICENCE_DOUBTS withhold it as they do every route's. It stands
# only where the other four routes leave the candidate with none - the
# holder's office photograph, a member's by bioguide id, an official guide's
# (one hosted here included) and the race's article - and an entry those
# routes now picture, or for a name no list prints any more, is a warning
# (validate: stale-statewide-photo-override).
#
# The first entries are the photo sweep of 2026-11-17: the candidates for
# governor whom every route left with the silhouette, each photograph found
# by one reader, re-opened and confirmed by a second who read the page and
# fetched the file again as this project (its bytes, pixel size and sha256
# the same) and measured it on the card, and looked at again on a contact
# sheet.
STATEWIDE_PHOTOS = {
    # Fred Love
    "AR|governor|State Senator Fred Love": {
        "url": "https://arkleg.state.ar.us/Content/photos/2027/Senate/640_sm.jpg",
        "page": "https://arkleg.state.ar.us/Legislators/Detail?member=F.+Love",
        "words": "alt text \"Photo of Senator Love\", under the page's heading \"Senator "
                 "Fredrick J. Love (D)\", followed by \"District: 15\"; "
                 "page title \"Senator Fredrick J. Love (D) - Arkansas "
                 "State Legislature\"",
        "by": "Arkansas State Legislature (Arkansas General Assembly)",
        "tie": "Route 1(d). The article the race's own article links for him "
               "('Fredrick Love', recorded in statewide_photos.json articles for "
               "AR|governor|State Senator Fred Love) says in its own words: \"Fredrick "
               "J. Love is an American politician representing the 15th district in "
               "the Arkansas Senate since 2023 ... He was the Democratic nominee in "
               "the 2026 Arkansas gubernatorial election.\" The election office's list "
               "(Pulaski County notice, p. 3) prints him as \"State Senator Fred "
               "Love-DEM\". The Arkansas General Assembly's own member page for him "
               "(one of the links Open States lists for this member, "
               "ocd-person/b35d0a49..., district 15) names Senator Fredrick J. Love "
               "(D), District 15, beside the photograph. The file is keyed by the "
               "legislature's member number 640, not by seat (the same number as his "
               "senate.arkansas.gov/senators/640 page), so it is not a seat file.",
        "seen": "A studio head-and-shoulders portrait of one man alone, smiling, bald, "
                "grey beard, grey plaid suit and striped tie, plain grey mottled "
                "backdrop; nobody else in the frame. The same man as the Commons file "
                "in his article (Rep Fredrick J Love.jpg). Not a logo or graphic. A "
                "second reader looked again and measured: brow at about band 3.6, chin "
                "at about band 6.3 on the card: about 2.6 tenths (about 133 of 536 "
                "source px; one band = 53.6 px)",
        "read": "2026-11-17",
    },
    # Greg Lopez
    "CO|governor|Greg Lopez": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/c/c7/Greg_Lopez_118th_Con"
               "gress_portrait.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Greg_Lopez_118th_Congress_portra"
                "it.jpg",
        "words": "file description \"A portrait of Rep. Greg Lopez (R-CO) for the 118th "
                 "U.S. Congress.\"; file name \"Greg Lopez 118th Congress portrait.jpg\"; "
                 "in Category:Greg Lopez and used in the article 'Greg Lopez'",
        "tie": "Route 1(c). The 2026 Colorado gubernatorial election article links "
               "'Greg Lopez' for him (statewide_photos.json articles for "
               "CO|governor|Greg Lopez); that article's Wikidata item Q126910689 has "
               "Commons category 'Category:Greg Lopez' (P373), which holds this file, "
               "and the article itself uses it. The file page gives the author as the "
               "Office of the Clerk, U.S. House of Representatives, a government "
               "office, source https://clerk.house.gov/members/L000604, licence public "
               "domain (PD US Congress). Not the article's lead (File:Greg Lopez in "
               "2024.jpg, refused as public-domain-unsupported) and not in "
               "NOT_A_PORTRAIT or PORTRAIT_LICENCE_DOUBTS.",
        "seen": "The House's official studio portrait of one man alone: grey hair, "
                "smiling, dark suit, white shirt, red tie, on the plain blue backdrop "
                "of the Congress portraits; nobody else in the frame, no words or "
                "graphics. A second reader looked again and measured: brow at about "
                "band 4.0, chin at about band 7.8 on the card: about 3.8 tenths (one "
                "band = 41 source px)",
        "read": "2026-11-17",
    },
    # David Jolly
    "FL|governor|David Jolly": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/1f/David_Jolly.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:David_Jolly.jpg",
        "words": "file description \"Official portrait of David Jolly, the U.S. "
                 "representative for Florida's 13th congressional district.\"; file name "
                 "\"David Jolly.jpg\"; in Category:David Jolly",
        "tie": "Route 1(c). The 2026 Florida gubernatorial election article links "
               "'David Jolly' for him (statewide_photos.json articles for "
               "FL|governor|David Jolly); that article's Wikidata item Q15963996 has "
               "Commons category 'Category:David Jolly' (P373), which holds this file, "
               "the item's own image (P18). The file page gives the author as the U.S. "
               "House of Representatives, licence public domain (PD US Congress), "
               "source https://bioguide.congress.gov/search/bio/J000296. It is not the "
               "article's lead (File:David Jolly (3x4).jpg, refused as a licence doubt "
               "for naming no author) and not in NOT_A_PORTRAIT or "
               "PORTRAIT_LICENCE_DOUBTS. A person should know: the file page's source "
               "line also names a 'Hi-res file' on orlandoweekly.com beside the "
               "Biographical Directory's 'Low-res file with metadata' "
               "(https://bioguide.congress.gov/photo/67f56dbbfddc8a66d43f6b02.jpg); I "
               "fetched the Directory's file as this project and it is the same "
               "official portrait (same pose, pin, tie and blue backdrop, the "
               "Directory's a tighter crop), so the photograph is the House's work "
               "whatever copy the uploader took the larger bytes from.",
        "seen": "The House's official studio portrait of one man alone: dark hair "
                "greying at the sides, smiling, pinstriped suit with the House member's "
                "pin, white shirt, silver tie, plain blue backdrop; nobody else in the "
                "frame, no words or graphics. A second reader looked again and "
                "measured: brow at about band 4.0, chin at about band 6.2 on the card: "
                "about 2.2 tenths (one band = 62.5 px of the 500px rendition); "
                "comfortably over a tenth",
        "read": "2026-11-17",
    },
    # Therese Maria Terlaje
    "GU|governor|TERLAJE, Therese Maria": {
        "url": "https://guamlegislature.gov/wp-content/uploads/2025/02/TMT-768x960.jpg",
        "page": "https://guamlegislature.gov/about-tmt/",
        "words": "alt text \"Senator Therese M. Terlaje\", under the page's heading \"About "
                 "– Senator Therese M. Terlaje\", followed by \"5th Guam Legislative Term "
                 "Legislative Years of Service 34th – 38th (2017 – present) Village "
                 "Party Democrat\"; page title \"About – Senator Therese M. Terlaje » Guam "
                 "Legislature\"",
        "by": "Guam Legislature",
        "tie": "Route 1(d). The article the race's own article links for her ('Therese "
               "Terlaje', recorded in statewide_photos.json articles for "
               "GU|governor|TERLAJE, Therese Maria) says in its own words: \"Terlaje "
               "has served as a member of the Legislature of Guam since 2017 ... "
               "having served in the 35th (2019–2021), 36th (2021–2023), 37th "
               "(2023–2025), and 38th (2025-present) sessions of the legislature. "
               "Terlaje is running for Governor of Guam.\" and links this very page "
               "(https://guamlegislature.gov/about-tmt/). The Guam Legislature's own "
               "page for her names \"Senator Therese M. Terlaje\" beside the photograph, "
               "\"34th – 38th (2017 – present)\". The file is named for her initials "
               "(TMT), not a seat. Offered in the 768w rendition the page's srcset "
               "lists (64 KB, 768x960), within the caps.",
        "seen": "A studio portrait of one woman alone: long dark wavy hair, smiling, "
                "black wrap jacket with a pin, orange bead necklace, plain mottled "
                "brown-grey backdrop; nobody else in the frame, no words or graphics. "
                "The same woman as the Commons files of her (2018 and 2024). A second "
                "reader looked again and measured: brow at about band 2.6, chin at "
                "about band 4.4 on the card: about 1.8 tenths (one band = 96 source px)",
        "read": "2026-11-17",
    },
    # Vicente A. Ada
    "GU|governor|ADA, Vicente A.": {
        "url": "https://guamlegislature.gov/wp-content/uploads/2025/02/VAA-768x960.jpg",
        "page": "https://guamlegislature.gov/about-vaa/",
        "words": "alt text \"Vice Speaker V. Anthony Ada\", under the page's heading "
                 "\"About – Vice Speaker V. Anthony Ada\", followed by \"6th Guam "
                 "Legislative Term Legislative Years of Service 30th – 33rd (2009 – "
                 "2016) 36th (2021 – 2022) 38th (2025 – present)\"; page title \"About – "
                 "Vice Speaker V. Anthony Ada » Guam Legislature\"",
        "by": "Guam Legislature",
        "tie": "Route 1(d). The article the race's own article links for him ('Vicente "
               "Ada', recorded in statewide_photos.json articles for GU|governor|ADA, "
               "Vicente A.) says in its own words: \"Vicente Anthony \\\"Tony\\\" Ada ... A "
               "member of the Republican Party, he has served in the Guam Legislature "
               "from 2009 to 2017, from 2021 to 2023 and since 2025.\" and links this "
               "very page (https://guamlegislature.gov/about-vaa/). The Guam "
               "Legislature's own page names \"Vice Speaker V. Anthony Ada\" beside the "
               "photograph, \"38th (2025 – present)\", and its biography \"Vicente "
               "Anthony Ada, or 'Tony' as he is known\". The file is named for his "
               "initials (VAA), not a seat. Offered in the 768w rendition the page's "
               "srcset lists (58 KB, 768x960), within the caps. (His article also "
               "calls him governor-elect; the legislature page is the office he holds "
               "now.)",
        "seen": "A studio portrait of one man alone: short dark hair, smiling, dark "
                "suit, white shirt, red tie, plain mottled grey-brown backdrop; nobody "
                "else in the frame, no words or graphics. The same man as the Commons "
                "crops of him (Joint Region Marianas, 2025 and 2026). A second reader "
                "looked again and measured: brow at about band 2.8, chin at about band "
                "5.0 on the card: about 2.2 tenths (one band = 96 source px)",
        "read": "2026-11-17",
    },
    # Darren Bailey
    "IL|governor|Darren Bailey": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/d0/Darren_Bailey_at_a_2"
               "022_Campaign_Event.jpg",
        "page": "https://commons.wikimedia.org/wiki/File:Darren_Bailey_at_a_2022_Campaign"
                "_Event.jpg",
        "words": "File:Darren Bailey at a 2022 Campaign Event.jpg, described \"Republican "
                 "nominee for Illinois Governor Darren Bailey at a campaign event, "
                 "2022.\"; in Category:Darren Bailey; the Wikidata item's image (P18)",
        "tie": "the article 'Darren Bailey', which the race's own article (2026 "
               "Illinois gubernatorial election) links for him (statewide_photos.json "
               "articles); its item Q59781882 names this file as its image (P18) and "
               "its Commons sitelink is Category:Darren Bailey, which holds the file. "
               "Author Cobiblair is the uploader, own work, CC BY-SA 4.0: no licence "
               "doubt (the two crops of it, uploaded by others, are doubts and not "
               "offered)",
        "seen": "him alone, smiling, glasses, checked shirt, before a brick wall and a "
                "white railing; nobody else anywhere in the frame (a grey box and a "
                "shrub at the right edge). The automatic route refused the article's "
                "lead (a crop of this file) for the words 'Campaign Event' in its name; "
                "the photograph itself is no scene A second reader looked again and "
                "measured: My own count on the card: brow at about band 3.6 (source y "
                "~165), chin at about band 6.5 (source y ~345): about 180 source px at "
                "62.5 px a band, about 2.9 tenths of the card; the card keeps x 0-500, "
                "y 0-625, only the lower shirt cut",
        "read": "2026-11-17",
    },
    # Aaron D. Ford
    "NV|governor|Ford, Aaron D.": {
        "url": "https://ag.nv.gov/uploadedImages/agnvgov/Content/About/20210324_AGPic.jp"
               "g",
        "page": "https://ag.nv.gov/About/AG_Aaron_Ford/",
        "words": "under the heading \"Nevada Attorney General Aaron Ford\", the image's "
                 "alt text \"Attorney General Aaron Ford\", followed by \"Attorney General "
                 "Aaron D. Ford, Nevada's 34th Attorney General, took office on January "
                 "7, 2019\"",
        "by": "Office of the Nevada Attorney General",
        "tie": "route 1(d): the article his race's own article links for him (Aaron "
               "Ford, via 2026 Nevada gubernatorial election; statewide_photos.json "
               "articles) says \"A member of the Democratic Party, Ford has served "
               "since 2019 as the 34th attorney general of Nevada\" (its infobox: \"34th "
               "Attorney General of Nevada Incumbent Assumed office January 7, 2019\"); "
               "this is that office's own page for its holder. This site's Nevada "
               "attorney general card (statewide_officers.json ag/NV, confirmed "
               "2026-11-16) already shows this very file from this page (39,455 bytes, "
               "480x480)",
        "seen": "a studio-lit office portrait, him alone, seated, smiling, dark suit "
                "and blue tie, a window and wooden shutters behind; nobody else in the "
                "frame A second reader looked again and measured: My own count on the "
                "card: brow at about band 3.0 (source y ~135), chin at about band 5.3 "
                "(source y ~245): about 110 source px at 48 px a band, about 2.3 tenths "
                "of the card; the card keeps x 48-432, y 0-480: head and shoulders "
                "whole",
        "read": "2026-11-17",
    },
    # Helena Buonanno Foulkes
    "RI|governor|HELENA BUONANNO FOULKES": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/0/0f/HelenaFoulkes_CROP.j"
               "pg",
        "page": "https://commons.wikimedia.org/wiki/File:HelenaFoulkes_CROP.jpg",
        "words": "the file's description \"Helena Foulkes, EVP CVS Caremark & President "
                 "CVS/Pharmacy\", its name \"HelenaFoulkes CROP.jpg\"; the lead image of "
                 "the article 'Helena Foulkes' and the image (P18) of its item "
                 "Q21067177, filed in Category:Helena Foulkes",
        "tie": "route 1(c): the race's own article '2026 Rhode Island gubernatorial "
               "election' links [[Helena Foulkes]] for the Rhode Island Department of "
               "State's 'Helena Buonanno Foulkes' (statewide_photos.json articles); "
               "that article leads with this file, which is in the person's own "
               "Commons category. The automatic reader passed it over as 'file-name' "
               "only because the surname is run together in 'HelenaFoulkes'; no "
               "person's list refuses it. Licence: Flickr import from the Digitas "
               "account (author Digitas Photos), CC BY 2.0, extracted from "
               "File:HelenaFoulkes.jpg; not an own-work claim, and the helper's "
               "licence test raised no doubt",
        "seen": "a 2014 conference photograph: she alone, seated, speaking, headset "
                "microphone at her cheek, blue jacket, white top, hands raised before "
                "her chest; behind her only a red and teal geometric stage backdrop and "
                "the edge of a clear acrylic chair. I also looked at the uncropped "
                "original (File:HelenaFoulkes.jpg): nobody else anywhere in the frame. "
                "Not a studio portrait, but a likeness of her alone, face unobscured A "
                "second reader looked again and measured: on the 960x1225 rendition the "
                "card keeps y 0-1200 (one band = 120 px): brow near y 185, chin near y "
                "440, about 2.1 tenths; on the helper's 500px card brow near band 1.8, "
                "chin near band 3.3, about 1.5-2 tenths: above a tenth",
        "read": "2026-11-17",
    },
    # Jermaine Johnson
    "SC|governor|Jermaine Johnson": {
        "url": "https://www.scstatehouse.gov/images/members/0943181705.jpg",
        "page": "https://www.scstatehouse.gov/member?code=0943181705",
        "words": "under the heading \"Representative Jermaine L. Johnson, Sr.\" (directly "
                 "above it), the image's alt text \"Representative Jermaine L. Johnson, "
                 "Sr. photo\", the words after it \"Democrat - Richland District 52 - "
                 "Kershaw & Richland Counties\"; the page's personal information \"Born "
                 "July 4, 1985\"; the file is keyed by the member's own code 0943181705 "
                 "(the page's ?code=), not by a seat",
        "by": "South Carolina General Assembly",
        "tie": "route 1(d): the article the race's own article '2026 South Carolina "
               "gubernatorial election' links for the list's 'Jermaine Johnson' "
               "('Jermaine Johnson (politician)', statewide_photos.json articles) says "
               "\"A member of the Democratic Party, he is a member for South Carolina "
               "House of Representatives, representing the 52nd district\" and its "
               "infobox \"Member of the South Carolina House of Representatives "
               "Incumbent ... 52nd district (2024–present)\", born \"July 4, 1985\"; the "
               "South Carolina Legislature's own member page for District 52 names "
               "\"Representative Jermaine L. Johnson, Sr.\" beside this image and gives "
               "the same birth date, July 4, 1985 (a second tie beyond the name). This "
               "site's own legislature roster (data/legislature/sc.js) already shows "
               "this very file on his card, credited to the South Carolina General "
               "Assembly. NOTE for the reviewer: the article says he did not run for "
               "re-election to the House in 2026 and its infobox already names a "
               "successor ('Succeeded by Malcolm Taylor'); the Legislature's page "
               "still names him for District 52 today, 2026-11-17",
        "seen": "an official studio portrait: he alone, head and shoulders, smiling, in "
                "a navy suit, white shirt and floral tie, a round pin on the lapel, "
                "before a plain grey backdrop; nobody else in the frame. The file is "
                "small (125x175) and soft but plainly a face A second reader looked "
                "again and measured: on the helper's card (one band = 15.6 source px) "
                "brow near band 2.5, chin near band 6.4: about 3.9 tenths",
        "read": "2026-11-17",
    },
    # Gina Hinojosa
    "TX|governor|GINA HINOJOSA": {
        "url": "https://house.texas.gov/images/members/3210.jpg?v=1",
        "page": "https://house.texas.gov/members/49",
        "words": "alt \"Representative Hinojosa, Gina\" on the member page headed \"Rep. "
                 "Hinojosa, Gina - District 49\" (title \"Official Home Page of the Texas "
                 "House of Representatives Website for Rep. Hinojosa, Gina.\"); file "
                 "3210.jpg is her member id, the same id as the article's State House "
                 "link house.texas.gov/members/3210",
        "by": "Texas House of Representatives",
        "tie": "Route 1(d). The article her race's own article links for her "
               "(statewide_photos.json articles: 'Gina Hinojosa', from '2026 Texas "
               "gubernatorial election', read 2026-11-03) says in its own words that "
               "she holds the seat now: \"she has represented the 49th district in the "
               "Texas House of Representatives since 2017\", infobox \"Member of the "
               "Texas House of Representatives from the 49th district Incumbent "
               "Assumed office January 10, 2017\", and links "
               "\"house.texas.gov/members/3210\" as her State House website. The Texas "
               "House's own member page for District 49 names her beside the "
               "photograph; the file is keyed by her member id 3210, not by the seat.",
        "seen": "An official studio head-and-shoulders portrait of Gina Hinojosa alone "
                "on a grey backdrop: dark jacket, striped collar, smiling at the "
                "camera. Nobody else in the frame, no words, no graphic. Small file "
                "(125x175) but sharp enough for the card. A second reader looked again "
                "and measured: On the card: brow (eyebrows) at about band 4.0, chin at "
                "about band 6.7: about 2.7 tenths of the card's height (one band = 15.6 "
                "source px; the face spans roughly 42 source px), well over the tenth "
                "required. (The first reader wrote 3.7 to 7.4; my reading of the ruler "
                "puts the brow and chin higher, but either way it passes.)",
        "read": "2026-11-17",
    },
    # Eric Barlow
    "WY|governor|Eric Barlow": {
        "url": "https://wyoleg.gov/LegislatorSummary/Photos/68th-BarlowEric.jpg",
        "page": "https://www.wyoleg.gov/Legislators/2025/S/1995",
        "words": "The Wyoming Legislature's own record for this member page (legID 1995, "
                 "read from https://api.wyoleg.gov/v1/Legislator/1995, the address the "
                 "page's own script reads): \"name\":\"Senator Eric Barlow\", "
                 "\"district\":\"Senate District 23\", \"senateYears\":\"Senate: 2023-Present\", "
                 "\"legPhoto\":\"68th-BarlowEric.jpg\"; the page draws the file as <img "
                 "src=\"https://wyoleg.gov/LegislatorSummary/Photos/\" + legPhoto "
                 "alt=\"Photograph of \" + name>, i.e. alt \"Photograph of Senator Eric "
                 "Barlow\". File name: 68th-BarlowEric.jpg.",
        "by": "Wyoming Legislature",
        "tie": "Route 1(d). The race's own article links 'Eric Barlow' "
               "(statewide_photos.json articles: race page '2026 Wyoming gubernatorial "
               "election', read 2026-11-03); that article says in its own words "
               "\"Member of the Wyoming Senate from the 23rd district Incumbent\" (and "
               "\"Governor-elect of Wyoming Assuming office January 4, 2027\"). The "
               "Wyoming Legislature's member record legID 1995 names him \"Senator Eric "
               "Barlow\", Senate District 23, \"Senate: 2023-Present\", with legPhoto "
               "68th-BarlowEric.jpg; the Wyoming Secretary of State's 2026 general "
               "election candidate list prints \"Republican Eric Barlow\" in its "
               "GOVERNOR row. This site's own legislature page already shows this file on "
               "his Senate District 23 card, credited to the Wyoming Legislature. The "
               "file is keyed by name, not by seat.",
        "seen": "A studio head-and-shoulders portrait of one man alone (grey beard, "
                "dark suit, red paisley tie) on a mottled grey backdrop; nobody else in "
                "the frame or at its edges, no text over him. The card keeps him "
                "whole-faced; the circle crop too. A second reader looked again and "
                "measured: face brow to chin: brow at about band 2.7, chin (beard line "
                "under the lip/jaw) at about band 5.5 of the card: about 2.8 tenths of "
                "the card (one band = 26.8 source px)",
        "read": "2026-11-17",
    },
}

# Campaign-site photographs taken by the narrow first-name route (the
# owner's decision of 2026-11-01, rule 38): the candidate's own campaign site,
# an image whose file name or alt text carries their first name and a
# likeness word ("headshot", "portrait", "profile") together
# (enrich.first_name_portraits). A first name is a weaker tie than a surname
# - a campaign pictures the candidate's family under first names - so each is
# withheld, and named by validate (portrait-first-name-unseen), until a
# person has looked at the file and recorded it here, keyed on the file the
# page draws (the original, where a lighter rendition is shown): (the day,
# what was seen - the candidate alone, nobody else in the frame, a face on a
# screen included, and the face, brow to chin, as a share of the 4:5 card
# that crops it from the top, as rule 38 measures it - the page it was on,
# and the bytes and pixel size of the file the card shows, as the cache's
# portraitWeight gives them). The size ties the look to the picture, not
# the address (the PR #186 review): a campaign that saves another
# photograph over the same file name, or a host that re-encodes it, sends it
# back behind the gate until a person looks again. One that fails the look
# goes in NOT_A_PORTRAIT instead. validate reports an entry no cached
# campaign record offers any more (stale-first-name-portrait), and fails a
# first-name portrait shown without one (photo-unevidenced).
SEEN_FIRST_NAME_PORTRAITS = {
    "https://bgp.stoke.dev/wp-content/uploads/2026/07/bernadette-headshot-about.png":
        ("2026-11-01", "Bernadette Greene-Placentia (AZ-8) alone, arms folded, before a "
                       "blurred shopfront and a tree, nobody else in the frame; 800x835, her "
                       "face about a seventh of the card's height (about 80 of the 500x521 "
                       "rendition's 521px, re-measured for the PR #186 review)",
         "https://bgp4az.com/about/", {"bytes": 239772, "width": 500, "height": 521}),
    "https://alexcookeforcongress.com/images/alexander-headshot.jpg":
        ("2026-11-01", "Alexander Cooke (FL-21) alone in a suit before a blurred marina, nobody "
                       "else in the frame; 1600x1541, his face about a fifth of the card's "
                       "height (about 95 of the 500x481 rendition's 481px, re-measured for the "
                       "PR #186 review)", "https://www.alexcookeforcongress.com/",
         {"bytes": 15510, "width": 500, "height": 481}),
    "https://static.wixstatic.com/media/0ca2e0_eedd6ff3cd6d4b2b84bf8f9023b8b0fb~mv2.jpg/v1/fill/"
    "w_269,h_307,al_c,q_80,usm_0.66_1.00_0.01,enc_avif,quality_auto/America%20Colby%20Profile.jpg":
        ("2026-11-01", "Colby Watson (NC-8) alone in a suit before a flag, nobody else in the "
                       "frame; 269x307, his face nearly a quarter of the card's height "
                       "(about 70 of 307px, re-measured for the PR #186 review)",
         "https://www.colbyforcongress.com/about", {"bytes": 10582, "width": 269, "height": 307}),
    "https://images.squarespace-cdn.com/content/v1/686220fecacd134503b4365c/"
    "ad1c74a1-fae7-4c06-8247-688e088d63f4/HEADSHOT_BRINKER_NOBG_2_Compressed.png":
        ("2026-11-01", "Brinker Harding (NE-2) alone, cut out on a transparent background, "
                       "nobody else in the frame; 1705x1911, his face about a fifth of the "
                       "card's height (about 120 of the 500x560 rendition's 560px, re-measured "
                       "for the PR #186 review)", "https://www.brinkerharding.com",
         {"bytes": 219876, "width": 500, "height": 560}),
    "https://electteresa.com/wp-content/uploads/2026/03/Teresa-headshot-square-new.jpg":
        ("2026-11-01", "Teresa Benitez-Thompson (NV-2) alone before mountains, nobody else in "
                       "the frame; 1317x1316, her face a quarter of the card's height (330 of "
                       "1316px; about 125 of the 480x480 rendition's 480px)",
         "https://electteresa.com/", {"bytes": 29496, "width": 480, "height": 480}),
    "https://static.wixstatic.com/media/2ce4e2_6c687650676f42f9928870c3695e5b68~mv2.png/v1/crop/"
    "x_0,y_2,w_972,h_885/fill/w_493,h_449,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/"
    "Jerrad-Headshot2.png":
        ("2026-11-01", "Jerrad Shane Christian (OH-12) alone, arms folded, on a white "
                       "background, nobody else in the frame (nor in the uncropped 972x1264 "
                       "original); 493x449, his face nearly a third of the card's height "
                       "(about 135 of 449px, re-measured for the PR #186 review)",
         "https://www.christianforohio.com/", {"bytes": 109282, "width": 493, "height": 449}),
}

# Commons files a judge's route (kyc/judge_links.py) or a statewide
# candidate's (kyc/statewide_photos.py) reaches whose licence is in doubt,
# keyed on the upload URL: (date, what the file's page says).
# Each is withheld - and reported - until a person reads the file's page and
# decides; delete the entry to show it, or move it to NOT_A_PORTRAIT to
# refuse it for good.
#
# One test, applied to every portrait alike: Commons' licence tag stands
# unless the file's page or its name points to an author who is neither its
# uploader nor a government office - a studio's code, a university's credit,
# a private site's photograph guessed to be official - or the page names no
# author at all. A
# court's own photograph tagged PD-USGov-Judiciary (or PD-USGov, author the
# court) stands, as it does for the 491 court-credited portraits shown on
# 2026-10-19, and so does an uploader's {{own}} work with nothing on its page
# that says otherwise. The review of PR #127 found the first list doubting
# two D.C. court photographs (Mehta, Sooknanan), two {{own}} uploads
# (Arias-Marxuach, Carreno-Coll), a Southern District of Florida photograph
# (Marra, author the court, "work of the Federal Government") and the
# Supreme Court photographer's portrait of Justice Jackson
# ({{PD-USGov-SCOTUS}}) on grounds that every shown portrait of their kind
# would fail; those were dropped (read 2026-10-19).
PORTRAIT_LICENCE_DOUBTS = {
    "https://upload.wikimedia.org/wikipedia/commons/f/fc/Richard_C._Wesley_(cropped).jpg":
        ("2026-10-19", "CC BY-SA 4.0 on a photograph credited 'Photo courtesy of the "
                       "University of Albany', with no permission recorded"),
    "https://upload.wikimedia.org/wikipedia/commons/6/6b/Higginbotham_Patrick_E.jpg":
        ("2026-10-19", "public domain on the uploader's reasoning that 'it must be his official "
                       "portrait'; taken from innsofcourt.org"),
    "https://upload.wikimedia.org/wikipedia/commons/7/7d/Rufe,_Hon_CynthiaVLF22561r_web2.jpg":
        ("2026-10-19", "'own work' by an uploader, of a file carrying a studio's code "
                       "(VLF22561r)"),
    "https://upload.wikimedia.org/wikipedia/commons/6/62/Header_NA_Yoon_US-Senate-Collection.jpg":
        ("2026-10-19", "public domain, from the Senate Press Gallery, author {{Unknown}}"),
    # Statewide candidates' (PR #135's review, 2026-10-25). The test above
    # finds Jolly's (no author) and Kobach's ("official portrait" under a
    # user's CC0) by itself (statewide_photos.licence_doubt); these three a
    # person must read.
    "https://upload.wikimedia.org/wikipedia/commons/8/89/Allen_Headshot_-_Pikes_Peak_background_(cropped).jpg":
        ("2026-10-25", "CC0 by the user account 'Koncurrentkat' on a studio-style headshot "
                       "against a backdrop ('Pikes Peak background'), with nothing on the page "
                       "showing the uploader took it"),
    "https://upload.wikimedia.org/wikipedia/commons/2/27/Ra%C3%BAl_Torrez_(cropped_2).jpg":
        ("2026-10-25", "CC0 by the user account 'LandofEnchantment Pics', with nothing on the "
                       "page showing the account took the photograph"),
    "https://upload.wikimedia.org/wikipedia/commons/9/94/Paul_Pate_(cropped).jpeg":
        ("2026-10-25", "'Copyrighted free use', author 'Iowa General Assembly', with no "
                       "permission or statute recorded behind the tag"),
}

# Each sitting justice's official portrait as Wikimedia Commons holds it,
# keyed on the FJC nid: (the Commons file, its author as the file's page
# names it, the day read, what shows it is the Court's own). The owner's
# decision of 2026-10-20: the Court's photographs page says its images "may
# not be reproduced for publication (print or web) without prior approval";
# the official portraits are its staff photographers' work, and Commons holds
# them, so a justice's portrait is taken from Commons, credited to its
# photographer, wherever this table names it. Commons holds the Court's
# official portraits, not always the ones it shows now: by each file's date,
# Roberts's is of 2005, Alito's 2006, Thomas's 2007, Sotomayor's 2009 (the
# Court's biographies page shows one of 2025), Kagan's 2010, Gorsuch's 2017,
# Kavanaugh's 2018, Barrett's 2021, Jackson's 2022 (read 2026-10-25; whether
# a newer public-domain copy should replace one is the owner's call). The
# judges' read (kyc/judge_links.py) takes this file for the justice, by the
# same checks as any judge's, and the federal pages show it only while
# Commons still names the author recorded here; otherwise the Court's own
# portrait stands, and the page says the read did not confirm the file.
# Sonia Sotomayor's Wikidata item's image is a 2009 White House photograph,
# not the Court's portrait, and Elena Kagan's is a 2013 upload of hers tagged
# CC BY-SA 3.0: each entry below names the Court's own portrait as Commons
# holds it, in the public domain (both read 2026-10-25).
_SCOTUS_STAFF = ("the Court's official portrait, by its staff photographer, as the Court's "
                 "Collection credits it")
JUSTICE_PORTRAITS = {
    "1391841": ("Official roberts CJ.jpg", "Steve Petteway", "2026-10-20",
                _SCOTUS_STAFF + "; the Chief Justice's official portrait"),
    "1388686": ("Clarence Thomas official SCOTUS portrait.jpg",
                "Steve Petteway, Collection of the Supreme Court of the United States",
                "2026-10-20", _SCOTUS_STAFF),
    "1377101": ("Justice Alito official.jpg", "Steve Petteway", "2026-10-20", _SCOTUS_STAFF),
    "1388091": ("Sonia Sotomayor in SCOTUS robe.jpg",
                "Collection of the Supreme Court of the United States, Steve Petteway",
                "2026-10-25", _SCOTUS_STAFF + "; public domain, its source Oyez; the item's "
                "image is a 2009 White House photograph by Stacey Ilyse"),
    "1393281": ("Elena Kagan official SCOTUS portrait.jpg",
                "Steve Petteway, Collection of the Supreme Court of the United States",
                "2026-10-25", _SCOTUS_STAFF + "; public domain, its source Oyez; the item's "
                "image, 'Elena Kagan Official SCOTUS Portrait (2013).jpg', is tagged CC BY-SA 3.0"),
    "1392461": ("Associate Justice Neil Gorsuch Official Portrait.jpg",
                "Franz Jantzen, Collection of the Supreme Court of the United States",
                "2026-10-20", _SCOTUS_STAFF),
    "1392406": ("Associate Justice Brett Kavanaugh Official Portrait.jpg",
                "The Collection of the Supreme Court of the United States", "2026-10-20",
                "the Court's official portrait, credited to the Court's Collection"),
    "3979311": ("Amy Coney Barrett official portrait.jpg", "United States Supreme Court",
                "2026-10-20", "the Court's official portrait, credited to the Court"),
    "1394151": ("Ketanji Brown Jackson official SCOTUS portrait.jpg",
                "Fred Schilling / United States Supreme Court", "2026-10-20", _SCOTUS_STAFF),
}

# A member's official issues page whose list `members` reads but that is not
# the page's list of issues, keyed on bioguide id: (date checked, the page
# read, what it shows). The rules take a page's links or one level of its
# headings in its words; a page that splits each title across two headings
# passes them and reads as fragments. The page is linked instead ("On their
# official site's issues page"). The refresh re-reads every site, so a
# correction made by editing the cache would not last; members.problems
# reports an entry whose page is no longer the one read.
OFFICIAL_ISSUES_NOT_A_LIST = {
    "L000575": ("2026-10-18", "https://www.lankford.senate.gov/issues/",
                "each title is split over two headings: 'Protecting' over 'Life, Liberty & "
                "Our Families', 'Bringing Down' over 'High Costs in Our Nation'"),
    # Read 2026-10-18 for the review of PR #106: the index lists the House
    # template's stock categories, each twice, beside categories that are
    # labels for constituent mail rather than positions - "PRO CHOICE",
    # "Pro Life", "PRO AG", "REDUCE TROOPS IN MIDDLE EAST PRO" - and one page
    # under two names ("11 Ideals for TX-11", "TX-11 Ideals"). As a platform
    # it would read as though a member who lists "Pro Life" held both views.
    "P000048": ("2026-10-18", "https://pfluger.house.gov/issues/",
                "mail categories ('PRO CHOICE', 'Pro Life', 'REDUCE TROOPS IN MIDDLE EAST PRO') "
                "listed among the stock categories, each of those twice"),
}

# The 2026 Senate seats are no longer typed here. A surname table matched
# Darline Graham to Lindsey Graham's seat; the seats are now the frozen race
# record, keyed on bioguide ids (kyc/record.py, data/record_2026.json).

# Seats whose first round is a nonpartisan ("jungle") primary held on general
# election day, with a runoff after it. Keyed (state, office, cycle); laid over
# the FEC calendar by results.effective_dates, and validate warns whenever the
# FEC's own dates disagree, so the entry is re-examined rather than forgotten.
#
# Louisiana's party primaries for the U.S. House (May 16 / June 27) were
# postponed after Louisiana v. Callais and the state redrew its map; Act 7 of
# the 2026 Regular Session moved the House races to an open primary on
# November 3 with a runoff on December 12 (Louisiana Secretary of State release
# of 2026-07-08; Wikipedia, "2026 United States House of Representatives
# elections in Louisiana", revision 1377090557, re-read 2026-10-01). The FEC
# calendar's "primary 2026-08-07" is the close of qualifying. Louisiana's
# Senate race kept its closed party primaries and is not listed.
OPEN_PRIMARY_SEATS = {
    ("LA", "H", 2026): {
        "primary": "2026-11-03",
        "runoff": "2026-12-12",
        "source": "https://en.wikipedia.org/w/index.php?oldid=1377090557 "
                  "(Louisiana Secretary of State, 2026-07-08; Act 7, 2026 R.S.)",
    },
}

# Seats whose 2026 primary was not the state's (results.seat_dates), keyed on
# race id: {"primary", "runoff", "source"}. A per-state calendar cannot hold
# them, and the four Alabama seats read "Primary held 2026-05-19" for a
# primary held in August.
#
# Alabama: after the Supreme Court stayed the court-drawn map, Governor Ivey's
# special primary proclamation of 2026-05-12 postponed the primaries for the
# 1st, 2nd, 6th and 7th districts to a special primary on August 11, 2026,
# under the Legislature's 2023 plan, with no runoff; the winners go to the
# November 3 ballot (governor.alabama.gov newsroom, 2026-05-12; Alabama Public
# Radio, 2026-08-10; read 2026-10-17).
_AL_SPECIAL = {"primary": "2026-08-11", "runoff": None,
               "source": "https://governor.alabama.gov/newsroom/2026/05/governor-ivey-celebrates-"
                         "major-court-victory-in-states-redistricting-battle-calls-special-"
                         "election-for-alabama-drawn-congressional-map/ (special primary "
                         "proclamation of 2026-05-12; read 2026-10-17)"}
SEAT_PRIMARY_DATES = {
    "H-AL-01-2026": _AL_SPECIAL,
    "H-AL-02-2026": _AL_SPECIAL,
    "H-AL-06-2026": _AL_SPECIAL,
    "H-AL-07-2026": _AL_SPECIAL,
}

# House seats left empty during the 119th Congress with no special election
# to fill them, keyed (state, district): who left, the day their term ended
# as congress-legislators' legislators-historical records it (the bioguide id
# is the key into it), how, and whether a special election has been called,
# each with the day it was checked. Shown on the delegation and the district
# map (RACES-05, FRESHNESS-12) while nobody sits there. validate reports an
# entry for a seat someone now sits in, and one whose member the snapshot
# still seats; it cannot check `left`, which the build has no offline record
# of (neither member is in Former_Members.csv), so check it by hand against
# legislators-historical when adding an entry. Re-check `special` before
# moving `checked`.
SEAT_VACANCIES = {
    ("FL", 20): {
        "bioguide": "C001127", "name": "Sheila Cherfilus-McCormick", "left": "2026-04-21",
        "how": "resigned", "special": "no special election called", "checked": "2026-10-17",
        "source": "legislators-historical (term end 2026-04-21); House Press Gallery, party "
                  "breakdown: resigned 04/21/26; Wikipedia, 119th United States Congress: no "
                  "special election before the 2026 elections; read 2026-10-17",
    },
    ("TX", 23): {
        "bioguide": "G000594", "name": "Tony Gonzales", "left": "2026-04-14",
        "how": "resigned", "special": "no special election called", "checked": "2026-10-17",
        "source": "legislators-historical (term end 2026-04-14); House Press Gallery, party "
                  "breakdown: resigned 04/14/2026; Texas Tribune: the governor has called no "
                  "special election; read 2026-10-17",
    },
}

# Certified November ballots published only as a PDF, which the standard
# library cannot read (kyc/certified.py reads the HTML ones), transcribed from
# the document named, printed names only: name and party as the list gives
# them, in its order. ``complete`` says the list is the whole ballot for its
# races, so that a filer it does not name is not on the ballot (rule 77); a
# list that is not (a party's own list of its nominees) only adds names.
# Re-read the document before the election and move ``read``.
CERTIFIED_BALLOTS = {
    "IA": {
        "source": "Iowa Secretary of State, Candidate List, November 3, 2026 General Election "
                  "(last updated 8/14/2026)",
        "url": "https://sos.iowa.gov/sites/default/files/2026-08/2026%20General%20-%20Candidate"
               "%20List%20Database%20-%20All%20Elections_0.pdf",
        "read": "2026-10-17", "complete": True,
        "races": {
            "S-IA-2026": [("Ashley Hinson", "Republican"), ("Josh Turek", "Democratic"),
                          ("Thomas Laehn", "Libertarian")],
            "H-IA-01-2026": [("Mariannette Miller-Meeks", "Republican"),
                             ("Christina Bohannan", "Democratic"),
                             ("Michael Bridgford", "No Party")],
            # Rick Stewart: kept on the ballot by the State Objections Panel
            # on June 15 (KCRG); the Cerro Gordo County list revised 9/3/2026
            # prints the same four.
            "H-IA-02-2026": [("Joe Mitchell", "Republican"), ("Lindsay James", "Democratic"),
                             ("Rick Stewart", "Libertarian"), ("Dave Bushaw", "No Party")],
            "H-IA-03-2026": [("Zach Nunn", "Republican"), ("Sarah Trone Garriott", "Democratic")],
            "H-IA-04-2026": [("Chris McGowan", "Republican"), ("Dave Dawson", "Democratic")],
        },
    },
    "NE": {
        "source": "Nebraska Secretary of State, Final Statewide General Candidate List, "
                  "November 3, 2026 General Election (9/11/2026)",
        "url": "https://sos.nebraska.gov/sites/default/files/doc/elections/2026/"
               "Final_Statewide_General_Candidate_Filing_List_9.11.26.pdf",
        "read": "2026-10-17", "complete": True,
        "races": {
            # Mike Marvin suspended his campaign on August 21 and stays on
            # the ballot (Nebraska Examiner via WOWT, 2026-09-02); the
            # certified list prints him.
            "S-NE-2026": [("Pete Ricketts", "Republican"), ("Mike Marvin", "Legal Marijuana NOW"),
                          ("Robin Richards", "Nebraska Working People"),
                          ("Chuck Conboy", "America First"), ("Dan Osborn", "By Petition")],
            "H-NE-01-2026": [("Mike Flood", "Republican"), ("Chris Backemeyer", "Democratic"),
                             ("Nik Sandman", "Libertarian"), ("Dan Hartong", "America First")],
            "H-NE-02-2026": [("Brinker Harding", "Republican"), ("Denise Powell", "Democratic"),
                             ("Eric Michael Foreman", "Libertarian")],
            "H-NE-03-2026": [("Adrian Smith", "Republican"), ("Becky Kelly Stille", "Democratic"),
                             ("David J. Else", "Legal Marijuana NOW"),
                             ("Macey Budke", "Nebraska Working People"),
                             ("Mark Cohen", "By Petition")],
        },
    },
}

# States whose federal general election goes to a runoff when no candidate wins
# a majority, and when (state code: (date, evidence)). After Election Day the
# results reader treats an unpartisan "Runoff results" table on these states'
# pages as that runoff (results.resolve_race). Louisiana's House seats are an
# open primary with its own December round (OPEN_PRIMARY_SEATS).
GENERAL_RUNOFFS = {
    "GA": ("2026-12-01", "O.C.G.A. 21-2-501(a): a runoff is held on the 28th day after a "
                         "general election in which no candidate receives a majority; "
                         "November 3 + 28 days = December 1, 2026"),
    # The Delegates from Guam and the Virgin Islands are elected by a
    # majority too (results night, 2026-11-04: read by plurality, a page
    # marking a leader short of one would have been "elected" a fortnight
    # before the runoff). The dates are data/voting_dates.json's.
    "GU": ("2026-11-17", "48 U.S.C. 1712: \"The Delegate from Guam shall be elected at large "
                         "and by a majority of the votes cast for the office of Delegate. If "
                         "no candidate receives such majority, on the fourteenth day following "
                         "such election a runoff election shall be held\"; November 3 + 14 "
                         "days = November 17, 2026"),
    "VI": ("2026-11-17", "48 U.S.C. 1712 elects the Delegate from the Virgin Islands by a "
                         "majority, with a runoff between the top two on the fourteenth day "
                         "after the election; the Elections System of the Virgin Islands' "
                         "2026 Elections Calendar (amended June 10, 2026) lists November 17 "
                         "as \"RUN-OFF ELECTION DAY (Revised Organic Act of 1954, Sec., 11 re: "
                         "Gov.-Lt. Gov.; P.L. 92-271 re: Delegate to House of "
                         "Representatives)\""),
}

# Seats whose November election is their only round: no primary, so the
# results reader's gate (results.primary_settled) has no date to open them
# on, and on results night (2026-11-04) neither page was read - American
# Samoa's five certified candidates and the Northern Mariana Islands' two
# would have read "Awaiting result" for good. The seat's page is read from
# the day after Election Day, its November table alone deciding.
# {(state, office): evidence}
NO_PRIMARY_SEATS = {
    ("AS", "H"): "American Samoa holds no primary for Delegate: its Election Office's certified "
                 "list for November 3, 2026 is the ballot, and the Delegate is elected by "
                 "plurality (48 U.S.C. 1732); the FEC's 2026 calendar lists no primary",
    ("MP", "H"): "the FEC's 2026 calendar lists no primary for the Northern Mariana Islands' "
                 "Delegate, and the seat's Wikipedia page holds only the November election's "
                 "table (read 2026-11-04); a runoff there is for governor and attorney general "
                 "alone (1 CMC 6509, as data/voting_dates.json records it)",
}

# Incorporated places the Census Bureau's 2022 Government Units listing files
# under a name the city join (counties.match_cities) cannot tie to the place,
# each joined here on the listing's own government id - never on a name
# (rule 59). {place GEOID: (listing id, the listing's name, evidence)}. The
# build refuses an entry whose id holds another name, lies in another county
# than the place, or is joined elsewhere, and reports one the join no longer
# needs. Checked 2026-10-16: in each case the place's county holds no other
# government the place could be. Never a government the place replaced:
# Rib Mountain and Lisbon, Wisconsin, and Baldwin and Empire, Minnesota,
# incorporated from the towns and townships the 2022 listing holds (rule 59).
PLACE_GOVERNMENTS = {
    "0934460": ("07200620100000", "Borough of Groton Long Point Association",
                "the Census maps the borough as Groton Long Point; its government is the "
                "Groton Long Point Association, the only one under that name in the region"),
    "1234132": ("10204430100000", "Village of Islamorada",
                "the Census maps it as Islamorada, Village of Islands, the village's full name"),
    "1326156": ("11105005000000", "County of Echols",
                "Echols County and Statenville are one consolidated government, which the "
                "Census maps as a place and lists as Echols County's county government"),
    "1939675": ("16204000300000", "City of Jewell",
                "the Census maps the city as Jewell Junction; the listing as Jewell, in the "
                "same county, Hamilton"),
    "2904248": ("26209500500000", "Village of Bellerive",
                "the Census maps it as Bellerive Acres, the listing as Bellerive, both in "
                "St. Louis County"),
    "2925411": ("26205730100000", "Village of Fountain-N-Lake",
                "the same name, spelled Fountain N' Lakes on the Census map"),
    "2964478": ("26209507500000", "City of St Johns",
                "the listing's St Johns, in St. Louis County, is the Census map's St. John"),
    "2975814": ("26209508600000", "Village of Velda Hills",
                "the Census maps it as Velda Village Hills, the listing as Velda Hills, both "
                "in St. Louis County"),
    "3709530": ("34201440100000", "Town of Cajah Mountain",
                "the same name, spelled Cajah's Mountain on the Census map"),
    "4030900": ("37204970100000", "Town of Grand Lake",
                "the Census maps the town as Grand Lake Towne; the listing as Grand Lake, in "
                "the same county, Mayes"),
    "4811155": ("44215220100000", "Village of Buffalo Springs",
                "the Census maps the village as Buffalo Springs Lake; the listing as Buffalo "
                "Springs, in the same county, Lubbock"),
    "5526350": ("50206500500000", "Village of Fontana",
                "the Census maps the village by its full name, Fontana-on-Geneva Lake"),
    "5624750": ("51200400500000", "Town of Grand Encampment",
                "the Census maps the town as Encampment; its legal name is Grand Encampment"),
    # Governments the listing files as towns or townships on a county
    # subdivision code the Census has since replaced: the 2025 map draws each
    # as an incorporated place with a subdivision of the same name and land,
    # coextensive with it (functional status F), on a new code - Mount
    # Lebanon 51696 -> 51794, Penn Hills 59032 -> 59040, Bridgewater 08085 ->
    # 08130, Randolph 55955 -> 56000. The same government, reclassified, not
    # a new one that replaced it.
    "4251794": ("39300202300000", "Township of Mount Lebanon",
                "the Census now maps the township as the municipality of Mount Lebanon"),
    "4259040": ("39300202900000", "Township of Penn Hills",
                "the Census now maps the township as the municipality of Penn Hills"),
    "2508130": ("22301200200000", "Town of Bridgewater",
                "the Census now maps the town, which has a city form of government, as "
                "Bridgewater Town city"),
    "2556000": ("22301102000000", "Town of Randolph",
                "the Census now maps the town, which has a city form of government, as "
                "Randolph Town city"),
}

# A committee seat's title as the body itself styles it, where the rosters
# give the minority's lead the majority's title. Keyed on the committee's
# code, the side and the rosters' own title, never on a person: (code,
# side, rosters' title) -> (title, evidence). congress-legislators titles
# both leads of the Senate Caucus on International Narcotics Control
# "Chairman", so the guide's committee table showed two chairmen of one
# panel and the minority's lead's profile read "(Chairman)". Checked
# 2026-10-17: the caucus's own site, drugcaucus.senate.gov, styles its
# majority lead "Chairman" and its minority lead "Co-Chair". validate
# warns on any other minority seat titled as a chair, and on an entry here
# that matches no seat.
COMMITTEE_TITLES = {
    ("SCNC", "minority", "Chairman"): (
        "Co-Chair", "drugcaucus.senate.gov, 2026-10-17: 'Chairman (R - TX)' and "
        "'Co-CHAIR (D - RI)' at the head of its home page"),
}

# A leadership post congress-legislators titles in words that read as
# something else, shown in the chamber's own words. "Senate Republican
# Committee Chair" sat beside Tim Scott's chair of the Banking Committee and
# read as the chair of a Senate committee; it is the party's campaign
# committee (the same title was Steve Daines's for 2023-24). Keyed on the
# record's title, never a person; validate warns once no one holds it.
LEADERSHIP_TITLES = {
    "Senate Republican Committee Chair": (
        "Republican Senatorial Committee Chair",
        "senate.gov/senators/leadership.htm, 2026-10-18: 'Republican Senatorial Committee "
        "Chair' Scott, Tim (R-SC), among the party leadership"),
}

# A justice's official portrait on their court's own page that the strict
# words test of kyc/court_photos.py refuses - an alt text that misspells
# them, a nickname, a file named by initials - looked at by a person, with
# the page's own words beside it and the day. Keyed (court, the name as the
# court's roster gives it); each is the record a read photograph carries
# (official_photos.record: the file, its page, the evidence, the day, its
# bytes and pixel size), with portraitHeavy where it is over the caps (rule
# 87: shown all the same and said).
# Not shown once the court no longer lists the justice, and the build says
# so.
def _justice_photo(photo, page, evidence, weight, read):
    return dict(zip(("bytes", "width", "height"), weight), photo=photo, page=page,
                evidence=evidence, read=read)


JUSTICE_PHOTOS = {
}

# State high courts whose own sites refuse every automated reader - a plain
# request and the headless Chrome of tools/read_court_pages.mjs alike (a
# Cloudflare or Akamai wall, a 403) - read once by hand, in an ordinary
# windowed Chrome, on the court's own page and nowhere else (rule 57). Each is
# (the court's page, the day it was read, the members in the court's order,
# the chief or "" when the page names none, what the page says, quoted).
# The build checks each against its seats and chief as it would a read
# roster, and warns once one is STALE_DAYS old (kyc/courts.py):
# read the page again, then move the date or change the names. The page
# says each was read by hand, and on which day.
COURT_ROSTERS = {
    "MO": ("https://www.courts.mo.gov/page.jsp?id=133", "2026-10-18",
           ("W. Brent Powell", "Zel M. Fischer", "Robin Ransom", "Paul C. Wilson",
            "Kelly C. Broniec", "Ginger K. Gooch", "Mary R. Russell"),
           "W. Brent Powell",
           "'The current Supreme Court of Missouri judges are:', then one per line: 'Chief "
           "Justice W. Brent Powell', 'Judge Zel M. Fischer', 'Judge Robin Ransom', 'Judge Paul "
           "C. Wilson', 'Judge Kelly C. Broniec', 'Judge Ginger K. Gooch', 'Judge Mary R. "
           "Russell'. A headless Chrome gets 'Error 403' and a notice that access 'by a site "
           "data scraper or any similar software' is prohibited."),
    "NH": ("https://www.courts.nh.gov/our-courts/supreme-court/about/justices", "2026-10-18",
           ("Patrick E. Donovan", "Melissa B. Countway", "Bryan K. Gould", "Daniel E. Will"),
           "",
           "One per line: 'Senior Associate Justice Patrick E. Donovan', 'Justice Melissa B. "
           "Countway', 'Justice Bryan K. Gould', 'Justice Daniel E. Will'. The page names no "
           "chief justice (a Senior Associate Justice is not one), and lists 'Senior Associate "
           "Justice Anna Barbara Hantz Marconi - February 12, 2026' and 'Senior Associate "
           "Justice James P. Bassett - August 31, 2025' under 'Recent retirements'. Akamai "
           "answers a headless Chrome 'Access Denied'."),
    "NV": ("https://nvcourts.gov/supreme/court_information/the_supreme_court_of_nevada_justices",
           "2026-10-18",
           ("Kristina Pickering", "Linda Marie Bell", "Ron D. Parraguirre", "Patricia Lee",
            "Elissa F. Cadish", "Douglas Herndon", "Lidia S. Stiglich"),
           "Douglas Herndon",
           "'Justice Kristina Pickering, Justice Linda Marie Bell, Justice Ron D. Parraguirre, "
           "Justice Patricia Lee, Justice Elissa F. Cadish, Chief Justice Douglas Herndon, "
           "Justice Lidia S. Stiglich', and the same seven under 'SUPREME COURT OF NEVADA "
           "JUSTICES'. Cloudflare answers a headless Chrome 'Just a moment...'."),
    "NY": ("https://www.nycourts.gov/ctapps/", "2026-10-18",
           ("Shirley Troutman", "Madeline Singas", "Jenny Rivera", "Rowan D. Wilson",
            "Michael J. Garcia", "Anthony Cannataro", "Caitlin J. Halligan"),
           "Rowan D. Wilson",
           "The menu 'JUDGES OF THE COURT': 'Hon. Shirley Troutman', 'Hon. Madeline Singas', "
           "'Hon. Jenny Rivera', 'Hon. Rowan D. Wilson', 'Hon. Michael J. Garcia', 'Hon. "
           "Anthony Cannataro', 'Hon. Caitlin J. Halligan'; the same page: 'On September 24, "
           "2026, Chief Judge Rowan D. Wilson conducted a statewide public hearing'. "
           "Cloudflare answers a headless Chrome 'Just a moment...'."),
}

# Statewide officers the office's own page names, read by hand in a person's
# browser (rule 57's way), where kyc/officers.py's own read concludes
# nothing (rule 8; each entry records what its reader saw) - or the
# association's roster does not speak for the office (NASS's "Currently Not a
# NASS Member", rule 55). Keyed (state, office), office "ag" or "sos"; each is
# (the holder the roster names, the office's own page, the day read, the
# page's words, each piece quoted as it stands: its title, then its text).
#
# An entry confirms only the very person the roster names, and only where
# officers.names_holder accepts one of its pieces - the full name beside the
# title, or the title before the surname (rule 56; NAME_FORMS for a short
# form). Once the roster names someone else it confirms nobody and validate
# says so (officers-by-hand); past officers.BY_HAND_STALE_DAYS the build
# warns that the page must be read again. Read on 2026-10-26
# (research/by-hand-2026-10-26/NOTES.md); nothing was got past a bot check.
OFFICERS_READ_BY_HAND = {
    # nvsos.gov answers a script with a bot check; NASS lists Nevada as not a
    # member. The office's "About" page for him (under Office Facts) is titled
    # with his name beside the office's, which is what passes rule 56's test;
    # its text, read by the same person, says he "was elected as Nevada
    # Secretary of State in 2022 and assumed office on January 2, 2023".
    # That sentence does not pass on its own, and is not made to: rule 56
    # refuses "<name> was elected as <title>" for every office, since it
    # also describes a predecessor.
    ("NV", "sos"): ("Francisco V. Aguilar",
                    "https://www.nvsos.gov/sos/sos-information/office-facts/about-francisco-v-aguilar",
                    "2026-10-26",
                    ("About Francisco V. Aguilar | Nevada Secretary of State",
                     "Francisco “Cisco” Aguilar was elected as Nevada Secretary of State in 2022 "
                     "and assumed office on January 2, 2023.")),
    # mass.gov refuses a script.
    ("MA", "ag"): ("Andrea Campbell", "https://www.mass.gov/orgs/office-of-the-attorney-general",
                   "2026-10-26",
                   ("Office of the Attorney General | Mass.gov",
                    "Attorney General Andrea Joy Campbell’s Office is an advocate and resource "
                    "for the people of Massachusetts")),
    # atg.sd.gov refuses a script.
    ("SD", "ag"): ("Marty Jackley", "https://atg.sd.gov/OurOffice/bio.aspx", "2026-10-26",
                   ("South Dakota Attorney General",
                    "Attorney General Marty J. Jackley Marty was raised in Sturgis")),
    # tn.gov refuses a script; tn.gov/attorneygeneral.html links this page as
    # "Attorney General Jonathan Skrmetti".
    ("TN", "ag"): ("Jonathan Skrmetti",
                   "https://www.tn.gov/attorneygeneral/about-the-office/general-skrmetti.html",
                   "2026-10-26",
                   ("Attorney General Jonathan Skrmetti",
                    "Attorney General Jonathan Skrmetti ... Jonathan Skrmetti has served as "
                    "Tennessee’s Attorney General and Reporter since 2022.")),
    # doj.nh.gov refuses a script. The home page's heading and name, and its
    # news item of October 23, 2026.
    ("NH", "ag"): ("John Formella", "https://www.doj.nh.gov/", "2026-10-26",
                   ("Welcome | New Hampshire Department of Justice",
                    "Attorney General John M. Formella",
                    "Attorney General Formella and Secretary of State Scanlan Provide Voters "
                    "with Update on Use of Student ID Cards Ahead of General Election")),
}

# Ids a chamber's roll calls list that belong to no member of that Congress,
# with what the record shows and why (kyc/rollcalls.py). Their votes are
# given to nobody either way (rule 17); an entry here only says the build
# need not warn about it, and validate warns once the id is a member's after
# all. Keyed on the record's id, never a name.
ROLL_CALL_NON_MEMBERS = {
    "G000578": (
        "Matt Gaetz, re-elected for FL-1 in 2024, did not take the seat in the 119th "
        "Congress: congress-legislators gives him no term in it, and FL-1's next member, "
        "Jimmy Patronis (P000622), was seated on 2025-04-02 after a special election. The "
        "Clerk's roll call 1 of 2025 (the call of the House by states, 2025-01-03) lists "
        "'Gaetz' (FL) as Not Voting; read 2026-10-18."),
}

# Lists of the statewide candidates (data/statewide_candidates.json, rule
# 91) published on a host that is not the jurisdiction's own domain
# (voting_dates.JURISDICTION_DOMAINS): the state election office's own file
# store or vendor, or - only where the state's own list could not be read or
# does not exist - a county's election office or another state body. A list
# the state's office serves only to a person's browser is read by hand from
# its own page, quoted and dated, never stood in for by another body's (rule
# 91: Nevada's, read 2026-10-25, replaced Clark County's notice; Arizona's
# Secretary of State's listing, read 2026-10-26, its Clean Elections
# Commission's voter education guide).
# {url prefix: (codes, who publishes it, own, evidence)}, where *own* is True
# only for the state election office's own document on another host. A list
# that is not the state's own is never called certified and says on the page
# why it was used (statewide.problems; PR #109 review: a county's sample
# ballot read "Certified by" the county). Being a .gov host is not enough: a
# list counts here only for the jurisdictions named. Read 2026-10-18.
STATEWIDE_LISTS_ELSEWHERE = {
    "https://votepulaskiar.gov/": (
        ("AR",), "Pulaski County Board of Election Commissioners", False,
        "the county board's Notice of Election for November 3, 2026 (PDF, Last-Modified "
        "2026-10-05); Arkansas's Secretary of State publishes no list of the November "
        "candidates, and its candidate search (candidates.arkansas.gov) names the same people "
        "for these offices"),
    "https://drive.google.com/file/d/1RKr3bLuivj8n0n29XKbQVHEgdUYwILMN/": (
        ("GU",), "Guam Election Commission", True,
        "'2026 General Election Sample Ballot', linked by that name from the Commission's home "
        "page, https://gec.guam.gov/"),
    "https://mi-boe.entellitrak.com/etk-mi-boe-prod/": (
        ("MI",), "Michigan Department of State", True,
        "the Bureau of Elections' Official Candidate Listing, linked as '2026 November General "
        "Candidate Listing' from https://www.michigan.gov/sos/elections"),
    "https://sos-prod.tnsosgovfiles.com/": (
        ("TN",), "Tennessee Secretary of State", True,
        "the Division of Elections' file store, linked as PDF from "
        "https://sos.tn.gov/elections/2026-candidate-lists"),
}

# The statewide ballot measures (data/ballot_measures.json, rule 95) cited
# from an official page on a host that is not the jurisdiction's own domain
# (voting_dates.JURISDICTION_DOMAINS): the election office's own file store
# or second domain, or a county's or town's official ballot where the state
# publishes the wording nowhere it could be read. A statewide question is
# printed on every ballot in the state, so one county's full set of official
# ballots shows what is statewide. {url prefix: (codes, who publishes it,
# evidence)}. Being a .gov host is not enough: a page counts here only for
# the jurisdictions named. Read 2026-10-19.
MEASURE_SOURCES_ELSEWHERE = {
    "https://www.clarkcountynv.gov/": (
        ("NV",), "Clark County Election Department",
        "the Department's official ballot-questions booklet for the November 3, 2026 general "
        "election, which prints State Questions 6 and 7, the two questions the Secretary of "
        "State's 2026 Petitions page names. The questions' words are quoted from it because, "
        "read on 2026-10-19, the Secretary of State's 2026 Ballot Question Guide was not yet "
        "posted ('will be published HERE prior to the 2026 General Election'); it is posted "
        "now (https://www.nvsos.gov/home/showpublisheddocument/20519/639233354596030000, linked "
        "from the 2026 Election Information page, read by hand 2026-10-25) and is the voter "
        "guide the page links; its text has not been compared with the booklet's, since "
        "nvsos.gov serves no script, so each question's words and its page stay the booklet's"),
    "https://s3.amazonaws.com/dl.ncsbe.gov/": (
        ("NC",), "North Carolina State Board of Elections",
        "the State Board's file store, linked as 'Statewide referenda' from "
        "https://www.ncsbe.gov/voting/upcoming-election"),
    "https://www.beaufortncboe.org/": (
        ("NC",), "Beaufort County Board of Elections",
        "the Legislative Services Officer's official summary explanation of the 2026 "
        "amendments (N.C.G.S. 147-54.10, adopted August 20, 2026) as the county board posts "
        "it; it was found on no state host"),
    "https://www.votedouglascounty-ne.gov/": (
        ("NE",), "Douglas County Election Commission",
        "the Commission's countywide sample ballot for the 11/03/2026 general election, the "
        "printed wording of Proposed Amendment No. 1, which the Secretary of State's pamphlet "
        "does not cover; the Legislative Council Executive Board's approved ballot statement "
        "on sos.nebraska.gov (a scan) carries the same words"),
    "https://www.edenvt.org/": (
        ("VT",), "Town of Eden",
        "the town's official sample ballot, whose 'OFFICIAL STATE CONSTITUTIONAL AMENDMENT "
        "BALLOT NOVEMBER 3, 2026' column prints both proposals; Burlington's sample ballot "
        "prints the same text word for word"),
    "https://drive.google.com/file/d/1RKr3bLuivj8n0n29XKbQVHEgdUYwILMN/": (
        ("GU",), "Guam Election Commission",
        "'2026 General Election Sample Ballots', linked by that name from "
        "https://gec.guam.gov/2026-general-election-info/"),
    "https://www.somersetcountynj.gov/": (
        ("NJ",), "Somerset County Clerk",
        "the Clerk's official 2026 general-election sample ballots for every municipality "
        "(Last-Modified 2026-10-09), linked from the County Clerk's Election Division page; "
        "the Division of Elections' 2026 page lists no statewide public question"),
    "https://www.vote.nyc/": (
        ("NY",), "Board of Elections in the City of New York",
        "the Board's 'Appendix A, Proposed Questions, 2026 General Election', linked from "
        "https://vote.nyc/page/ballot-proposals; the State Board of Elections publishes no "
        "2026 ballot-proposals page"),
    "https://www.gtcountysc.gov/": (
        ("SC",), "Georgetown County Board of Voter Registration and Elections",
        "the county's official sample ballots for all 52 ballot styles of the November 3, "
        "2026 general election, linked from https://www.gtcountysc.gov/398/Upcoming-Elections"),
}

# The local ballot questions (data/local_measures.json, kyc/local_measures.py):
# the hosts each county's record may cite, by the county codes they may speak
# for, who publishes there, and how that is known. A state election office's
# own domain (voting_dates.official_source) needs no entry. Being a .gov host
# is not enough (rule 84): a county's host counts only for that county, and a
# city's only for the counties the city lies in. A .gov host's evidence is the
# CISA .gov registry's row for it (dotgov-data current-full.csv, read
# 2026-11-01); any other host's is the page that links it, read that day.
# {host (or a URL prefix): (county codes, publisher, evidence)}. A host
# matches itself and its subdomains.
_DOTGOV = "the .gov registry (CISA dotgov-data current-full.csv, read 2026-11-01) lists "
LOCAL_MEASURE_SOURCES = {
    "lavote.gov": (("06037",), "Los Angeles County Registrar-Recorder/County Clerk",
                   _DOTGOV + "lavote.gov: County, 'County of Los Angeles', Downey, CA"),
    "alamedacountyca.gov": (("06001",), "Alameda County Registrar of Voters",
        _DOTGOV + "alamedacountyca.gov: County, 'Alameda County', Oakland, CA"),
    # Another county's source only through the one document: a host entry
    # would let any Alameda page stand for Contra Costa or Santa Clara.
    "https://acvote.alamedacountyca.gov/acvote-assets/02_election_information/PDFs/20261103/"
    "Measures/public_transit_revenue_measure.pdf": (("06013", "06085"),
        "Alameda County Registrar of Voters",
        _DOTGOV + "alamedacountyca.gov: County, 'Alameda County', Oakland, CA. Its copy of the "
        "five registrars' joint Notice of General Election for the Public Transit Revenue "
        "Measure District (Measure RTM), which names the Contra Costa (06013) and Santa Clara "
        "(06085) registrars; their own sites could not be read"),
    "cuyahogacounty.gov": (("39035",), "Cuyahoga County Board of Elections",
                           _DOTGOV + "cuyahogacounty.gov: County, 'Cuyahoga County', Cleveland, OH"),
    "oaklandcountymi.gov": (("26125",), "Oakland County Clerk",
                            _DOTGOV + "oaklandcountymi.gov: County, 'Oakland County Michigan', Pontiac, MI"),
    "westchestergov.com": (("36119",), "Westchester County Board of Elections",
        "the Census Bureau's 2022 Government Units listing gives http://www.westchestergov.com as "
        "the County of Westchester's website, and it now redirects to westchestercountyny.gov"),
    "westchestercountyny.gov": (("36119",), "Westchester County Board of Elections",
        _DOTGOV + "westchestercountyny.gov: County, 'County of Westchester', White Plains, NY"),
    "dallascityhall.com": (("48113",), "City of Dallas City Secretary",
        "the Census Bureau's 2022 Government Units listing gives http://www.dallascityhall.com as "
        "the City of Dallas's website"),
    "https://content.civicplus.com/api/assets/az-pimacounty/": (("04019",), "Pima County Elections Department",
        "Pima County's own file store, linked as '2026 General Election Proposition Text (PDF)' "
        "from https://www.pima.gov/810/Upcoming-Elections"),
    "pima.gov": (("04019",), "Pima County", _DOTGOV + "pima.gov: County, 'Pima County Government', Tucson, AZ"),
    "maricopa.gov": (("04013",), "Maricopa County Elections Department",
                     _DOTGOV + "maricopa.gov: County, 'Maricopa County', Phoenix, AZ"),
    "bexar.gov": (("48029",), "Bexar County Elections Department",
                  _DOTGOV + "bexar.gov: County, 'Bexar County', San Antonio, TX"),
    "saccounty.gov": (("06067",), "Sacramento County Voter Registration and Elections",
                      _DOTGOV + "saccounty.gov: County, 'County of Sacramento', Sacramento, CA"),
    "sbcounty.gov": (("06071",), "San Bernardino County Registrar of Voters",
                     _DOTGOV + "sbcounty.gov: County, 'San Bernardino County', San Bernardino, CA"),
    "fultoncountyga.gov": (("13121",), "Fulton County Registration and Elections",
                           _DOTGOV + "fultoncountyga.gov: County, 'Fulton County Government', Atlanta, GA"),
    "https://hctxdnnstg.blob.core.windows.net/harrisvotes/": (("48201",), "Harris County Clerk",
        "the file store harrisvotes.com links its November 3, 2026 sample ballot from "
        "(https://www.harrisvotes.com/, read 2026-11-01)"),
    "harrisvotes.com": (("48201",), "Harris County Clerk",
        "linked as the county's voter site from https://www.harriscountytx.gov/ (read 2026-11-01)"),
    "houstontx.gov": (("48201",), "City of Houston",
                      _DOTGOV + "houstontx.gov: City, 'City of Houston', Houston, TX"),
    "kingcounty.gov": (("53033",), "King County Elections",
                       _DOTGOV + "kingcounty.gov: County, 'King County Information Technology (KCIT)', Seattle, WA"),
    "ocvote.gov": (("06059",), "Orange County Registrar of Voters",
                   _DOTGOV + "ocvote.gov: County, 'Orange County Registrar of Voters', Santa Ana, CA"),
    "https://s3.us-west-1.amazonaws.com/wakegov.com.if-us-west-1/": (("37183",), "Wake County Board of Elections",
        "Wake County's file store, which https://www.wake.gov/departments-government/board-elections "
        "links its election documents from (read 2026-11-01)"),
    "wake.gov": (("37183",), "Wake County", _DOTGOV + "wake.gov: County, 'Wake County Information Services', Raleigh, NC"),
    "https://apps.meckboe.org/pages/SampleBallots/": (("37119",), "Mecklenburg County Board of Elections",
        "the Board's sample ballots, each linked as '2026 General Election Sample Ballots: Click Here for "
        "your Sample Ballot' from its address search (https://apps.meckboe.org/addressSearch_New.aspx), "
        "which https://vote.mecknc.gov/ links as 'Look-Up Districts by Address' (read 2026-11-01)"),
    "franklincountyohio.gov": (("39049",), "Franklin County Board of Elections",
                               _DOTGOV + "franklincountyohio.gov: County, 'Franklin County Data Center', Columbus, OH"),
    "phila.gov": (("42101",), "Philadelphia City Commissioners",
                  _DOTGOV + "phila.gov: City, 'Office of Innovation and Technology', Philadelphia, PA"),
    "santaclaracounty.gov": (("06085",), "Santa Clara County Registrar of Voters",
                             _DOTGOV + "santaclaracounty.gov: County, 'County of Santa Clara', San Jose, CA"),
    "voteinfo.net": (("06065",), "Riverside County Registrar of Voters",
        "the California Secretary of State's county elections offices page "
        "(https://www.sos.ca.gov/elections/voting-resources/county-elections-offices, read "
        "2026-11-01) gives www.voteinfo.net as Riverside County's"),
    "sdvote.com": (("06073",), "San Diego County Registrar of Voters",
        "the California Secretary of State's county elections offices page "
        "(https://www.sos.ca.gov/elections/voting-resources/county-elections-offices, read "
        "2026-11-01) gives www.sdvote.com as San Diego County's"),
    "voteorangefl.gov": (("12095",), "Orange County Supervisor of Elections",
                         _DOTGOV + "voteorangefl.gov: County, 'Orange County Supervisor of Elections', Orlando, FL"),
    "votetravis.gov": (("48453",), "Travis County Clerk, Elections Division",
                       _DOTGOV + "votetravis.gov: County, \"Travis County Clerk's Office\", Austin, TX"),
    "alleghenycounty.us": (("42003",), "Allegheny County Elections Division",
        "the Census Bureau's 2022 Government Units listing gives http://www.alleghenycounty.us as "
        "the County of Allegheny's website"),
    "browardvotes.gov": (("12011",), "Broward County Supervisor of Elections",
                         _DOTGOV + "browardvotes.gov: County, 'Broward County Supervisor of Elections', Fort Lauderdale, FL"),
    "chandleraz.gov": (("04013",), "City of Chandler City Clerk",
                       _DOTGOV + "chandleraz.gov: City, 'City of Chandler', Chandler, AZ"),
    "mesaaz.gov": (("04013",), "City of Mesa City Clerk",
                   _DOTGOV + "mesaaz.gov: City, 'City Of Mesa', Mesa, AZ"),
    "phoenix.gov": (("04013",), "City of Phoenix City Clerk",
                    _DOTGOV + "phoenix.gov: City, 'City Of Phoenix', Phoenix, AZ"),
    "clarkcountynv.gov": (("32003",), "Clark County Election Department",
                          _DOTGOV + "clarkcountynv.gov: County, 'Clark County Nevada', Las Vegas, NV"),
    "collincountytx.gov": (("48085",), "Collin County Elections",
        _DOTGOV + "collincountytx.gov: County, 'Collin County Government', McKinney, TX"),
    "https://www.collincountytx.gov/docs/default-source/elections/sample-ballots/"
    "20261103_joint-general-and-special-election_all-race-sample-ballot_final.pdf": (
        ("48113",), "Collin County Elections",
        _DOTGOV + "collincountytx.gov: County, 'Collin County Government', McKinney, TX. For "
        "Dallas County (48113) only this all-race sample ballot's City of Garland proposition, "
        "for Garland's precincts in Collin County"),
    "contracostavote.gov": (("06013",), "Contra Costa County Elections Division",
        _DOTGOV + "contracostavote.gov: County, 'Contra Costa County Clerk-Recorder-Elections "
        "Department', Martinez, CA"),
    "cookcountyclerkil.gov": (("17031",), "Cook County Clerk",
                              _DOTGOV + "cookcountyclerkil.gov: County, 'Cook County Clerk', Chicago, IL"),
    "dallascountyvotes.org": (("48113",), "Dallas County Elections Department",
        "linked as the county's elections site from https://www.dallascounty.org/ (read 2026-11-01)"),
    "duvalelections.gov": (("12031",), "Duval County Supervisor of Elections",
                           _DOTGOV + "duvalelections.gov: County, 'Duval County Supervisor of Elections', Jacksonville, FL"),
    "fairfaxcounty.gov": (("51059",), "Fairfax County Office of Elections",
                          _DOTGOV + "fairfaxcounty.gov: County, 'Fairfax County Government', Fairfax, VA"),
    "fresnocountyca.gov": (("06019",), "Fresno County Clerk/Registrar of Voters",
                           _DOTGOV + "fresnocountyca.gov: County, 'County of Fresno', Clovis, CA"),
    "gwinnettcounty.com": (("13135",), "Gwinnett County Voter Registrations and Elections",
        "the Census Bureau's 2022 Government Units listing gives http://www.gwinnettcounty.com/ as "
        "the County of Gwinnett's website"),
    "hennepincounty.gov": (("27053",), "Hennepin County Elections",
                           _DOTGOV + "hennepincounty.gov: County, 'Hennepin County', Minneapolis, MN"),
    "mecknc.gov": (("37119",), "Mecklenburg County Board of Elections",
                   _DOTGOV + "mecknc.gov: County, 'Mecklenburg County', Charlotte, NC"),
    "miamidade.gov": (("12086",), "Miami-Dade Elections Department",
                      _DOTGOV + "miamidade.gov: County, 'Miami Dade County', Miami, FL"),
    "votemiamidade.gov": (("12086",), "Miami-Dade Elections Department",
        _DOTGOV + "votemiamidade.gov: County, 'Miami-Dade County Elections Department', Miami, FL"),
    "montgomerycountymd.gov": (("24031",), "Montgomery County Board of Elections",
        _DOTGOV + "montgomerycountymd.gov: County, 'Montgomery County Maryland', Rockville, MD"),
    "nassaucountyny.gov": (("36059",), "Nassau County Board of Elections",
                           _DOTGOV + "nassaucountyny.gov: County, 'Nassau County', Mineola, NY"),
    "palmbeachschools.org": (("12099",), "School District of Palm Beach County",
        "the school district's own site (its title 'Home - Palm Beach County School District', read "
        "2026-11-01), for its own referendum only: the Supervisor of Elections' site could not be "
        "read, and the Census listing's address for the district, palmbeach.k12.fl.us, no longer "
        "resolves"),
    "saltlakecounty.gov": (("49035",), "Salt Lake County Clerk",
                           _DOTGOV + "saltlakecounty.gov: County, 'Salt Lake County', SLC, UT"),
    "suffolkcountyny.gov": (("36103",), "Suffolk County Board of Elections",
                            _DOTGOV + "suffolkcountyny.gov: County, 'Suffolk County Government', Hauppauge, NY"),
    "tarrantcountytx.gov": (("48439",), "Tarrant County Elections",
                            _DOTGOV + "tarrantcountytx.gov: County, 'Tarrant County', Fort Worth, TX"),
    "vote.nyc": (("36047", "36081", "36061", "36005"), "Board of Elections in the City of New York",
        "the Board's own site; its 'Appendix A, Proposed Questions, 2026 General Election' is linked "
        "from https://vote.nyc/page/ballot-proposals (MEASURE_SOURCES_ELSEWHERE)"),
    "votedenton.gov": (("48121",), "Denton County Elections",
        _DOTGOV + "votedenton.gov: County, 'Denton County Elections Administration', Denton, TX"),
    "votehillsborough.gov": (("12057",), "Hillsborough County Supervisor of Elections",
        _DOTGOV + "votehillsborough.gov: County, 'Hillsborough County Supervisor of Elections', Tampa, FL"),
    "votepalmbeach.gov": (("12099",), "Palm Beach County Supervisor of Elections",
        _DOTGOV + "votepalmbeach.gov: County, 'Palm Beach County Supervisor of Elections', West Palm Beach, FL"),
    "waynecountymi.gov": (("26163",), "Wayne County Clerk",
                          _DOTGOV + "waynecountymi.gov: County, 'Charter County of Wayne', Detroit, MI"),
}

# A holder whose name the list of candidates prints with another given name,
# where only a short form and its full form differ (rule 56: a different
# first name is never taken on a surname alone). {(state, office, holder as
# the rosters name them): (the list's name, evidence)}.
STATEWIDE_NAME_FORMS = {
    ("NV", "governor", "Joe Lombardo"): (
        "Lombardo, Joseph",
        "the Governor's own site, gov.nv.gov (read 2026-10-18), links his account "
        "twitter.com/JosephMLombardo; the Secretary of State's statewide certified list "
        "prints 'Lombardo, Joseph | Joseph Lombardo | Republican Party | Governor' (read by "
        "hand 2026-10-25), as Clark County's notice printed 'Lombardo, Joseph REP', and every "
        "reader read it as the governor"),
}

# A candidate the Clerk of the House's "Statistics of the Presidential and
# Congressional Election" prints under one form of their name and the second
# compilation its counts are checked against (kyc/seat_history.py, rule 90)
# under another: the legal name a state's returns print beside the name the
# person goes by. Keyed on the seat as the cache keys it ("PA-4"), the
# election's year and the Clerk's name exactly as read; (the second
# compilation's name exactly as its table or infobox gives it, the evidence
# that the two are one person: the state's own returns, their words and the
# day read). The name then joins only a row whose whole name is that one,
# never a surname (rules 3, 17, 25), and the counts are still checked
# (seat_history.TOLERANCE). Without one the result is withheld, as PR #187
# left these three: the check matches by surname, and "Cunnane", "Hernandez"
# and "Pudlo" are on neither page's row.
SEAT_HISTORY_NAMES = {
    ("PA-4", 2020, "Madeleine Dean Cunnane"): (
        "Madeleine Dean",
        "the Pennsylvania Department of State's returns of the 2020 general election "
        "(electionreturns.pa.gov, election 83, Representative in Congress, read 2026-11-12) "
        "give the 4th Congressional District as 'DEM CUNNANE, MADELEINE DEAN 264637 59.53' and "
        "'REP BARNETTE, KATHY 179926', the Clerk's 'Madeleine Dean Cunnane, Democrat' 264,637 "
        "and 'Kathy Barnette, Republican' 179,926; Wikipedia's 2020 Pennsylvania page gives "
        "'Madeleine Dean (incumbent)' 264,637, and her article opens \"Madeleine Dean Cunnane "
        "(born June 6, 1959) ... U.S. representative for Pennsylvania's 4th congressional "
        "district since 2019\"; the Clerk's 2018, 2022 and 2024 statistics name the district's "
        "winner 'Madeleine Dean', and congress-legislators seats D000631, Madeleine Dean, in "
        "PA-4 for the term the 2020 election chose"),
    ("TX-15", 2020, "Monica De La Cruz-Hernandez"): (
        "Monica De La Cruz",
        "the Texas Secretary of State's County by County Canvass Report of the 2020 November "
        "3rd General Election (results.texas-election.com/static/data/Reports/44144/"
        "CountybyCountyCanvassReport.pdf, page 73; the address answers this project's reader "
        "403, so read 2026-11-12 from the Internet Archive's capture of 2020-12-16) gives 'U. S. "
        "REPRESENTATIVE DISTRICT 15 ... MONICA DE LA CRUZ-HERNANDEZ [REP] ... TOTAL VOTES "
        "109,017', the Clerk's 'Monica De La Cruz-Hernandez, Republican' 109,017; Wikipedia's "
        "2020 Texas page lists the Republican nominee as 'Monica de la Cruz-Hernandez, insurance "
        "agent' and gives '[[Monica De La Cruz]]' 109,017 in the district's infobox and "
        "general-election table (read 2026-11-12); the Clerk's 2022 and 2024 statistics name "
        "the district's winner 'Monica De La Cruz'; and the FEC files one candidate, "
        "H0TX15124, as 'DE LA CRUZ HERNANDEZ, MONICA' for 2020 and 'DE LA CRUZ, MONICA' for "
        "2022, 2024 and 2026, Texas's 15th district each time (its candidate history, read "
        "2026-11-12)"),
    ("CA-30", 2022, "G. “Maebe A. Girl” Pudlo"): (
        "Maebe A. Girl",
        "the California Secretary of State's Statement of Vote of the November 8, 2022 general "
        "election, 'United States Representative in Congress by District' (elections.cdn.sos."
        "ca.gov/sov/2022-general/sov/48-congress.pdf, page 54, read 2026-11-12), gives '30th "
        "Congressional District: G \"Maebe A. Girl\" Pudlo DEM 60,968' beside 'Adam B. Schiff "
        "DEM 150,100', the ballot's quoted name being the one the Clerk prints; Wikipedia's 2022 "
        "California page gives 'Maebe A. Girl' 60,968 in the district's infobox, and her article "
        "opens \"Maebe A. Girl (also known as G. Pudlo; born July 27, 1986)\""),
}

# The Clerk's counts for a contest that are a later round than the Clerk's
# statistics say (kyc/seat_history.py, rule 90): the file prints them as the
# election's with no footnote, and the jurisdiction's own official results
# give them as a runoff's or as a ranked-choice tabulation's final round.
# Keyed on the seat as the cache keys it and the election's year; "kind" is
# "runoff" or "rcv-final", "date" a runoff's day, "counts" every candidate
# the Clerk lists, by the Clerk's name, with the count the document gives
# them, "source" (the words the page names the document by, a singular noun
# phrase the strip's cell sets before "gives them as the runoff's" or "the
# final round's", and its address) and the evidence. Applied only where the Clerk's
# file prints exactly those names and counts and no other (a reissued file
# that differs is an error, seat_history.result_of), and the result is
# still checked against the second compilation's table of that round.
SEAT_HISTORY_ROUNDS = {
    ("GU-0", 2020): {
        "kind": "runoff",
        "date": "2020-11-17",
        "counts": {"Michael F. Q. San Nicolas": 10467, "Robert A. Underwood": 7090},
        "source": ("the Guam Election Commission’s official results report",
                   "https://gec.guam.gov/2020-runoff-election-unofficial-results-precinct-report/"),
        "evidence": (
            "the Clerk's 2020 statistics list for Guam's delegate 'Michael F. Q. San Nicolas, "
            "Democrat 10,467', 'Robert A. Underwood, Democrat 7,090', 'Under Votes 28', 'Over "
            "Votes 5', 'Total 17,590', and say nothing of a runoff; the Guam Election "
            "Commission's post '2020 Runoff Election, Official Results Precinct Report' (gec.guam."
            "gov, posted 2020-12-03) links its 'Election Summary Report' (drive.google.com/file/"
            "d/1Y8lzyXXcAiRJh28RnNjJKPpjZvu69KO6, read 2026-11-12), headed 'Summary Results "
            "Report OFFICIAL RESULTS Guam 2020 Runoff November 17, 2020', which gives "
            "'Non-Voting Delegate to the U.S. House of Representatives ... DEM San Nicolas, "
            "Michael F.Q. 10,467 59.62% DEM Underwood, Robert Anacletus 7,090 40.38% Total Votes "
            "Cast 17,557 ... Overvotes 5 Undervotes 28 Contest Totals 17,590'; the November 3 "
            "round had three candidates (Wikipedia's 2020 Guam page: San Nicolas 13,000, "
            "Underwood 9,300, Wil Castro 5,942), and no one a majority (48 U.S.C. 1712)"),
    },
    ("ME-2", 2018): {
        "kind": "rcv-final",
        "counts": {"Jared F. Golden": 142440, "Bruce Poliquin": 138931},
        "source": ("the Maine Secretary of State’s certified ranked-choice tabulation (an "
                   "archived copy)",
                   "https://web.archive.org/web/20181214213948/https://www.maine.gov/sos/cec/"
                   "elec/results/2018/updated-summary-report-CD2.xls"),
        "evidence": (
            "the Clerk's 2018 statistics list Maine's 2nd district as 'Jared F. Golden, "
            "Democrat 142,440' and 'Bruce Poliquin, Republican 138,931', with no other name and "
            "no word of a round; the Secretary of State's 'Tabulations for Elections held in "
            "2018' page linked 'Representative to Congress - District 2 - Results Certified to "
            "the Governor 11/26/18' to www.maine.gov/sos/cec/elec/results/2018/updated-summary-"
            "report-CD2.xls, whose 'Summary Report ... Congressional District 2' gives 'Round 1' "
            "'DEM Golden, Jared F. 132013', 'REP Poliquin, Bruce 134184', 'Bond, Tiffany L. "
            "16552', 'Hoar, William R.S. 6875' and 'Round 2' 'DEM Golden, Jared F. 142440', 'REP "
            "Poliquin, Bruce 138931', 'Continuing Ballots 281371'. maine.gov refuses this "
            "project's reader (403) and the address answered 404 from 2026, so the file was read "
            "2026-11-12 from the Internet Archive's capture of 2018-12-14, the one digest it "
            "holds for the address from then to 2025-04-04"),
    },
}

# Phrases in a Status value that mean the incumbent is not on the 2026 ballot.
NOT_SEEKING_MARKERS = ("retiring", "not running", "defeated", "ineligible", "resigned")


def status_override(member_id, current):
    """Return the curated status for a member, falling back to *current*.

    Keyed on bioguide id only (rules 3 and 17): a name never selects a note."""
    entry = MEMBER_STATUS_BY_ID.get(member_id) if member_id else None
    return entry[0] if entry else current


def is_not_seeking(status):
    """True when a status line says the incumbent is leaving the seat."""
    lowered = str(status or "").lower()
    return any(marker in lowered for marker in NOT_SEEKING_MARKERS)


def blocked_campaign_host(url):
    """The BLOCKED_CAMPAIGN_HOSTS key that bars *url*, or None."""
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return None
    bare = host[4:] if host.startswith("www.") else host
    for key in (host, bare):
        if key and key in BLOCKED_CAMPAIGN_HOSTS:
            return key
    return None
