"""Build the cleaned district-risk CSVs bundled in datasets/.

Sources (official, Government of India):

1. Fluoride and arsenic, DISTRICT level
   PIB, Ministry of Jal Shakti, "Contamination of Ground Water", Lok Sabha written reply, 24 Mar 2022,
   Annexure-I "States Wise Details of Partly Affected Districts with Fluoride and Arsenic Contaminants
   in Ground Water of India" (CGWB data).
   https://www.pib.gov.in/PressReleasePage.aspx?PRID=1809264
   Totals stated there: fluoride > 1.5 mg/L in parts of 370 districts (23 States/UTs),
   arsenic > 0.01 mg/L in parts of 152 districts (21 States/UTs).

2. Salinity, nitrate and iron, STATE level (number of partly affected districts)
   PIB, Ministry of Jal Shakti, "Contamination of Groundwater", Rajya Sabha written reply, 29 Nov 2021,
   Annexure-I (CGWB data).
   https://www.pib.gov.in/PressReleasePage.aspx?PRID=1776171

3. District centroids (for the map only)
   Polygon centroids computed from geohacker/india district GeoJSON (MIT licence)
   https://github.com/geohacker/india ; gaps filled from Goyal, Bhatia & Kumar (2024), "Assessing Temporal Dynamics of Nitrogen Surplus in Indian Agriculture",
   Zenodo, file district_centroids_lat_long.csv, CC BY 4.0. https://doi.org/10.5281/zenodo.12662782

The annexure text below is copied verbatim from the PIB page (typos included) and then cleaned:
spelling fixes, splitting of merged names, one row per (state, district).
Run:  python scripts/build_dataset.py
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "datasets"

SRC_FA = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1809264"
SRC_SNI = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1776171"
GEOJSON_URL = "https://raw.githubusercontent.com/geohacker/india/master/district/india_district.geojson"


def polygon_centroid(geom: dict) -> tuple[float, float]:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    a = cx = cy = 0.0
    for poly in polys:
        ring = poly[0]
        for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
            c = x0 * y1 - x1 * y0
            a += c
            cx += (x0 + x1) * c
            cy += (y0 + y1) * c
    if abs(a) < 1e-12:
        ring = polys[0][0]
        return sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring)
    return cy / (3 * a), cx / (3 * a)

# (state, fluoride districts, arsenic districts) - verbatim from PRID=1809264 Annexure-I
ANNEXURE_FA = [
    ("Andhra Pradesh",
     "Visakhapatnam, West-Godavari, Krishna, Guntur, Prakasam, Nellore, Chittoor Kadapa, Kurnool, Ananthapur, "
     "Sirkakulam, Vizianagaram",
     "Guntur, Kurnool, Nellore"),
    ("Telangana",
     "Adilabad, Karimnagar, Khammam, Warangal, Mahabubnagar, Medak, Nalgonda, Rangareddy, Nizamabad, Hyderabad",
     "Nalgonda,"),
    ("Assam",
     "Goalpara, Kamrup, KarbiAnglong, Naugaon, Golaghat, Karimganj, Bangiagaon, Sibasagar, Jorhat",
     "Sivsagar, Jorhat, Golaghat, Sonitpur, Lakhimpur, Dhemaji, Hailakandi, Karimganj, Cachar, Barpeta, Bongaigaon, "
     "Goalpara, Dhubri, Nalbari, Nagaon, Morigaon, Kamrup, Darrang&Baksha"),
    ("Bihar",
     "Aurangabad, Banka, Bhagalpur, Gaya, Jamui, Kaimur( Bhabua), Munger, Nawada, Rohtas, Jahanabd, Lakhisarai, "
     "Sheikhpura, Nalanda",
     "Begusarai, Bhagalpur, Bhojpur, Buxar, Darbhanga, Katihar, Khagaria, Kishanganj, Lakhisarai, Munger, Patna, "
     "Purnea, Samastipur, Saran, Vaishali E.Champaran, Gopalganj, Madhepura, Muzaffarpur, Saharsa, Siwan, W Champaran"),
    ("Chhattisgarh",
     "Bastar, Balod ,Balrampur, Bemetra, Bijapur , Durg, Kanker, Kondagaon , Korba, Koriya , Raigarh, Surajpur , "
     "Surguja, Jashpur, Dhamtari, Mahasamund, Rajnandgaon, Bilaspur, Raipur",
     "Rajnandgon"),
    ("Delhi",
     "East Delhi, New Delhi, North West Delhi, South Delhi, South West Delhi, North Delhi, West Delhi",
     "East, North east"),
    ("Gujarat",
     "Ahmedabad, Amreli, Anand, Banaskantha, Bharuch, Bhavnagar, Dahod, Gandhinagar, Jamnagar, Junagadh, Kachchh, "
     "Mehesana, Panchmahals, Patan, Porbandar, Rajkot, Sabarkantha, Surendranagar, Vadodara, Kheda, Navsari, Surat",
     "Amreli, Anand, Bharuch, Bhavnagar, Dahod, Gandhinagar, Kachchh, Mehesana,Patan, Rajkot, Surendranagar, Vadodara"),
    ("Haryana",
     "Ambali, Bhiwani, Fatehabad, Faridabad, Gurgaon, Hissar, Jhajjar, Jind, Kaithal, Karnal, Kurukshetra, "
     "Mahendergarh, Panchkula, Palwal,Panipat, Rewari, Rohtak, Sirsa, Sonepat, Yamuna Nagar, Mewat",
     "Ambala, Bhiwani, Faridabad, Fatehabad, Hissar, Jhajjar, Jind, Karnal, Panipat, Rohtak, Sirsa, Sonepat, "
     "Yamunanagar, Mahendergarh, Palwal"),
    ("Himachal Pradesh", "", "Kangra"),
    ("Jammu & Kashmir", "Jammu, Kathua", "Jammu, Kathua, Rajouri"),
    ("Jharkhand",
     "Bokaro, Dhanbad, Garhwa,Giridih, Godda, Gumla, Koderma, Pakur, Palamu, Ranchi, , Sahebganj, Khunti",
     "Sahebganj, Lohardaga"),
    ("Karnataka",
     "Bagalkot, Bangalore-Rural, Bangalore-Urban, Belgaum, Bellary, Bidar, Bijapur, Chikaballapur Chamarajanagar, "
     "Chikmagalur, Chitradurga, Davanagere, Dharwad, Dakshina Kannada, Gadag, Gulburga, Hassan, Haveri, Kolar, Koppal, "
     "Mandya, Mysore, Raichur, Ramnagara , Shimoga, Tumkur, Yadgir, Uttara Kannada, Udupi, Kodagu",
     "Raichur andYadgir district"),
    ("Kerala", "Palakkad, Alappuzha, Idukki, Ernakulum, Thiruvananthpuram", ""),
    ("Madhya Pradesh",
     "Alirajpur, Balaghat, Barwani, Betul, Bhind, Bhopal,Chhatarpur, Chhindwara, Datia, Dewas, Dhar, Dindori, Guna, "
     "Gwalior, Harda, Jabalpur, Jhabua, Khargon, Mandla, Mandsaur, Morena, Narsinhpur, Neemuch, Panna, Raisen, Rajgarh, "
     "Ratlam, Sagar, Satna, Sehore, Seoni, Shahdol, Shajapur, Sheopur, Sidhi, Shivpuri, Singrauli, Uajjain, Vidisha, "
     "Anuppur, Indore, Khandwa, Tikkamgarh",
     "Betul,Burhanpur, Chhindwara , Dhar, Khandwa, Mandsaur, Neemuch, Umaria"),
    ("Maharashtra",
     "Ahmednagar, Beed, Chandrapur, Bhandara, Dhule, Gadchiroli, Gondia, Jalna, Nagpur, Nanded, Ratnagiri, Sangli, "
     "Satara, Sindhudurg, Solapur, Wardha,Yavatmal",
     ""),
    ("Manipur", "Thoubal", "Bishnupur, Thoubal"),
    ("Meghalaya", "Ri Bhoi", ""),
    ("Nagaland", "Dimapur", ""),
    ("Odisha",
     "Angul, Balasore, Bhadrak, Bargarh Bolangir, Boudh, Cuttack, Deogarh Dhenkanal, Jajpur, Kandhamal ,Keonjhar, "
     "Khurda, Mayurbhanj, Nayagarh, Nuapada, Ganjam, Jagatsinghpur, Kalahandi, Koraput, Puri, Rayagada, Sambalpur, "
     "Sonepur, Sundargarh, Gajapati",
     "Gajapati"),
    ("Punjab",
     "Amritsar, Barnala, Bhatinda, Fazilka, Faridkot, Fatehgarh Sahib, Firozpur, Gurdaspur, Jalandhar, Ludhiana, Mansa, "
     "Moga, Muktsar, Pathankot, Patiala, Ropar, Sangrur, SAS Nagar (Mohali), Tarn-Taran",
     "Mansa, Amritsar, Gurdaspur, Hoshiarpur, Kapurthala, Ropar, Faridkot, Nawashahar, Sangrur, TaranTaran"),
    ("Rajasthan",
     "Ajmer, Alwar, Banswara, Barmer, Bharatpur, Baran, Bhilwara, Bikaner, Bundi, Chittaurgarh, Churu, Dausa, Dhaulpur, "
     "Dungarpur, Ganganagar, Hanumangarh, Jaipur, Jaisalmer, Jalore, Jhalawar Jhunjhunu, Jodhpur, Karauli, Kota, Nagaur, "
     "Pali, Pratapgarh, Rajsamand, Sirohi, Sikar, Sawai Madhopur, Tonk, Udaipur",
     "Ganganagar"),
    ("Tamil Nadu",
     "Coimbatore, Dharmapuri, Dindigul, Erode, Karur, Kancheepuram, Krishnagiri, Namakkal, Madurai, Puddukotai, "
     "Ramanathanpuram, Salem, Sivagangai, Theni, Thiruvannamalai, Tiruchirapally, Thirunelveli, Tirupur Vellore,"
     "Cuddalore, Perambalur, Thanjavur, Thiruvarur, Tuticorin, Virudhunagar",
     "Ariyalur Cuddalore, Nagapattinam, Ramnathapuram,Tiruvallur, Tirunelveli, Thiruvarur, Trichchirappalli, Tuticorin"),
    ("Uttar Pradesh",
     "Agra, Aligarh, Allahabad ,Auraiya, Banda ,Bulandshahar ,Etah,Etawah,, Farrukhabad, Fatehpur, , Firozabad, "
     "G B Nagar, Ghaziabad, Hathras,Jaunpur, Kannauj , Kanpur Nagar, Kasganj (Kashiram Nagar), Lalitpur, Mahoba, "
     "Mainpuri, Mathura, MaunathBhanjan,Pratapgarh, Rai Bareli, Shajahanpur, Sonbhadra, Sultanpur, Varanasi and Unnao,"
     "Chandauli, Gonda, Hardoi, Sitapur",
     "Bahraich, Balia, Balrampur, Bareilly, Basti, Bijnor, Chandauli, Ghazipur, Gonda, Gorakhpur, LakhimpurKheri, "
     "Meerut, Mirzapur, Muradabad, Rai Bareilly, SantKabir Nagar, Shajahanpur, Siddarthnagar, SantRavidasNagar, Unnao, "
     "Azamgarh,Badaun, Deoria, Jhansi, Kausambi, Kushinagar, Pilibhit, MaunathBhanjan"),
    ("West Bengal",
     "Bankura, Birbhum, Dakshindinajpur, Malda, Purulia, Uttardinajpur, South 24 Praganas, Nadia",
     "Bardhaman, Hooghly, Howrah, Malda, Murshidabad, Nadia, N-24 Parganas, S- 24 Parganas, Coochbehar"),
    ("Daman & Diu", "", "Diu"),
]

# Names where the annexure is missing a comma between two districts (line breaks in the PDF table).
SPLITS = {
    "Chittoor Kadapa": ["Chittoor", "Kadapa"],
    "Vaishali E.Champaran": ["Vaishali", "East Champaran"],
    "Chikaballapur Chamarajanagar": ["Chikkaballapur", "Chamarajanagar"],
    "Bargarh Bolangir": ["Bargarh", "Bolangir"],
    "Deogarh Dhenkanal": ["Deogarh", "Dhenkanal"],
    "Jhalawar Jhunjhunu": ["Jhalawar", "Jhunjhunu"],
    "Tirupur Vellore": ["Tiruppur", "Vellore"],
    "Ariyalur Cuddalore": ["Ariyalur", "Cuddalore"],
    "Darrang&Baksha": ["Darrang", "Baksa"],
    "Raichur andYadgir district": ["Raichur", "Yadgir"],
    "Varanasi and Unnao": ["Varanasi", "Unnao"],
}

# Spelling / naming fixes -> commonly used district name. Old names kept as aliases at lookup time.
FIXES = {
    "West-Godavari": "West Godavari", "Ananthapur": "Anantapur", "Sirkakulam": "Srikakulam", "Nellore": "Nellore",
    "KarbiAnglong": "Karbi Anglong", "Naugaon": "Nagaon", "Bangiagaon": "Bongaigaon", "Sibasagar": "Sivasagar",
    "Sivsagar": "Sivasagar", "Kaimur( Bhabua)": "Kaimur", "Jahanabd": "Jehanabad", "Purnea": "Purnia",
    "W Champaran": "West Champaran", "Bemetra": "Bemetara", "Kanker": "Kanker", "Rajnandgon": "Rajnandgaon",
    "Koriya": "Korea", "East": "East Delhi", "North east": "North East Delhi", "Kachchh": "Kachchh",
    "Mehesana": "Mehsana", "Panchmahals": "Panchmahal", "Ambali": "Ambala", "Gurgaon": "Gurugram", "Hissar": "Hisar",
    "Mahendergarh": "Mahendragarh", "Sonepat": "Sonipat", "Yamunanagar": "Yamuna Nagar", "Mewat": "Nuh",
    "Sahebganj": "Sahibganj", "Bangalore-Rural": "Bengaluru Rural", "Bangalore-Urban": "Bengaluru Urban",
    "Belgaum": "Belagavi", "Bellary": "Ballari", "Chikmagalur": "Chikkamagaluru",
    "Gulburga": "Kalaburagi", "Mysore": "Mysuru", "Ramnagara": "Ramanagara", "Shimoga": "Shivamogga",
    "Tumkur": "Tumakuru", "Ernakulum": "Ernakulam", "Thiruvananthpuram": "Thiruvananthapuram",
    "Khargon": "Khargone", "Narsinhpur": "Narsinghpur", "Uajjain": "Ujjain", "Tikkamgarh": "Tikamgarh",
    "Ahmednagar": "Ahmednagar", "Beed": "Beed", "Gondia": "Gondia", "Balasore": "Balasore", "Bolangir": "Balangir",
    "Boudh": "Boudh", "Khurda": "Khordha", "Sonepur": "Subarnapur", "Bhatinda": "Bathinda", "Firozpur": "Ferozepur",
    "Muktsar": "Sri Muktsar Sahib", "Ropar": "Rupnagar", "SAS Nagar (Mohali)": "SAS Nagar", "Tarn-Taran": "Tarn Taran",
    "TaranTaran": "Tarn Taran", "Nawashahar": "Shaheed Bhagat Singh Nagar", "Chittaurgarh": "Chittorgarh",
    "Dhaulpur": "Dholpur", "Ganganagar": "Sri Ganganagar", "Jalore": "Jalor", "Kancheepuram": "Kanchipuram",
    "Puddukotai": "Pudukkottai", "Ramanathanpuram": "Ramanathapuram", "Ramnathapuram": "Ramanathapuram",
    "Sivagangai": "Sivaganga", "Thiruvannamalai": "Tiruvannamalai", "Tiruchirapally": "Tiruchirappalli",
    "Trichchirappalli": "Tiruchirappalli", "Thirunelveli": "Tirunelveli", "Thiruvarur": "Tiruvarur",
    "Tuticorin": "Thoothukudi", "Allahabad": "Prayagraj", "Bulandshahar": "Bulandshahr", "Buland Shahar": "Bulandshahr",
    "G B Nagar": "Gautam Buddha Nagar", "Kasganj (Kashiram Nagar)": "Kasganj", "MaunathBhanjan": "Mau",
    "Rai Bareli": "Rae Bareli", "Rai Bareilly": "Rae Bareli", "Shajahanpur": "Shahjahanpur", "Balia": "Ballia",
    "LakhimpurKheri": "Lakhimpur Kheri", "Muradabad": "Moradabad", "SantKabir Nagar": "Sant Kabir Nagar",
    "Siddarthnagar": "Siddharthnagar", "SantRavidasNagar": "Bhadohi", "Badaun": "Budaun", "Kausambi": "Kaushambi",
    "Dakshindinajpur": "Dakshin Dinajpur", "Uttardinajpur": "Uttar Dinajpur", "South 24 Praganas": "South 24 Parganas",
    "S- 24 Parganas": "South 24 Parganas", "N-24 Parganas": "North 24 Parganas", "Bardhaman": "Purba Bardhaman",
    "Coochbehar": "Cooch Behar", "Ri Bhoi": "Ri-Bhoi", "Kodagu": "Kodagu",
}

# Old/alternate names users may type -> canonical (lookup only; written to datasets/district_aliases.csv)
ALIASES = {
    "Allahabad": "Prayagraj", "Gurgaon": "Gurugram", "Mewat": "Nuh", "Mysore": "Mysuru", "Belgaum": "Belagavi",
    "Bellary": "Ballari", "Gulbarga": "Kalaburagi", "Gulburga": "Kalaburagi", "Shimoga": "Shivamogga",
    "Tumkur": "Tumakuru", "Bijapur Karnataka": "Vijayapura", "Bangalore": "Bengaluru Urban",
    "Bangalore Urban": "Bengaluru Urban", "Bangalore Rural": "Bengaluru Rural", "Chikmagalur": "Chikkamagaluru",
    "Hissar": "Hisar", "Sonepat": "Sonipat", "Mahendergarh": "Mahendragarh", "Bhatinda": "Bathinda",
    "Firozpur": "Ferozepur", "Mohali": "SAS Nagar", "Ropar": "Rupnagar", "Muktsar": "Sri Muktsar Sahib",
    "Nawanshahr": "Shaheed Bhagat Singh Nagar", "Nawashahar": "Shaheed Bhagat Singh Nagar", "Noida": "Gautam Buddha Nagar",
    "Greater Noida": "Gautam Buddha Nagar", "Raebareli": "Rae Bareli", "Rai Bareli": "Rae Bareli",
    "Sant Ravidas Nagar": "Bhadohi", "Mau Nath Bhanjan": "Mau", "Badaun": "Budaun", "Kausambi": "Kaushambi",
    "Purnea": "Purnia", "Jahanabad": "Jehanabad", "Motihari": "East Champaran", "Purbi Champaran": "East Champaran",
    "Bettiah": "West Champaran", "Pashchim Champaran": "West Champaran", "Bhabua": "Kaimur",
    "Tuticorin": "Thoothukudi", "Trichy": "Tiruchirappalli", "Tiruchi": "Tiruchirappalli",
    "Kanchipuram": "Kanchipuram", "Kancheepuram": "Kanchipuram", "Tirupur": "Tiruppur", "Calcutta": "Kolkata",
    "Burdwan": "Purba Bardhaman", "Bardhaman": "Purba Bardhaman", "Koch Bihar": "Cooch Behar",
    "Mehesana": "Mehsana", "Kutch": "Kachchh", "Kachh": "Kachchh", "Panchmahals": "Panchmahal",
    "Baroda": "Vadodara", "Khurda": "Khordha", "Bolangir": "Balangir", "Sonepur": "Subarnapur",
    "Baleswar": "Balasore", "Anugul": "Angul", "Ernakulum": "Ernakulam",
    "Trivandrum": "Thiruvananthapuram", "Palghat": "Palakkad", "Alleppey": "Alappuzha", "Khargon": "Khargone",
    "West Nimar": "Khargone", "East Nimar": "Khandwa", "Narsimhapur": "Narsinghpur", "Tikamgarh": "Tikamgarh",
    "Ahmadnagar": "Ahmednagar", "Ahilyanagar": "Ahmednagar", "Bid": "Beed", "Gondiya": "Gondia",
    "Sibsagar": "Sivasagar", "Nowgong": "Nagaon", "Kamrup Metro": "Kamrup", "Kamrup Metropolitan": "Kamrup",
    "Sahebganj": "Sahibganj", "Palamau": "Palamu", "Korea": "Korea", "Koriya": "Korea", "Kanker": "Kanker",
    "Uttar Bastar Kanker": "Kanker", "Dholpur": "Dholpur", "Dhaulpur": "Dholpur", "Ganganagar": "Sri Ganganagar",
    "Chittaurgarh": "Chittorgarh", "Jalore": "Jalor", "Ananthapur": "Anantapur", "Anantapuramu": "Anantapur",
    "Cuddapah": "Kadapa", "YSR Kadapa": "Kadapa", "Vizag": "Visakhapatnam", "Nellore": "Nellore",
    "Sri Potti Sriramulu Nellore": "Nellore", "Ranga Reddy": "Rangareddy", "Mahbubnagar": "Mahabubnagar",
    "Ri Bhoi": "Ri-Bhoi", "Kendujhar": "Keonjhar", "Chamrajnagar": "Chamarajanagar",
    "Chamarajnagar": "Chamarajanagar", "Thiruvallur": "Tiruvallur", "Chikballapur": "Chikkaballapur",
    "Chikkaballapura": "Chikkaballapur", "Prayag Raj": "Prayagraj", "Gautam Budh Nagar": "Gautam Buddha Nagar",
    "Bemetra": "Bemetara",
}

# Centroid file uses older spellings; map them to our canonical names where they differ.
CENTROID_STATE_FIX = {"Arunanchal Pradesh": "Arunachal Pradesh", "Orissa": "Odisha", "NCT of Delhi": "Delhi",
                      "Andaman & Nicobar Island": "Andaman & Nicobar Islands",
                      "Dadara & Nagar Havelli": "Dadra & Nagar Haveli", "Andaman and Nicobar": "Andaman & Nicobar Islands",
                      "Dadra and Nagar Haveli": "Dadra & Nagar Haveli", "Daman and Diu": "Daman & Diu",
                      "Jammu and Kashmir": "Jammu & Kashmir", "Uttaranchal": "Uttarakhand"}
# 2011-era boundaries list these under Andhra Pradesh; they are in Telangana since 2014.
TELANGANA_2011 = {"adilabad", "hyderabad", "karimnagar", "khammam", "mahabubnagar", "medak", "nalgonda",
                  "nizamabad", "rangareddy", "warangal"}

# STATE-level counts of partly affected districts - verbatim numbers from PRID=1776171 Annexure-I
# (state, salinity EC>3000 uS/cm, nitrate >45 mg/L, iron >1 mg/L); blank = none reported
ANNEXURE_SNI = [
    ("Andhra Pradesh", 12, 13, 7), ("Telangana", 8, 10, 8), ("Assam", None, None, 18),
    ("Arunachal Pradesh", None, None, 4), ("Bihar", None, 10, 19), ("Chhattisgarh", 1, 12, 17),
    ("Delhi", 7, 8, None), ("Goa", None, None, 2), ("Gujarat", 21, 24, 10), ("Haryana", 18, 21, 17),
    ("Himachal Pradesh", None, 6, None), ("Jammu & Kashmir", None, 6, 9), ("Jharkhand", None, 11, 6),
    ("Karnataka", 29, 29, 22), ("Kerala", 4, 11, 14), ("Madhya Pradesh", 18, 51, 41), ("Maharashtra", 25, 30, 20),
    ("Manipur", None, None, 4), ("Meghalaya", None, None, 6), ("Nagaland", None, None, 1), ("Odisha", 17, 28, 30),
    ("Punjab", 10, 21, 9), ("Rajasthan", 30, 33, 33), ("Tamil Nadu", 27, 29, 2), ("Tripura", None, None, 4),
    ("Uttar Pradesh", 13, 59, 15), ("Uttarakhand", None, 4, 5), ("West Bengal", 6, 5, 16),
    ("Andaman & Nicobar Islands", 1, None, 2), ("Daman & Diu", 1, 1, None), ("Puducherry", None, 1, None),
]


STATE_FIXES = {("Karnataka", "Bijapur"): "Vijayapura"}  # Bijapur in Chhattisgarh keeps its name


def split_names(raw: str, state: str = "") -> list[str]:
    out: list[str] = []
    for part in re.split(r",", raw):
        name = re.sub(r"\s+", " ", part).strip(" .")
        if not name:
            continue
        for n in SPLITS.get(name, [name]):
            n = STATE_FIXES.get((state, n), FIXES.get(n, n))
            if n and n not in out:
                out.append(n)
    return out


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rows: dict[tuple[str, str], dict] = {}
    for state, fl, ars in ANNEXURE_FA:
        for d in split_names(fl, state):
            rows.setdefault((state, d), {"state": state, "district": d, "fluoride": 0, "arsenic": 0})["fluoride"] = 1
        for d in split_names(ars, state):
            rows.setdefault((state, d), {"state": state, "district": d, "fluoride": 0, "arsenic": 0})["arsenic"] = 1
    data = sorted(rows.values(), key=lambda r: (r["state"], r["district"]))
    with open(OUT / "district_risks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["state", "district", "fluoride", "arsenic", "source"])
        w.writeheader()
        for r in data:
            w.writerow({**r, "source": SRC_FA})
    nf = sum(r["fluoride"] for r in data)
    na = sum(r["arsenic"] for r in data)

    with open(OUT / "state_risks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "salinity_districts", "nitrate_districts", "iron_districts", "source"])
        for st, s, n, i in ANNEXURE_SNI:
            w.writerow([st, s or 0, n or 0, i or 0, SRC_SNI])

    with open(OUT / "district_aliases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["alias", "district"])
        for a, d in sorted(ALIASES.items()):
            if norm(a) != norm(d):
                w.writerow([a, d])

    # centroids (map only): polygon centroids from geohacker/india (MIT), then Zenodo CC BY 4.0 points
    cents: dict[str, tuple] = {}
    geo = Path(os.environ.get("DISTRICT_GEOJSON", "/tmp/india_district.geojson"))
    if not geo.exists():
        import urllib.request
        urllib.request.urlretrieve(GEOJSON_URL, geo)
    for feat in json.load(open(geo, encoding="utf-8"))["features"]:
        p, g = feat["properties"], feat.get("geometry")
        if not g:
            continue
        st = CENTROID_STATE_FIX.get(p["NAME_1"], p["NAME_1"])
        d = p["NAME_2"]
        d = FIXES.get(d, ALIASES.get(d, d))
        if st == "Andhra Pradesh" and norm(d) in TELANGANA_2011:
            st = "Telangana"
        lat, lng = polygon_centroid(g)
        cents.setdefault(norm(st) + "|" + norm(d), (st, d, round(lat, 4), round(lng, 4), "geohacker/india (MIT)"))
    with open(OUT / "raw_district_centroids_zenodo.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            st = CENTROID_STATE_FIX.get(r["State Name"].strip(), r["State Name"].strip())
            d = r["Dist Name"].strip()
            d = FIXES.get(d, ALIASES.get(d, d))
            cents.setdefault(norm(st) + "|" + norm(d), (st, d, round(float(r["latitude"]), 4),
                                                        round(float(r["longitude"]), 4), "Zenodo 12662782 (CC BY 4.0)"))
    with open(OUT / "district_centroids.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "district", "lat", "lng", "source"])
        w.writerows(sorted(cents.values()))
    names = {k.split("|")[1] for k in cents}
    matched = sum(1 for r in data if norm(r["district"]) in names)
    print(f"district_risks.csv: {len(data)} districts (fluoride {nf}, arsenic {na}); "
          f"{matched} have a centroid; state_risks.csv: {len(ANNEXURE_SNI)} states; centroids: {len(cents)}")


if __name__ == "__main__":
    main()
