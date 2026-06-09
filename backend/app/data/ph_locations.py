"""
Philippine geographic reference data: 17 regions, 82 provinces (+ NCR) and major
cities with coordinates. Used to seed the database and to drive live weather
fetching, province-level intelligence and map markers.

Coordinates are the provincial capital / centroid (WGS84, lat/lon).
Source attribution: PSGC region/province structure (PSA), public coordinates.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------
REGIONS = [
    {"code": "NCR", "name": "National Capital Region", "lat": 14.5995, "lon": 120.9842},
    {"code": "CAR", "name": "Cordillera Administrative Region", "lat": 17.0897, "lon": 120.9772},
    {"code": "R1", "name": "Ilocos Region", "lat": 16.6159, "lon": 120.3166},
    {"code": "R2", "name": "Cagayan Valley", "lat": 17.6131, "lon": 121.7269},
    {"code": "R3", "name": "Central Luzon", "lat": 15.0349, "lon": 120.6875},
    {"code": "R4A", "name": "CALABARZON", "lat": 14.1008, "lon": 121.0794},
    {"code": "R4B", "name": "MIMAROPA", "lat": 12.5778, "lon": 121.2695},
    {"code": "R5", "name": "Bicol Region", "lat": 13.1391, "lon": 123.7438},
    {"code": "R6", "name": "Western Visayas", "lat": 10.7202, "lon": 122.5621},
    {"code": "R7", "name": "Central Visayas", "lat": 10.3157, "lon": 123.8854},
    {"code": "R8", "name": "Eastern Visayas", "lat": 11.2440, "lon": 125.0030},
    {"code": "R9", "name": "Zamboanga Peninsula", "lat": 7.8257, "lon": 123.4370},
    {"code": "R10", "name": "Northern Mindanao", "lat": 8.4822, "lon": 124.6472},
    {"code": "R11", "name": "Davao Region", "lat": 7.1907, "lon": 125.4553},
    {"code": "R12", "name": "SOCCSKSARGEN", "lat": 6.5030, "lon": 124.8470},
    {"code": "R13", "name": "Caraga", "lat": 8.9475, "lon": 125.5406},
    {"code": "BARMM", "name": "Bangsamoro (BARMM)", "lat": 7.2236, "lon": 124.2464},
]

# ---------------------------------------------------------------------------
# Provinces  (name, region code, lat, lon, capital)
# ---------------------------------------------------------------------------
PROVINCES = [
    # NCR
    {"name": "Metro Manila", "region": "NCR", "lat": 14.5995, "lon": 120.9842, "capital": "Manila"},
    # CAR
    {"name": "Abra", "region": "CAR", "lat": 17.5951, "lon": 120.6178, "capital": "Bangued"},
    {"name": "Apayao", "region": "CAR", "lat": 18.0188, "lon": 121.1820, "capital": "Kabugao"},
    {"name": "Benguet", "region": "CAR", "lat": 16.4550, "lon": 120.5887, "capital": "La Trinidad"},
    {"name": "Ifugao", "region": "CAR", "lat": 16.8005, "lon": 121.1212, "capital": "Lagawe"},
    {"name": "Kalinga", "region": "CAR", "lat": 17.4189, "lon": 121.4443, "capital": "Tabuk"},
    {"name": "Mountain Province", "region": "CAR", "lat": 17.0897, "lon": 120.9772, "capital": "Bontoc"},
    # Region I
    {"name": "Ilocos Norte", "region": "R1", "lat": 18.1978, "lon": 120.5936, "capital": "Laoag"},
    {"name": "Ilocos Sur", "region": "R1", "lat": 17.5747, "lon": 120.3869, "capital": "Vigan"},
    {"name": "La Union", "region": "R1", "lat": 16.6159, "lon": 120.3166, "capital": "San Fernando"},
    {"name": "Pangasinan", "region": "R1", "lat": 16.0218, "lon": 120.2326, "capital": "Lingayen"},
    # Region II
    {"name": "Batanes", "region": "R2", "lat": 20.4487, "lon": 121.9702, "capital": "Basco"},
    {"name": "Cagayan", "region": "R2", "lat": 17.6131, "lon": 121.7269, "capital": "Tuguegarao"},
    {"name": "Isabela", "region": "R2", "lat": 17.1487, "lon": 121.8893, "capital": "Ilagan"},
    {"name": "Nueva Vizcaya", "region": "R2", "lat": 16.4824, "lon": 121.1490, "capital": "Bayombong"},
    {"name": "Quirino", "region": "R2", "lat": 16.5710, "lon": 121.5410, "capital": "Cabarroguis"},
    # Region III
    {"name": "Aurora", "region": "R3", "lat": 15.7589, "lon": 121.5623, "capital": "Baler"},
    {"name": "Bataan", "region": "R3", "lat": 14.6761, "lon": 120.5361, "capital": "Balanga"},
    {"name": "Bulacan", "region": "R3", "lat": 14.8433, "lon": 120.8114, "capital": "Malolos"},
    {"name": "Nueva Ecija", "region": "R3", "lat": 15.5414, "lon": 121.0857, "capital": "Palayan"},
    {"name": "Pampanga", "region": "R3", "lat": 15.0349, "lon": 120.6875, "capital": "San Fernando"},
    {"name": "Tarlac", "region": "R3", "lat": 15.4755, "lon": 120.5963, "capital": "Tarlac City"},
    {"name": "Zambales", "region": "R3", "lat": 15.3276, "lon": 119.9787, "capital": "Iba"},
    # Region IV-A
    {"name": "Batangas", "region": "R4A", "lat": 13.7565, "lon": 121.0583, "capital": "Batangas City"},
    {"name": "Cavite", "region": "R4A", "lat": 14.2811, "lon": 120.8669, "capital": "Trece Martires"},
    {"name": "Laguna", "region": "R4A", "lat": 14.2813, "lon": 121.4160, "capital": "Santa Cruz"},
    {"name": "Quezon", "region": "R4A", "lat": 13.9314, "lon": 121.6176, "capital": "Lucena"},
    {"name": "Rizal", "region": "R4A", "lat": 14.5878, "lon": 121.1759, "capital": "Antipolo"},
    # Region IV-B
    {"name": "Marinduque", "region": "R4B", "lat": 13.4470, "lon": 121.8400, "capital": "Boac"},
    {"name": "Occidental Mindoro", "region": "R4B", "lat": 13.2233, "lon": 120.5960, "capital": "Mamburao"},
    {"name": "Oriental Mindoro", "region": "R4B", "lat": 13.4117, "lon": 121.1803, "capital": "Calapan"},
    {"name": "Palawan", "region": "R4B", "lat": 9.7392, "lon": 118.7353, "capital": "Puerto Princesa"},
    {"name": "Romblon", "region": "R4B", "lat": 12.5778, "lon": 122.2695, "capital": "Romblon"},
    # Region V
    {"name": "Albay", "region": "R5", "lat": 13.1391, "lon": 123.7438, "capital": "Legazpi"},
    {"name": "Camarines Norte", "region": "R5", "lat": 14.1122, "lon": 122.9550, "capital": "Daet"},
    {"name": "Camarines Sur", "region": "R5", "lat": 13.5586, "lon": 123.2740, "capital": "Pili"},
    {"name": "Catanduanes", "region": "R5", "lat": 13.5836, "lon": 124.2348, "capital": "Virac"},
    {"name": "Masbate", "region": "R5", "lat": 12.3700, "lon": 123.6200, "capital": "Masbate City"},
    {"name": "Sorsogon", "region": "R5", "lat": 12.9742, "lon": 124.0058, "capital": "Sorsogon City"},
    # Region VI
    {"name": "Aklan", "region": "R6", "lat": 11.7000, "lon": 122.3667, "capital": "Kalibo"},
    {"name": "Antique", "region": "R6", "lat": 10.7400, "lon": 121.9400, "capital": "San Jose de Buenavista"},
    {"name": "Capiz", "region": "R6", "lat": 11.5853, "lon": 122.7511, "capital": "Roxas"},
    {"name": "Guimaras", "region": "R6", "lat": 10.5950, "lon": 122.5970, "capital": "Jordan"},
    {"name": "Iloilo", "region": "R6", "lat": 10.7202, "lon": 122.5621, "capital": "Iloilo City"},
    {"name": "Negros Occidental", "region": "R6", "lat": 10.6770, "lon": 122.9500, "capital": "Bacolod"},
    # Region VII
    {"name": "Bohol", "region": "R7", "lat": 9.6475, "lon": 123.8550, "capital": "Tagbilaran"},
    {"name": "Cebu", "region": "R7", "lat": 10.3157, "lon": 123.8854, "capital": "Cebu City"},
    {"name": "Negros Oriental", "region": "R7", "lat": 9.3103, "lon": 123.3080, "capital": "Dumaguete"},
    {"name": "Siquijor", "region": "R7", "lat": 9.2140, "lon": 123.5150, "capital": "Siquijor"},
    # Region VIII
    {"name": "Biliran", "region": "R8", "lat": 11.5630, "lon": 124.3970, "capital": "Naval"},
    {"name": "Eastern Samar", "region": "R8", "lat": 11.6080, "lon": 125.4320, "capital": "Borongan"},
    {"name": "Leyte", "region": "R8", "lat": 11.2440, "lon": 125.0030, "capital": "Tacloban"},
    {"name": "Northern Samar", "region": "R8", "lat": 12.4980, "lon": 124.6360, "capital": "Catarman"},
    {"name": "Samar", "region": "R8", "lat": 11.7750, "lon": 124.8860, "capital": "Catbalogan"},
    {"name": "Southern Leyte", "region": "R8", "lat": 10.1330, "lon": 124.8420, "capital": "Maasin"},
    # Region IX
    {"name": "Zamboanga del Norte", "region": "R9", "lat": 8.5890, "lon": 123.3410, "capital": "Dipolog"},
    {"name": "Zamboanga del Sur", "region": "R9", "lat": 7.8257, "lon": 123.4370, "capital": "Pagadian"},
    {"name": "Zamboanga Sibugay", "region": "R9", "lat": 7.7840, "lon": 122.5870, "capital": "Ipil"},
    # Region X
    {"name": "Bukidnon", "region": "R10", "lat": 8.1575, "lon": 125.1278, "capital": "Malaybalay"},
    {"name": "Camiguin", "region": "R10", "lat": 9.2510, "lon": 124.7150, "capital": "Mambajao"},
    {"name": "Lanao del Norte", "region": "R10", "lat": 8.0520, "lon": 124.0490, "capital": "Tubod"},
    {"name": "Misamis Occidental", "region": "R10", "lat": 8.4860, "lon": 123.8050, "capital": "Oroquieta"},
    {"name": "Misamis Oriental", "region": "R10", "lat": 8.4822, "lon": 124.6472, "capital": "Cagayan de Oro"},
    # Region XI
    {"name": "Davao de Oro", "region": "R11", "lat": 7.6010, "lon": 125.9650, "capital": "Nabunturan"},
    {"name": "Davao del Norte", "region": "R11", "lat": 7.4480, "lon": 125.8090, "capital": "Tagum"},
    {"name": "Davao del Sur", "region": "R11", "lat": 6.7497, "lon": 125.3570, "capital": "Digos"},
    {"name": "Davao Occidental", "region": "R11", "lat": 6.4090, "lon": 125.6120, "capital": "Malita"},
    {"name": "Davao Oriental", "region": "R11", "lat": 6.9550, "lon": 126.2160, "capital": "Mati"},
    # Region XII
    {"name": "Cotabato", "region": "R12", "lat": 7.0083, "lon": 125.0890, "capital": "Kidapawan"},
    {"name": "Sarangani", "region": "R12", "lat": 6.1030, "lon": 125.2890, "capital": "Alabel"},
    {"name": "South Cotabato", "region": "R12", "lat": 6.5030, "lon": 124.8470, "capital": "Koronadal"},
    {"name": "Sultan Kudarat", "region": "R12", "lat": 6.6290, "lon": 124.6050, "capital": "Isulan"},
    # Region XIII
    {"name": "Agusan del Norte", "region": "R13", "lat": 9.1230, "lon": 125.5340, "capital": "Cabadbaran"},
    {"name": "Agusan del Sur", "region": "R13", "lat": 8.6010, "lon": 125.9150, "capital": "Prosperidad"},
    {"name": "Dinagat Islands", "region": "R13", "lat": 10.0470, "lon": 125.5910, "capital": "San Jose"},
    {"name": "Surigao del Norte", "region": "R13", "lat": 9.7890, "lon": 125.4950, "capital": "Surigao City"},
    {"name": "Surigao del Sur", "region": "R13", "lat": 9.0780, "lon": 126.1980, "capital": "Tandag"},
    # BARMM
    {"name": "Basilan", "region": "BARMM", "lat": 6.6500, "lon": 122.1330, "capital": "Lamitan"},
    {"name": "Lanao del Sur", "region": "BARMM", "lat": 8.0000, "lon": 124.2930, "capital": "Marawi"},
    {"name": "Maguindanao del Norte", "region": "BARMM", "lat": 7.1500, "lon": 124.2500, "capital": "Datu Odin Sinsuat"},
    {"name": "Maguindanao del Sur", "region": "BARMM", "lat": 6.7220, "lon": 124.7920, "capital": "Buluan"},
    {"name": "Sulu", "region": "BARMM", "lat": 6.0530, "lon": 121.0020, "capital": "Jolo"},
    {"name": "Tawi-Tawi", "region": "BARMM", "lat": 5.0290, "lon": 119.7730, "capital": "Bongao"},
]

# ---------------------------------------------------------------------------
# Major cities / municipalities (for search + map markers)
# ---------------------------------------------------------------------------
CITIES = [
    {"name": "Manila", "province": "Metro Manila", "lat": 14.5995, "lon": 120.9842},
    {"name": "Quezon City", "province": "Metro Manila", "lat": 14.6760, "lon": 121.0437},
    {"name": "Makati", "province": "Metro Manila", "lat": 14.5547, "lon": 121.0244},
    {"name": "Taguig", "province": "Metro Manila", "lat": 14.5176, "lon": 121.0509},
    {"name": "Pasig", "province": "Metro Manila", "lat": 14.5764, "lon": 121.0851},
    {"name": "Caloocan", "province": "Metro Manila", "lat": 14.6510, "lon": 120.9720},
    {"name": "Baguio", "province": "Benguet", "lat": 16.4023, "lon": 120.5960},
    {"name": "Laoag", "province": "Ilocos Norte", "lat": 18.1978, "lon": 120.5936},
    {"name": "Vigan", "province": "Ilocos Sur", "lat": 17.5747, "lon": 120.3869},
    {"name": "Dagupan", "province": "Pangasinan", "lat": 16.0430, "lon": 120.3330},
    {"name": "San Fernando (La Union)", "province": "La Union", "lat": 16.6159, "lon": 120.3166},
    {"name": "Tuguegarao", "province": "Cagayan", "lat": 17.6131, "lon": 121.7269},
    {"name": "Angeles", "province": "Pampanga", "lat": 15.1450, "lon": 120.5930},
    {"name": "San Fernando (Pampanga)", "province": "Pampanga", "lat": 15.0349, "lon": 120.6875},
    {"name": "Olongapo", "province": "Zambales", "lat": 14.8290, "lon": 120.2820},
    {"name": "Cabanatuan", "province": "Nueva Ecija", "lat": 15.4860, "lon": 120.9720},
    {"name": "Malolos", "province": "Bulacan", "lat": 14.8433, "lon": 120.8114},
    {"name": "Antipolo", "province": "Rizal", "lat": 14.5878, "lon": 121.1759},
    {"name": "Batangas City", "province": "Batangas", "lat": 13.7565, "lon": 121.0583},
    {"name": "Lipa", "province": "Batangas", "lat": 13.9411, "lon": 121.1631},
    {"name": "Calamba", "province": "Laguna", "lat": 14.2118, "lon": 121.1653},
    {"name": "Lucena", "province": "Quezon", "lat": 13.9314, "lon": 121.6176},
    {"name": "Puerto Princesa", "province": "Palawan", "lat": 9.7392, "lon": 118.7353},
    {"name": "Calapan", "province": "Oriental Mindoro", "lat": 13.4117, "lon": 121.1803},
    {"name": "Legazpi", "province": "Albay", "lat": 13.1391, "lon": 123.7438},
    {"name": "Naga", "province": "Camarines Sur", "lat": 13.6218, "lon": 123.1948},
    {"name": "Sorsogon City", "province": "Sorsogon", "lat": 12.9742, "lon": 124.0058},
    {"name": "Iloilo City", "province": "Iloilo", "lat": 10.7202, "lon": 122.5621},
    {"name": "Bacolod", "province": "Negros Occidental", "lat": 10.6770, "lon": 122.9500},
    {"name": "Roxas", "province": "Capiz", "lat": 11.5853, "lon": 122.7511},
    {"name": "Kalibo", "province": "Aklan", "lat": 11.7000, "lon": 122.3667},
    {"name": "Cebu City", "province": "Cebu", "lat": 10.3157, "lon": 123.8854},
    {"name": "Mandaue", "province": "Cebu", "lat": 10.3236, "lon": 123.9220},
    {"name": "Lapu-Lapu", "province": "Cebu", "lat": 10.3103, "lon": 123.9494},
    {"name": "Tagbilaran", "province": "Bohol", "lat": 9.6475, "lon": 123.8550},
    {"name": "Dumaguete", "province": "Negros Oriental", "lat": 9.3103, "lon": 123.3080},
    {"name": "Tacloban", "province": "Leyte", "lat": 11.2440, "lon": 125.0030},
    {"name": "Ormoc", "province": "Leyte", "lat": 11.0060, "lon": 124.6075},
    {"name": "Calbayog", "province": "Samar", "lat": 12.0668, "lon": 124.5960},
    {"name": "Zamboanga City", "province": "Zamboanga del Sur", "lat": 6.9214, "lon": 122.0790},
    {"name": "Pagadian", "province": "Zamboanga del Sur", "lat": 7.8257, "lon": 123.4370},
    {"name": "Dipolog", "province": "Zamboanga del Norte", "lat": 8.5890, "lon": 123.3410},
    {"name": "Cagayan de Oro", "province": "Misamis Oriental", "lat": 8.4822, "lon": 124.6472},
    {"name": "Iligan", "province": "Lanao del Norte", "lat": 8.2280, "lon": 124.2452},
    {"name": "Malaybalay", "province": "Bukidnon", "lat": 8.1575, "lon": 125.1278},
    {"name": "Valencia", "province": "Bukidnon", "lat": 7.9060, "lon": 125.0940},
    {"name": "Davao City", "province": "Davao del Sur", "lat": 7.1907, "lon": 125.4553},
    {"name": "Tagum", "province": "Davao del Norte", "lat": 7.4480, "lon": 125.8090},
    {"name": "Digos", "province": "Davao del Sur", "lat": 6.7497, "lon": 125.3570},
    {"name": "General Santos", "province": "South Cotabato", "lat": 6.1164, "lon": 125.1716},
    {"name": "Koronadal", "province": "South Cotabato", "lat": 6.5030, "lon": 124.8470},
    {"name": "Kidapawan", "province": "Cotabato", "lat": 7.0083, "lon": 125.0890},
    {"name": "Cotabato City", "province": "Maguindanao del Norte", "lat": 7.2236, "lon": 124.2464},
    {"name": "Butuan", "province": "Agusan del Norte", "lat": 8.9475, "lon": 125.5406},
    {"name": "Surigao City", "province": "Surigao del Norte", "lat": 9.7890, "lon": 125.4950},
    {"name": "Marawi", "province": "Lanao del Sur", "lat": 8.0000, "lon": 124.2930},
    {"name": "Jolo", "province": "Sulu", "lat": 6.0530, "lon": 121.0020},
    {"name": "Bongao", "province": "Tawi-Tawi", "lat": 5.0290, "lon": 119.7730},
]

# Convenience lookups -------------------------------------------------------
REGION_BY_CODE = {r["code"]: r for r in REGIONS}
PROVINCE_BY_NAME = {p["name"]: p for p in PROVINCES}


def region_name(code: str) -> str:
    r = REGION_BY_CODE.get(code)
    return r["name"] if r else code


# National map default view
PH_CENTER = {"lat": 12.8797, "lon": 121.7740, "zoom": 6}
