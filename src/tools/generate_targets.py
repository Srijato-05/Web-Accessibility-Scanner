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
CONCURRENT_CHECKS = 100  # High concurrency for speed
TIMEOUT_SECONDS = 4      # Fast fail to churn through dead links
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

# ==========================================
#        DATASET: THE "TITAN" SEEDS
# ==========================================
STATIC_TARGETS = {
    "Central_Digital_Backbone": [
        "https://www.india.gov.in", "https://www.mygov.in", "https://www.digitalindia.gov.in",
        "https://uidai.gov.in", "https://myaadhaar.uidai.gov.in", "https://www.digilocker.gov.in",
        "https://umang.gov.in", "https://www.nic.in", "https://gem.gov.in", "https://mkisan.gov.in",
        "https://enam.gov.in", "https://csc.gov.in", "https://meity.gov.in", "https://mha.gov.in",
        "https://mea.gov.in", "https://finmin.nic.in", "https://mod.gov.in", "https://morth.gov.in",
        "https://mohua.gov.in", "https://tribal.nic.in", "https://socialjustice.gov.in",
        "https://labour.gov.in", "https://powermin.gov.in", "https://mnre.gov.in", "https://pngrb.gov.in",
        "https://commerce.gov.in", "https://dpiit.gov.in", "https://msme.gov.in", "https://corporate.gov.in",
        "https://coal.gov.in", "https://jalshakti-dowr.gov.in", "https://education.gov.in", "https://niti.gov.in"
    ],
    "Finance_Banking_Critical": [
        "https://rbi.org.in", "https://sebi.gov.in", "https://irdai.gov.in", "https://pfrda.org.in",
        "https://incometax.gov.in", "https://gst.gov.in", "https://onlinesbi.sbi", "https://sbi.co.in",
        "https://pnbindia.in", "https://bankofbaroda.in", "https://canarabank.com", "https://unionbankofindia.co.in",
        "https://bankofindia.co.in", "https://indianbank.in", "https://centralbankofindia.co.in", "https://iob.in",
        "https://ucobank.com", "https://bankofmaharashtra.in", "https://psbindia.com", "https://hdfcbank.com",
        "https://icicibank.com", "https://axisbank.com", "https://kotak.com", "https://indusind.com",
        "https://yesbank.in", "https://idfcfirstbank.com", "https://bandhanbank.com", "https://licindia.in",
        "https://newindia.co.in", "https://unitedinsurance.in", "https://orientalinsurance.org.in",
        "https://npci.org.in", "https://bhimupi.org.in", "https://rupay.co.in", "https://sidbi.in", "https://nabard.org"
    ],
    "Transport_Logistics": [
        "https://irctc.co.in", "https://indianrail.gov.in", "https://indianrailways.gov.in",
        "https://parivahan.gov.in", "https://sarathi.parivahan.gov.in", "https://fastag.ihmcl.com",
        "https://nhai.gov.in", "https://civilaviation.gov.in", "https://dgca.gov.in", "https://airindia.com",
        "https://indigo.in", "https://spicejet.com", "https://aai.aero", "https://newdelhiairport.in",
        "https://csmia.adaniairports.com", "https://bengaluruairport.com", "https://hyderabad.aero",
        "https://delhimetrorail.com", "https://english.bmrc.co.in", "https://ltmetro.com", "https://cmrl.in",
        "https://kmrl.co.in", "https://mmrda.maharashtra.gov.in", "https://mahametro.org", "https://lmrcl.com",
        "https://nmrcnoida.com", "https://upsrtc.com", "https://msrtc.gov.in", "https://ksrtc.in",
        "https://apsrtconline.in", "https://tsrtconline.in", "https://gsrtc.in", "https://rsrtconline.rajasthan.gov.in"
    ]
}

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
#        INTELLIGENT VALIDATION ENGINE
# ==========================================

async def check_target(session, url):
    """
    Pings a URL to see if it is alive. 
    Returns the URL if 200 OK or 403 Forbidden (Valid but blocked).
    """
    try:
        # HEAD request is faster, but some servers block it. 
        # If HEAD fails with 405, we try GET.
        async with session.head(url, timeout=TIMEOUT_SECONDS, allow_redirects=True) as resp:
            if resp.status < 400:
                print(f"[ALIVE] {url}")
                return url
            elif resp.status in [403, 406]:
                print(f"[WAF] {url} (Protected)")
                return url
            elif resp.status == 405: # Method Not Allowed, try GET
                async with session.get(url, timeout=TIMEOUT_SECONDS) as resp_get:
                    if resp_get.status < 400:
                        print(f"[ALIVE] {url}")
                        return url
    except:
        pass # Dead link, ignore
    return None

async def validate_targets_parallel(raw_targets):
    """
    Orchestrates the massive parallel validation.
    """
    valid_targets = []
    # Deduplicate first
    unique_targets = list(set(raw_targets))
    print(f"[INFO] Unique candidates to validate: {len(unique_targets)}")
    
    async with aiohttp.ClientSession(headers={"User-Agent": random.choice(USER_AGENTS)}) as session:
        # Process in chunks to avoid blowing up the OS socket limit
        chunk_size = CONCURRENT_CHECKS
        for i in range(0, len(unique_targets), chunk_size):
            chunk = unique_targets[i:i+chunk_size]
            tasks = [check_target(session, url) for url in chunk]
            results = await asyncio.gather(*tasks)
            
            # Filter None
            alive = [r for r in results if r]
            valid_targets.extend(alive)
            
            # Progress Bar
            sys.stdout.write(f"\r[STATUS] Validated: {len(valid_targets)} / Scanned: {i+len(chunk)}")
            sys.stdout.flush()
            
    print("\n")
    return valid_targets

def generate_and_validate():
    final_list = STATIC_TARGETS.copy()
    
    # 1. PERMUTATION: State Departments (~1,000 URLs)
    print("[GEN] Generating State Department Candidates...")
    state_candidates = []
    for state in STATES:
        for dept in DEPARTMENTS:
            state_candidates.append(f"https://{dept}.{state}.gov.in")
            state_candidates.append(f"https://{state}{dept}.gov.in")

    # 2. PERMUTATION: District Portals & Services (~3,000 URLs)
    print("[GEN] Generating District Portal Candidates...")
    district_candidates = []
    for dist in DISTRICTS:
        # Standard NIC format (most common)
        district_candidates.append(f"https://{dist}.nic.in")
        district_candidates.append(f"https://{dist}.gov.in")
        # Police & Court subdomains
        district_candidates.append(f"https://{dist}police.gov.in")
        district_candidates.append(f"https://districts.ecourts.gov.in/{dist}")

    # 3. COMBINE ALL DYNAMIC CANDIDATES
    all_dynamic = state_candidates + district_candidates
    
    # 4. EXECUTE INTELLIGENT VALIDATION
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    print("-" * 50)
    print(f"[START] Beginning Concurrent Network Scan of {len(all_dynamic)} targets...")
    live_dynamic = asyncio.run(validate_targets_parallel(all_dynamic))
    
    # 5. RE-CATEGORIZE & SAVE
    final_list["State_Departments_Verified"] = [u for u in live_dynamic if u in state_candidates]
    final_list["District_Services_Verified"] = [u for u in live_dynamic if u in district_candidates]
    
    # Calculate Totals
    total_static = sum(len(v) for k,v in STATIC_TARGETS.items())
    total_verified = len(live_dynamic)
    grand_total = total_static + total_verified
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_list, f, indent=2)
    
    print("-" * 50)
    print(f"[SUCCESS] Generation Complete.")
    print(f"[STATS] Seed Targets: {total_static}")
    print(f"[STATS] Candidates Scanned: {len(all_dynamic)}")
    print(f"[STATS] Validated Live: {total_verified}")
    print(f"[RESULT] Final Target Database: {grand_total} URLs")
    print(f"[OUTPUT] Saved to '{OUTPUT_FILE}'")
    print("-" * 50)

if __name__ == "__main__":
    generate_and_validate()