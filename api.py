from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import math
import csv
import urllib.request
import json

# ---------------------------------------------------------------------------
# 27 RUNOFF COEFFICIENTS (IS 15797:2008 / CGWB)
# ---------------------------------------------------------------------------
SURFACE_RUNOFF_COEFFICIENTS = {
    'concrete': 0.85,
    'cement_screed': 0.80,
    'terracotta_tiles': 0.82,
    'glazed_ceramic_tiles': 0.90,
    'unglazed_ceramic_tiles': 0.80,
    'slate_stone': 0.78,
    'corrugated_galvanized_iron': 0.90,
    'corrugated_aluminum': 0.92,
    'color_coated_steel': 0.90,
    'polycarbonate_sheet': 0.92,
    'asbestos_cement_sheet': 0.80,
    'pvc_membrane': 0.93,
    'epdm_rubber_membrane': 0.88,
    'bitumen_tar_felt': 0.75,
    'brick_bat_coba': 0.75,
    'lime_terrace': 0.70,
    'cool_roof_coating': 0.88,
    'thatched_natural': 0.45,
    'wood_shingles': 0.65,
    'extensive_green_roof': 0.50,
    'intensive_green_roof': 0.35,
    'solar_panel_arrays': 0.92,
    'glass_skylights': 0.95,
    'interlocking_concrete_pavers': 0.65,
    'permeable_porous_pavers': 0.30,
    'gravel_ballast_roof': 0.60,
    'compacted_soil_roof': 0.50,
}

# ---------------------------------------------------------------------------
# 12 SOIL INFILTRATION RATES (mm/hr) (CGWB / USDA)
# ---------------------------------------------------------------------------
SOIL_INFILTRATION_RATES = {
    'coarse_sand': 120.0,
    'fine_sand': 75.0,
    'loamy_sand': 50.0,
    'sandy_loam': 30.0,
    'loam': 20.0,
    'silt_loam': 15.0,
    'silt': 10.0,
    'sandy_clay_loam': 12.0,
    'clay_loam': 6.0,
    'silty_clay_loam': 4.0,
    'sandy_clay': 2.5,
    'heavy_clay': 0.5,
}

app = FastAPI(title="RTRWH Decision Support Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# NEW: Load Pre-Monsoon CGWB Dataset into Memory
# ---------------------------------------------------------------------------
CGWB_DATA = []
try:
    with open("cgwb_data.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                CGWB_DATA.append({
                    "village": row.get("VILLAGE", "Unknown"),
                    "district": row.get("DISTRICT", "Unknown"),
                    "lat": float(row["LATITUDE"]),
                    "lng": float(row["LONGITUDE"]),
                    "dtwl": float(row["DTWL"])
                })
            except (ValueError, KeyError):
                continue # Skip rows with missing or invalid numbers
except Exception as e:
    print(f"Warning: Could not load cgwb_data.csv. Error: {e}")

# ---------------------------------------------------------------------------
# NEW: Haversine Formula (Calculates distance between two coordinates)
# ---------------------------------------------------------------------------
def get_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

class SurfaceSplit(BaseModel):
    surface: str
    percentage: float

class AuditRequest(BaseModel):
    roof_area_sqm: float
    annual_rainfall_mm: float
    surface_splits: List[SurfaceSplit]
    soil_key: str
    water_table_depth_m: float
    roof_slope: Optional[str] = "flat"
    water_cost_per_kl_inr: Optional[float] = 60.0

class LocationLookupRequest(BaseModel):
    lat: float
    lng: float
    district: Optional[str] = None

# ---------------------------------------------------------------------------
# NEW: Auto-Lookup Environment Endpoint
# ---------------------------------------------------------------------------
@app.post("/api/lookup-environment")
def lookup_environment(req: LocationLookupRequest):
    """
    Dynamically fetches rainfall (Open-Meteo), CGWB groundwater depth, 
    and geospatial soil type with independent error handling so nothing blocks.
    """
    lat, lng = req.lat, req.lng
    
    # 1. Fetch Real Historical Climate Rainfall from Open-Meteo (Safe 3s timeout in its own try/except)
    annual_rain_mm = 950.0  
    try:
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lng}&start_date=2023-01-01&end_date=2023-12-31&daily=precipitation_sum&timezone=auto"
        req_obj = urllib.request.Request(url, headers={'User-Agent': 'SIH-RTRWH-App'})
        with urllib.request.urlopen(req_obj, timeout=3.0) as resp:
            data = json.loads(resp.read().decode())
            daily_precip = data.get("daily", {}).get("precipitation_sum", [])
            total_rain = sum(p for p in daily_precip if p is not None)
            if total_rain > 100:
                annual_rain_mm = round(total_rain, 0)
    except Exception as e:
        print(f"Rainfall fetch fallback used due to: {e}")

    # 2. Nearest Neighbor Search for Groundwater Depth using CGWB Data
    nearest_village = "Default Estimate"
    water_table_depth_m = 7.5 
    min_distance = float('inf')

    try:
        if CGWB_DATA:
            for site in CGWB_DATA:
                dist = get_haversine_distance(lat, lng, site["lat"], site["lng"])
                if dist < min_distance:
                    min_distance = dist
                    water_table_depth_m = site["dtwl"]
                    nearest_village = f"{site['village']}, {site['district']} ({round(dist, 1)}km away)"

        if min_distance > 600:
            if annual_rain_mm < 300:
                water_table_depth_m = 35.0
                nearest_village = "Global Arid Zone Estimate"
            elif 300 <= annual_rain_mm < 1000:
                water_table_depth_m = 12.5
                nearest_village = "Global Semi-Arid Estimate"
            else:
                water_table_depth_m = 3.5
                nearest_village = "Global Tropical/Coastal Estimate"
    except Exception as e:
        print(f"CGWB lookup fallback used due to: {e}")

    # 3. BULLETPROOF GEOSPATIAL SOIL HEURISTIC
    dominant_soil = "loam" 
    try:
        if 24.0 < lat < 32.0 and 74.0 < lng < 88.0:
            dominant_soil = "silt_loam"       # Indo-Gangetic Plains
        elif 18.0 < lat < 25.0 and 72.0 < lng < 80.0:
            dominant_soil = "heavy_clay"      # Deccan Trap / Black Cotton
        elif 8.0 < lat < 18.0 and 74.0 < lng < 81.0:
            dominant_soil = "sandy_loam"      # South India Red/Laterite
        elif 22.0 < lat < 30.0 and 68.0 < lng < 74.0:
            dominant_soil = "fine_sand"       # Thar Desert / Kutch
        elif 15.0 < lat < 35.0 and -17.0 < lng < 60.0:
            dominant_soil = "fine_sand"       # Sahara & Arabian Peninsula
        elif -35.0 < lat < -15.0 and 113.0 < lng < 153.0:
            dominant_soil = "sandy_loam"      # Australian Outback
        elif 30.0 < lat < 50.0 and -100.0 < lng < -70.0:
            dominant_soil = "loam"            # North American Great Plains
        elif 30.0 < lat < 50.0 and -125.0 < lng < -100.0:
            dominant_soil = "sandy_clay_loam" # North American Arid/Rockies
        elif -20.0 < lat < 10.0 and -80.0 < lng < -35.0:
            dominant_soil = "clay_loam"       # South American Amazon / Tropics
        elif 35.0 < lat < 70.0 and -10.0 < lng < 40.0:
            dominant_soil = "silt_loam"       # Europe Temperate Soils
        elif -35.0 < lat < 15.0 and -20.0 < lng < 50.0:
            dominant_soil = "sandy_clay"      # Sub-Saharan Africa
        elif -10.0 < lat < 40.0 and 90.0 < lng < 150.0:
            dominant_soil = "silty_clay_loam" # East & Southeast Asia
        else:
            if annual_rain_mm < 300:
                dominant_soil = "coarse_sand"
            elif 300 <= annual_rain_mm < 800:
                dominant_soil = "sandy_loam"
            elif 800 <= annual_rain_mm < 1500:
                dominant_soil = "loam"
            else:
                dominant_soil = "heavy_clay"
    except Exception as e:
        print(f"Soil heuristic fallback used due to: {e}")

    return {
        "status": "success",
        "annual_rainfall_mm": annual_rain_mm,
        "water_table_depth_m": round(water_table_depth_m, 2),
        "dominant_soil": dominant_soil,
        "source": f"Rainfall: Open-Meteo | DTWL: {nearest_village}"
    }


@app.get("/")
def serve_ui():
    if os.path.exists("map_tracer.html"):
        return FileResponse("map_tracer.html")
    return {"message": "SIH25065 RTRWH API is live."}

@app.get("/api/materials")
def get_materials():
    """Populates frontend dropdowns with human-readable titles"""
    surfaces = [
        {"key": k, "name": f"{k.replace('_', ' ').title()} (C={v})"}
        for k, v in SURFACE_RUNOFF_COEFFICIENTS.items()
    ]
    soils = [
        {"key": k, "name": f"{k.replace('_', ' ').title()} ({v} mm/hr)"}
        for k, v in SOIL_INFILTRATION_RATES.items()
    ]
    return {"surfaces": surfaces, "soils": soils}

@app.post("/api/calculate")
def calculate_audit(req: AuditRequest):
    try:
        # 1. Composite Runoff Coefficient
        total_coeff = 0.0
        for split in req.surface_splits:
            c = SURFACE_RUNOFF_COEFFICIENTS.get(split.surface.lower(), 0.80)
            total_coeff += c * (split.percentage / 100.0)

        # Apply pitch factor if sloped
        if req.roof_slope and req.roof_slope.lower() == "pitched":
            total_coeff = min(0.98, total_coeff * 1.05)

        runoff_coeff = round(total_coeff, 3)

        # 2. Hydrological Yield
        annual_rainfall_m = req.annual_rainfall_mm / 1000.0
        harvestable_liters = round(req.roof_area_sqm * annual_rainfall_m * runoff_coeff * 0.90 * 1000.0, 2)
        first_flush_liters = round(req.roof_area_sqm * 1.5, 2)

        # 3. Decision Matrix Evaluation
        soil_rate = SOIL_INFILTRATION_RATES.get(req.soil_key.lower(), 20.0)
        area = req.roof_area_sqm
        wt_depth = req.water_table_depth_m
        rainfall = req.annual_rainfall_mm

        pit_dimensions = None
        storage_tank_liters = 0

        # Scenario A: Shallow Water Table (< 3m) -> Risk of waterlogging & aquifer contamination
        if wt_depth < 3.0:
            system_type = "Surface Storage Tank System (Direct Reuse)"
            rationale = (
                f"Shallow groundwater table ({wt_depth} m) prohibits artificial ground injection "
                f"under CGWB guidelines. High-efficiency modular storage tank is recommended."
            )
            storage_tank_liters = min(25000, max(2000, int(harvestable_liters * 0.25)))
            capex = 22000 + int(storage_tank_liters * 5.0)

        # Scenario B: Low Soil Permeability (Clay / Dense Silt <= 5 mm/hr)
        elif soil_rate <= 5.0:
            system_type = "Underground Sump with Slow Sand Filtration"
            rationale = (
                f"Subsurface soil ({req.soil_key.replace('_', ' ').title()}) has very low infiltration capacity ({soil_rate} mm/hr). "
                f"Recharge pits will fail to percolate runoff. Storage with dual-media filtration is recommended."
            )
            storage_tank_liters = min(30000, max(3000, int(harvestable_liters * 0.30)))
            capex = 30000 + int(storage_tank_liters * 4.8)

        # Scenario C: Deep Groundwater Table (> 15m) on Medium/Large Catchments
        elif wt_depth >= 15.0 and area >= 120.0:
            system_type = "Recharge Shaft with Slotted Injection Well"
            rationale = (
                f"Deep unsaturated aquifer zone ({wt_depth} m) detected. A deep recharge shaft with PVC slotted "
                f"casing pipe is necessary to bypass upper impermeable strata directly into the unconfined aquifer."
            )
            pit_dia = 2.5
            pit_depth = 4.5
            pit_dimensions = {
                "Diameter Meters": pit_dia,
                "Depth Meters": pit_depth,
                "Cgwb Clearance Buffer Meters": round(wt_depth - pit_depth, 2),
                "Effective Volume m3": round(3.14159 * ((pit_dia / 2) ** 2) * pit_depth * 0.45, 2),
            }
            capex = 55000 + int(area * 60)

        # Scenario D: High Rainfall & Moderate/Large Area -> Dual System (Storage + Overflow Recharge)
        elif rainfall >= 1000.0 and area >= 120.0:
            system_type = "Dual Hybrid: Storage Tank + Overflow Recharge Pit"
            rationale = (
                f"High annual rainfall ({rainfall} mm) allows immediate non-potable reuse savings while routing "
                f"monsoon peak overflow to an inverted filter recharge pit to replenish local groundwater."
            )
            storage_tank_liters = min(15000, max(3000, int(harvestable_liters * 0.15)))
            pit_dia = 1.8
            pit_depth = min(3.0, max(1.5, wt_depth - 2.5))
            pit_dimensions = {
                "Diameter Meters": pit_dia,
                "Depth Meters": round(pit_depth, 2),
                "Cgwb Clearance Buffer Meters": round(wt_depth - pit_depth, 2),
                "Effective Volume m3": round(3.14159 * ((pit_dia / 2) ** 2) * pit_depth * 0.40, 2),
            }
            capex = 42000 + int(storage_tank_liters * 3.5) + int(area * 30)

        # Scenario E: Large Catchment (> 400 sqm) -> Recharge Trench with Desilting Chamber
        elif area > 400.0:
            system_type = "Continuous Recharge Trench with Siltation Chamber"
            rationale = (
                f"Large catchment area ({area} m²) generates heavy peak runoff volumes. A linear recharge trench "
                f"with coarse aggregate filter layers and desilting chamber provides adequate percolation area."
            )
            pit_dia = 3.0
            pit_depth = min(3.5, max(2.0, wt_depth - 2.5))
            pit_dimensions = {
                "Diameter Meters": pit_dia,
                "Depth Meters": round(pit_depth, 2),
                "Cgwb Clearance Buffer Meters": round(wt_depth - pit_depth, 2),
                "Effective Volume m3": round(3.14159 * ((pit_dia / 2) ** 2) * pit_depth * 0.50, 2),
            }
            capex = 60000 + int(area * 40)

        # Scenario F: Standard Small/Medium Domestic Catchment (< 120 sqm)
        else:
            system_type = "Modular Recharge Pit with Inverted Filter Media"
            rationale = (
                f"Optimal soil permeability ({soil_rate} mm/hr) and favorable water table clearance ({wt_depth} m). "
                f"A graded gravel-sand recharge pit fulfills IS 15797 standard residential criteria."
            )
            pit_dia = 1.5
            pit_depth = min(2.5, max(1.2, wt_depth - 2.0))
            pit_dimensions = {
                "Diameter Meters": pit_dia,
                "Depth Meters": round(pit_depth, 2),
                "Cgwb Clearance Buffer Meters": round(wt_depth - pit_depth, 2),
                "Effective Volume m3": round(3.14159 * ((pit_dia / 2) ** 2) * pit_depth * 0.40, 2),
            }
            capex = 28000 + int(area * 35)

        # 4. Financial & Carbon Metrics
        annual_savings = round((harvestable_liters / 1000.0) * req.water_cost_per_kl_inr, 2)
        payback_years = round(capex / max(annual_savings, 1.0), 1)
        grid_kwh_saved = round((harvestable_liters / 1000.0) * 0.45, 1)
        co2_reduction_kg = round(grid_kwh_saved * 0.82, 1)

        return {
            "status": "success",
            "data": {
                "Catchment Summary": {
                    "Total Roof Area Sqm": req.roof_area_sqm,
                    "Composite runoff Coeff": runoff_coeff,
                },
                "Hydrology": {
                    "Annual Rainfall mm": req.annual_rainfall_mm,
                    "Annual Harvestable Liters": harvestable_liters,
                    "First Flush Diverter Liters": first_flush_liters,
                },
                "Engineering Recommendation": {
                    "System Type": system_type,
                    "Design Rationale": rationale,
                    "Recharge Pit Dimensions": pit_dimensions,
                    "Storage Tank Liters": storage_tank_liters,
                },
                "Financial and Carbon ROI": {
                    "Total capex inr": capex,
                    "Annual savings inr": annual_savings,
                    "Payback years": payback_years,
                    "Grid electricity saved kwh year": grid_kwh_saved,
                    "CO2 reduction kg year": co2_reduction_kg,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
