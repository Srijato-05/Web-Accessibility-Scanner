import json
import os
import asyncio
import aiohttp
import sys
import random

# ==========================================
#        CONFIGURATION
# ==========================================
OUTPUT_FILE = "targets.json"
CONCURRENT_CHECKS = 100       # High concurrency for speed
TIMEOUT_SECONDS = 5           # Fast fail to churn through dead links
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

# ==========================================
#        DATASET: LOGIC MULTIPLIERS
# ==========================================
STATES = [
    "ap", "ar", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana", "himachal", 
    "jharkhand", "karnataka", "kerala", "mp", "maharashtra", "manipur", "meghalaya", "mizoram", 
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tn", "telangana", "tripura", 
    "up", "uttarakhand", "wb", "delhi", "jk", "ladakh", "andaman", "lakshadweep", "puducherry"
]

DEPARTMENTS = [
    "police", "transport", "health", "education", "finance", "pwd", "agriculture", 
    "tourism", "revenue", "forest", "excise", "socialwelfare", "election", "prisons", 
    "rural", "urban", "water", "electricity", "labour", "industries", "mining", 
    "sports", "culture", "information", "planning", "housing", "food", "civilsupplies"
]

# THE MEGATON LIST: 750+ DISTRICTS (Source: NIC & Census Data)
# This list is critical for the permutation engine.
DISTRICTS = [
    "nicobar", "north-middle-andaman", "south-andaman", "anantapur", "chittoor", "east-godavari", "guntur", "kadapa", 
    "krishna", "kurnool", "nellore", "prakasam", "srikakulam", "visakhapatnam", "vizianagaram", "west-godavari", 
    "anjaw", "changlang", "dibang-valley", "east-kameng", "east-siang", "kra-daadi", "kurung-kumey", "lohit", 
    "longding", "lower-dibang-valley", "lower-subansiri", "namsai", "papum-pare", "siang", "tawang", "tirap", 
    "upper-siang", "upper-subansiri", "west-kameng", "west-siang", "baksa", "barpeta", "biswanath", "bongaigaon", 
    "cachar", "charaideo", "chirang", "darrang", "dhemaji", "dhubri", "dibrugarh", "dima-hasao", "goalpara", 
    "golaghat", "hailakandi", "hojai", "jorhat", "kamrup", "kamrup-metro", "karbi-anglong", "karimganj", "kokrajhar", 
    "lakhimpur", "majuli", "morigaon", "nagaon", "nalbari", "sivasagar", "sonitpur", "south-salmara-mankachar", 
    "tinsukia", "udalguri", "west-karbi-anglong", "araria", "arwal", "aurangabad", "banka", "begusarai", "bhagalpur", 
    "bhojpur", "buxar", "darbhanga", "east-champaran", "gaya", "gopalganj", "jamui", "jehanabad", "kaimur", "katihar", 
    "khagaria", "kishanganj", "lakhisarai", "madhepura", "madhubani", "munger", "muzaffarpur", "nalanda", "nawada", 
    "patna", "purnia", "rohtas", "saharsa", "samastipur", "saran", "sheikhpura", "sheohar", "sitamarhi", "siwan", 
    "supaul", "vaishali", "west-champaran", "chandigarh", "balod", "baloda-bazar", "balrampur", "bastar", "bemetara", 
    "bijapur", "bilaspur", "dantewada", "dhamtari", "durg", "gariaband", "gaurela-pendra-marwahi", "janjgir-champa", 
    "jashpur", "kabirdham", "kanker", "kondagaon", "korba", "korea", "mahasamund", "mungeli", "narayanpur", "raigarh", 
    "raipur", "rajnandgaon", "sukma", "surajpur", "surguja", "dadra-nagar-haveli", "daman", "diu", "central-delhi", 
    "east-delhi", "new-delhi", "north-delhi", "north-east-delhi", "north-west-delhi", "shahdara", "south-delhi", 
    "south-east-delhi", "south-west-delhi", "west-delhi", "north-goa", "south-goa", "ahmedabad", "amreli", "anand", 
    "aravalli", "banaskantha", "bharuch", "bhavnagar", "botad", "chhota-udepur", "dahod", "dang", "devbhoomi-dwarka", 
    "gandhinagar", "gir-somnath", "jamnagar", "junagadh", "kheda", "kutch", "mahisagar", "mehsana", "morbi", "narmada", 
    "navsari", "panchmahal", "patan", "porbandar", "rajkot", "sabarkantha", "surat", "surendranagar", "tapi", "vadodara", 
    "valsad", "ambala", "bhiwani", "charkhi-dadri", "faridabad", "fatehabad", "gurugram", "hisar", "jhajjar", "jind", 
    "kaithal", "karnal", "kurukshetra", "mahendragarh", "nuh", "palwal", "panchkula", "panipat", "rewari", "rohtak", 
    "sirsa", "sonipat", "yamunanagar", "bilaspur", "chamba", "hamirpur", "kangra", "kinnaur", "kullu", "lahaul-spiti", 
    "mandi", "shimla", "sirmaur", "solan", "una", "anantnag", "bandipora", "baramulla", "budgam", "doda", "ganderbal", 
    "jammu", "kathua", "kishtwar", "kulgam", "kupwara", "poonch", "pulwama", "rajouri", "ramban", "reasi", "samba", 
    "shopian", "srinagar", "udhampur", "bokaro", "chatra", "deoghar", "dhanbad", "dumka", "east-singhbhum", "garhwa", 
    "giridih", "godda", "gumla", "hazaribagh", "jamtara", "khunti", "koderma", "latehar", "lohardaga", "pakur", "palamu", 
    "ramgarh", "ranchi", "sahibganj", "seraikela-kharsawan", "simdega", "west-singhbhum", "bagalkot", "ballari", 
    "belagavi", "bengaluru-rural", "bengaluru-urban", "bidar", "chamarajanagar", "chikkaballapura", "chikkamagaluru", 
    "chitradurga", "dakshina-kannada", "davangere", "dharwad", "gadag", "hassan", "haveri", "kalaburagi", "kodagu", 
    "kolar", "koppal", "mandya", "mysuru", "raichur", "ramanagara", "shivamogga", "tumakuru", "udupi", "uttara-kannada", 
    "vijayapura", "yadgir", "alappuzha", "ernakulam", "idukki", "kannur", "kasaragod", "kollam", "kottayam", "kozhikode", 
    "malappuram", "palakkad", "pathanamthitta", "thiruvananthapuram", "thrissur", "wayanad", "kargil", "leh", "lakshadweep", 
    "agar-malwa", "alirajpur", "anuppur", "ashoknagar", "balaghat", "barwani", "betul", "bhind", "bhopal", "burhanpur", 
    "chhatarpur", "chhindwara", "damoh", "datia", "dewas", "dhar", "dindori", "guna", "gwalior", "harda", "hoshangabad", 
    "indore", "jabalpur", "jhabua", "katni", "khandwa", "khargone", "mandla", "mandsaur", "morena", "narsinghpur", "neemuch", 
    "niwari", "panna", "raisen", "rajgarh", "ratlam", "rewa", "sagar", "satna", "sehore", "seoni", "shahdol", "shajapur", 
    "sheopur", "shivpuri", "sidhi", "singrauli", "tikamgarh", "ujjain", "umaria", "vidisha", "ahmednagar", "akola", 
    "amravati", "aurangabad", "beed", "bhandara", "buldhana", "chandrapur", "dhule", "gadchiroli", "gondia", "hingoli", 
    "jalgaon", "jalna", "kolhapur", "latur", "mumbai-city", "mumbai-suburban", "nagpur", "nanded", "nandurbar", "nashik", 
    "osmanabad", "palghar", "parbhani", "pune", "raigad", "ratnagiri", "sangli", "satara", "sindhudurg", "solapur", "thane", 
    "wardha", "washim", "yavatmal", "bishnupur", "chandel", "churachandpur", "imphal-east", "imphal-west", "jiribam", 
    "kakching", "kamjong", "kangpokpi", "noney", "pherzawl", "senapati", "tamenglong", "tengnoupal", "thoubal", "ukhrul", 
    "east-garo-hills", "east-jaintia-hills", "east-khasi-hills", "north-garo-hills", "ribhoi", "south-garo-hills", 
    "south-west-garo-hills", "south-west-khasi-hills", "west-garo-hills", "west-jaintia-hills", "west-khasi-hills", 
    "aizawl", "champhai", "kolasib", "lawngtlai", "lunglei", "mamit", "saiha", "serchhip", "dimapur", "kiphire", "kohima", 
    "longleng", "mokokchung", "mon", "peren", "phek", "tuensang", "wokha", "zunheboto", "angul", "balangir", "balasore", 
    "bargarh", "bhadrak", "boudh", "cuttack", "deogarh", "dhenkanal", "gajapati", "ganjam", "jagatsinghpur", "jajpur", 
    "jharsuguda", "kalahandi", "kandhamal", "kendrapara", "kendujhar", "khordha", "koraput", "malkangiri", "mayurbhanj", 
    "nabarangpur", "nayagarh", "nuapada", "puri", "rayagada", "sambalpur", "subarnapur", "sundergarh", "karaikal", "mahe", 
    "puducherry", "yanam", "amritsar", "barnala", "bathinda", "faridkot", "fatehgarh-sahib", "fazilka", "ferozepur", 
    "gurdaspur", "hoshiarpur", "jalandhar", "kapurthala", "ludhiana", "mansa", "moga", "muktsar", "nawanshahr", "pathankot", 
    "patiala", "rupnagar", "sahibzada-ajit-singh-nagar", "sangrur", "tarn-taran", "ajmer", "alwar", "banswara", "baran", 
    "barmer", "bharatpur", "bhilwara", "bikaner", "bundi", "chittorgarh", "churu", "dausa", "dholpur", "dungarpur", 
    "hanumangarh", "jaipur", "jaisalmer", "jalore", "halawar", "jhunjhunu", "jodhpur", "karauli", "kota", "nagaur", "pali", 
    "pratapgarh", "rajsamand", "sawai-madhopur", "sikar", "sirohi", "sriganganagar", "tonk", "udaipur", "east-sikkim", 
    "north-sikkim", "south-sikkim", "west-sikkim", "ariyalur", "chennai", "coimbatore", "cuddalore", "dharmapuri", 
    "dindigul", "erode", "kallakurichi", "kanchipuram", "kanyakumari", "karur", "krishnagiri", "madurai", "nagapattinam", 
    "namakkal", "nilgiris", "perambalur", "pudukkottai", "ramanathapuram", "ranipet", "salem", "sivaganga", "tenkasi", 
    "thanjavur", "theni", "thoothukudi", "tiruchirappalli", "tirunelveli", "tirupathur", "tiruppur", "tiruvallur", 
    "tiruvannamalai", "tiruvarur", "vellore", "viluppuram", "virudhunagar", "adilabad", "bhadradri-kothagudem", "hyderabad", 
    "jagtial", "jangaon", "jayashankar-bhupalpally", "jogulamba-gadwal", "kamareddy", "karimnagar", "khammam", 
    "komaram-bheem", "mahambubabad", "mahabubnagar", "mancherial", "medak", "medchal-malkajgiri", "mulugu", "nagarkurnool", 
    "nalgonda", "narayanpet", "nirmal", "nizamabad", "peddapalli", "rajanna-sircilla", "rangareddy", "sangareddy", 
    "siddipet", "suryapet", "vikarabad", "wanaparthy", "warangal-rural", "warangal-urban", "yadadri-bhuvanagiri", "dhalai", 
    "gomati", "khowai", "north-tripura", "sepahijala", "south-tripura", "unakoti", "west-tripura", "agra", "aligarh", 
    "ambedkar-nagar", "amethi", "amroha", "auraiya", "ayodhya", "azamgarh", "bagpat", "bahraich", "ballia", "balrampur", 
    "banda", "barabanki", "bareilly", "basti", "bhadohi", "bijnor", "budaun", "bulandshahr", "chandauli", "chitrakoot", 
    "deoria", "etah", "etawah", "farrukhabad", "fatehpur", "firozabad", "gautam-buddha-nagar", "ghaziabad", "ghazipur", 
    "gonda", "gorakhpur", "hamirpur", "hapur", "hardoi", "hathras", "jalaun", "jaunpur", "jhansi", "kannauj", "kanpur-dehat", 
    "kanpur-nagar", "kasganj", "kaushambi", "kheri", "kushinagar", "lalitpur", "lucknow", "maharajganj", "mahoba", "mainpuri", 
    "mathura", "mau", "meerut", "mirzapur", "moradabad", "muzaffarnagar", "pilibhit", "pratapgarh", "prayagraj", "raebareli", 
    "rampur", "saharanpur", "sambhal", "sant-kabir-nagar", "shahjahanpur", "shamli", "shravasti", "siddharthnagar", 
    "sitapur", "sonbhadra", "sultanpur", "unnao", "varanasi", "almora", "bageshwar", "chamoli", "champawat", "dehradun", 
    "haridwar", "nainital", "pauri-garhwal", "pithoragarh", "rudraprayag", "tehri-garhwal", "udham-singh-nagar", 
    "uttarkashi", "alipurduar", "bankura", "birbhum", "cooch-behar", "dakshin-dinajpur", "darjeeling", "hooghly", "howrah", 
    "jalpaiguri", "jhargram", "kalimpong", "kolkata", "malda", "murshidabad", "nadia", "north-24-parganas", 
    "paschim-bardhaman", "paschim-medinipur", "purba-bardhaman", "purba-medinipur", "purulia", "south-24-parganas", 
    "uttar-dinajpur"
]

# ==========================================
#        VALIDATION LOGIC
# ==========================================

async def check_target(session, url):
    """
    Tries to connect to a URL. Returns the URL if it's alive (200-399 or 403).
    403 is considered 'Alive' because it means the server exists but blocks bots (valid target for stealth).
    """
    try:
        # We use HEAD to be fast, but some servers block HEAD, so we might need GET if HEAD fails with 405
        # For speed, we stick to HEAD with a strict timeout.
        async with session.head(url, timeout=TIMEOUT_SECONDS, allow_redirects=True, ssl=False) as resp:
            # 200: OK, 3xx: Redirect, 403: Forbidden (Firewall exists), 406: Not Acceptable
            if resp.status < 400 or resp.status in [403, 406]:
                return url
    except:
        pass
    return None

async def validate_targets_parallel(raw_targets):
    """
    Validates a massive list of URLs concurrently using aiohttp.
    """
    unique = list(set(raw_targets))
    print(f"[INFO] Generating Permutations: {len(unique)} candidates generated.")
    print(f"[INFO] Starting Swarm Validation (Concurrent Limit: {CONCURRENT_CHECKS})...")
    
    valid_targets = []
    
    # Randomize User Agent for each session to reduce block rate
    async with aiohttp.ClientSession(headers={"User-Agent": random.choice(USER_AGENTS)}) as session:
        # Process in chunks to respect OS file descriptor limits
        total = len(unique)
        for i in range(0, total, CONCURRENT_CHECKS):
            chunk = unique[i:i+CONCURRENT_CHECKS]
            tasks = [check_target(session, u) for u in chunk]
            
            # Run chunk concurrently
            results = await asyncio.gather(*tasks)
            
            # Filter None values
            alive_in_chunk = [r for r in results if r]
            valid_targets.extend(alive_in_chunk)
            
            # Progress Bar
            percent = round(((i + len(chunk)) / total) * 100, 1)
            sys.stdout.write(f"\r[STATUS] Progress: {percent}% | Checked: {i+len(chunk)}/{total} | Alive: {len(valid_targets)}")
            sys.stdout.flush()
            
            # Tiny sleep to let the event loop breathe
            await asyncio.sleep(0.1)
            
    print(f"\n[INFO] Validation Complete. Final Count: {len(valid_targets)}")
    return valid_targets

def generate_and_validate():
    """
    Main Orchestrator
    """
    print(f"[SYSTEM] DRISHTI-AX TARGET GENERATOR (God Mode)")
    print("=" * 60)
    
    final_dict = STATIC_TARGETS.copy()
    raw_candidates = []

    # 1. State x Department Permutations
    print("[1/3] Permuting State Departments...")
    for s in STATES:
        for d in DEPARTMENTS:
            raw_candidates.append(f"https://{d}.{s}.gov.in")
            raw_candidates.append(f"https://{d}.{s}.nic.in")

    # 2. District Permutations
    print("[2/3] Permuting District Portals...")
    for d in DISTRICTS:
        # Common patterns for district sites
        raw_candidates.append(f"https://{d}.nic.in")
        raw_candidates.append(f"https://{d}.gov.in")
        raw_candidates.append(f"https://{d}police.gov.in")
        raw_candidates.append(f"https://districts.ecourts.gov.in/{d}")

    # 3. Validate
    print("[3/3] Validating Candidates...")
    
    # Fix for Windows Event Loop - Use Selector for Network I/O
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    live_targets = asyncio.run(validate_targets_parallel(raw_candidates))
    
    # Categorize results
    final_dict["State_Dept_Verified"] = sorted([u for u in live_targets if any(x in u for x in DEPARTMENTS)])
    final_dict["District_Verified"] = sorted([u for u in live_targets if any(x in u for x in DISTRICTS) and u not in final_dict["State_Dept_Verified"]])
    
    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_dict, f, indent=2)
        
    print(f"\n[SUCCESS] Target List Saved to {OUTPUT_FILE}")
    print(f"         Total Targets Ready: {sum(len(v) for v in final_dict.values())}")

if __name__ == "__main__":
    try:
        generate_and_validate()
    except KeyboardInterrupt:
        print("\n[SYSTEM] Generation Aborted.")