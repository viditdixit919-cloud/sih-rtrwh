import json
import math

# Top-level lists (accessible by api.py)
surface_options = [
    ("concrete", "Standard Concrete Roof (RCC)"),
    ("ceramic_tiles", "Ceramic / Vitrified Tiles"),
    ("brick_bat_coba", "Brick Bat Coba Screed"),
    ("china_mosaic", "China Mosaic Flooring"),
    ("terracotta_tiles", "Terracotta Clay Tiles"),
    ("ips_flooring", "Indian Patent Stone (IPS)"),
    ("kota_stone", "Kota Stone Flooring"),
    ("metal_sheet", "Corrugated Metal Roofing"),
    ("membrane", "Waterproof Sheet Membrane (PVC/EPDM)"),
    ("polyurea", "Polyurea Liquid Membrane"),
    ("pmma_screed", "PMMA Liquid Screed"),
    ("glass_mosaic", "Monolithic Glass Tile Screed"),
    ("quartz", "Broadcast Quartz Flooring"),
    ("thermal_tiles", "Thermal Sandwich Tiles"),
    ("industrial_paving", "Acid-Resistant Industrial Paving"),
    ("microcement", "Exterior Microcement"),
    ("granolithic", "Granolithic Concrete Screed"),
    ("stamped_concrete", "Stamped / Patterned Concrete"),
    ("hydraulic_tiles", "Hydraulic Pressed Cement Tiles"),
    ("lime_surkhi", "Lime-Surkhi Pozzolanic Concrete"),
    ("pavers", "Interlocking Pavers & Tiles"),
    ("paved_brick", "Paved Brick Flooring"),
    ("epdm_rubber", "Pour-in-Place EPDM Rubber"),
    ("green_roof", "Green / Vegetative Soft Flooring"),
    ("resin_gravel", "Resin Bound Permeable Gravel"),
]

soil_options = [
    ("loam", "Loamy Soil (Standard balanced ground)"),
    ("sandy_loam", "Sandy Loam (Fast draining)"),
    ("coarse_sand", "Coarse Sand"),
    ("fine_sand", "Fine Sand"),
    ("gravel", "Gravel / Rocky ground"),
    ("chalky", "Chalky / Limestone ground"),
    ("silt_loam", "Silt Loam"),
    ("silt", "Silt Soil"),
    ("sandy_clay_loam", "Sandy Clay Loam"),
    ("clay_loam", "Clay Loam"),
    ("silty_clay_loam", "Silty Clay Loam"),
    ("sandy_clay", "Sandy Clay"),
    ("silty_clay", "Silty Clay"),
    ("heavy_clay", "Heavy Clay (Water pools on surface)"),
    ("peat", "Peat / Organic Spongy Soil"),
    ("saline", "Saline / Mineral-rich Soil"),
]


def calculate_rtrwh_complete(
    roof_area_sqm,
    annual_rainfall_mm,
    surface_splits,
    soil_key,
    water_table_depth_m,
    roof_slope="flat",  # "flat" or "pitched"
    water_cost_per_kl_inr=60.0,
    peak_24h_rainfall_mm=50.0,
):
    # 1. Surface Database (26 Specialized Materials)
    surface_db = {
        "pmma_screed": {"name": "PMMA Liquid Screed", "C": 0.95},
        "polyurea": {"name": "Polyurea Liquid Membrane", "C": 0.95},
        "glass_mosaic": {"name": "Monolithic Glass Tile Screed", "C": 0.93},
        "quartz": {"name": "Broadcast Quartz Flooring", "C": 0.92},
        "thermal_tiles": {"name": "Thermal Sandwich Tiles", "C": 0.90},
        "membrane": {
            "name": "Waterproof Sheet Membrane (PVC/EPDM)",
            "C": 0.90,
        },
        "mastic_asphalt": {"name": "Mastic Asphalt Decking", "C": 0.90},
        "metal_sheet": {
            "name": "Corrugated Metal / Sheet Roofing",
            "C": 0.90,
        },
        "china_mosaic": {"name": "China Mosaic Flooring", "C": 0.90},
        "ceramic_tiles": {"name": "Ceramic / Vitrified Tiles", "C": 0.88},
        "industrial_paving": {
            "name": "Acid-Resistant Industrial Paving",
            "C": 0.88,
        },
        "microcement": {"name": "Exterior Microcement", "C": 0.88},
        "granolithic": {"name": "Granolithic Concrete Screed", "C": 0.86},
        "brick_bat_coba": {
            "name": "Brick Bat Coba with Smooth Screed",
            "C": 0.85,
        },
        "concrete": {"name": "Standard Concrete Roof (RCC)", "C": 0.85},
        "ips_flooring": {
            "name": "Indian Patent Stone (IPS) Flooring",
            "C": 0.85,
        },
        "stamped_concrete": {"name": "Stamped / Patterned Concrete", "C": 0.82},
        "kota_stone": {"name": "Kota Stone Flooring", "C": 0.82},
        "hydraulic_tiles": {
            "name": "Hydraulic Pressed Cement Tiles",
            "C": 0.78,
        },
        "terracotta_tiles": {"name": "Terracotta Clay Tiles", "C": 0.78},
        "lime_surkhi": {"name": "Traditional Lime-Surkhi Concrete", "C": 0.75},
        "pavers": {"name": "Interlocking Pavers & Tiles", "C": 0.70},
        "paved_brick": {"name": "Paved Brick Flooring", "C": 0.70},
        "epdm_rubber": {
            "name": "Pour-in-Place EPDM Rubber Flooring",
            "C": 0.55,
        },
        "green_roof": {"name": "Green / Vegetative Soft Flooring", "C": 0.40},
        "resin_gravel": {"name": "Resin Bound Permeable Gravel", "C": 0.35},
    }

    # 2. Soil Database (16 Geotechnical Classes)
    soil_db = {
        "gravel": {
            "name": "Gravel / Sandy Gravel",
            "k": 0.360,
            "suitable_for_ar": True,
        },
        "coarse_sand": {
            "name": "Coarse Sand",
            "k": 0.120,
            "suitable_for_ar": True,
        },
        "fine_sand": {
            "name": "Fine Sand",
            "k": 0.060,
            "suitable_for_ar": True,
        },
        "chalky": {
            "name": "Chalky / Limestone Soil",
            "k": 0.040,
            "suitable_for_ar": True,
        },
        "sandy_loam": {
            "name": "Sandy Loam Soil",
            "k": 0.030,
            "suitable_for_ar": True,
        },
        "loam": {"name": "Loamy Soil", "k": 0.020, "suitable_for_ar": True},
        "silt_loam": {
            "name": "Silt Loam Soil",
            "k": 0.010,
            "suitable_for_ar": True,
        },
        "sandy_clay_loam": {
            "name": "Sandy Clay Loam Soil",
            "k": 0.008,
            "suitable_for_ar": True,
        },
        "silt": {"name": "Silt Soil", "k": 0.005, "suitable_for_ar": True},
        "clay_loam": {
            "name": "Clay Loam Soil",
            "k": 0.004,
            "suitable_for_ar": False,
        },
        "silty_clay_loam": {
            "name": "Silty Clay Loam Soil",
            "k": 0.003,
            "suitable_for_ar": False,
        },
        "sandy_clay": {
            "name": "Sandy Clay Soil",
            "k": 0.002,
            "suitable_for_ar": False,
        },
        "peat": {
            "name": "Peat / Organic Soil",
            "k": 0.002,
            "suitable_for_ar": False,
        },
        "saline": {
            "name": "Saline Soil",
            "k": 0.001,
            "suitable_for_ar": False,
        },
        "silty_clay": {
            "name": "Silty Clay Soil",
            "k": 0.001,
            "suitable_for_ar": False,
        },
        "heavy_clay": {
            "name": "Heavy Clay Soil",
            "k": 0.0003,
            "suitable_for_ar": False,
        },
    }

    # Composite C Calculation & Slope Factor
    composite_C = sum(
        (s["percentage"] / 100.0) * surface_db[s["surface"]]["C"]
        for s in surface_splits
    )
    if roof_slope.lower() == "pitched":
        composite_C = min(0.98, composite_C * 1.05)
    composite_C = round(composite_C, 3)

    # First Flush Volume
    first_flush_liters = round(roof_area_sqm * 1.5, 1)

    # Hydrological Output
    annual_yield_liters = round(
        roof_area_sqm * (annual_rainfall_mm / 1000.0) * composite_C * 1000.0, 0
    )
    peak_volume_m3 = roof_area_sqm * (peak_24h_rainfall_mm / 1000.0) * composite_C

    soil = soil_db[soil_key]
    k = soil["k"]
    is_ar_viable = soil["suitable_for_ar"]

    # CGWB Water Table Safety Clearance
    max_safe_pit_depth = max(1.0, water_table_depth_m - 2.0)
    recommendation = {}

    if not is_ar_viable or k < 0.005 or max_safe_pit_depth < 1.5:
        tank_capacity = min(annual_yield_liters * 0.25, 45000)
        recommendation["System Type"] = (
            "Dedicated Above-Ground Storage Tank System"
        )
        recommendation["Storage Tank Liters"] = round(tank_capacity, -2)
        if max_safe_pit_depth < 1.5:
            recommendation["Design Rationale"] = (
                f"High water table detected ({water_table_depth_m}m). CGWB safety norms mandate a 2.0m clearance buffer, making subsurface pits unsafe."
            )
        else:
            recommendation["Design Rationale"] = (
                f"{soil['name']} has poor drainage (k={k} m/hr). Direct reuse storage is recommended."
            )
    else:
        # Dual Hybrid System
        domestic_tank_liters = min(5000.0, annual_yield_liters * 0.08)
        excess_peak_volume_m3 = max(
            0.5, peak_volume_m3 - (domestic_tank_liters / 1000.0)
        )

        detention_time_hrs = 4
        absorbed_volume_m3 = (roof_area_sqm * k * detention_time_hrs) / 100
        required_pit_volume_m3 = max(
            0.5, excess_peak_volume_m3 - absorbed_volume_m3
        )

        pit_depth_m = min(2.5, max_safe_pit_depth)
        pit_surface_area = required_pit_volume_m3 / pit_depth_m
        pit_dia_m = max(1.2, round(math.sqrt(pit_surface_area / math.pi) * 2, 2))

        filter_layer_vol = round(
            math.pi * ((pit_dia_m / 2) ** 2) * 0.5, 2
        )

        recommendation["System Type"] = (
            "Dual Hybrid System: Direct Storage Tank + Recharge Pit"
        )
        recommendation["Storage Buffer Liters"] = round(
            domestic_tank_liters, -2
        )
        recommendation["Recharge Pit Dimensions"] = {
            "Diameter Meters": pit_dia_m,
            "Depth Meters": pit_depth_m,
            "Effective Volume m3": round(required_pit_volume_m3, 2),
            "Cgwb Clearance Buffer Meters": round(
                water_table_depth_m - pit_depth_m, 2
            ),
        }
        recommendation["Filter Media Breakdown"] = {
            "Coarse Sand Top Layer m3": filter_layer_vol,
            "Gravel Middle Layer m3": filter_layer_vol,
            "Pebbles Boulders Bottom Layer m3": filter_layer_vol,
        }
        recommendation["Design Rationale"] = (
            f"Favorable soil and safe groundwater clearance ({water_table_depth_m}m). Excess rainwater recharges the aquifer after filling the domestic buffer tank."
        )

    # Financial & Environmental Returns
    cost_inr = round(18000 + (roof_area_sqm * 135), -2)
    water_saved_kl = annual_yield_liters / 1000.0
    annual_savings_inr = round(water_saved_kl * water_cost_per_kl_inr, 2)
    payback_years = (
        round(cost_inr / annual_savings_inr, 1) if annual_savings_inr > 0 else 0
    )

    kwh_saved = round(water_saved_kl * 0.45, 1)
    co2_offset = round(kwh_saved * 0.82, 1)

    return {
        "Catchment Summary": {
            "Area sqm": roof_area_sqm,
            "Slope": roof_slope.capitalize(),
            "Composite runoff Coeff": composite_C,
        },
        "Hydrology": {
            "Annual Harvestable Liters": annual_yield_liters,
            "First Flush Diverter Liters": first_flush_liters,
        },
        "Engineering Recommendation": recommendation,
        "Financial and Carbon ROI": {
            "Total capex inr": cost_inr,
            "Annual savings inr": annual_savings_inr,
            "Payback years": payback_years,
            "Grid electricity saved kwh year": kwh_saved,
            "CO2 reduction kg year": co2_offset,
        },
    }


# --- INTERACTIVE USER PROMPT EXECUTION ---
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("   AI ROOFTOP RWH, RECHARGE & FINANCIAL ROI AUDITOR (SIH)")
    print("=" * 70)

    try:
        user_area = float(
            input("\n1. Enter Total Roof/Terrace Area (in sq. meters) [e.g., 200]: ")
        )
        user_rain = float(
            input("2. Enter Average Annual Rainfall (in mm) [e.g., 900]: ")
        )

        slope_choice = input("3. Is the roof flat or pitched? (flat/pitched) [default: flat]: ").strip().lower()
        if slope_choice not in ["flat", "pitched"]:
            slope_choice = "flat"

        print("\n--- Catchment Material Setup ---")
        user_splits = []
        remaining_percentage = 100.0

        while remaining_percentage > 0:
            print(f"\nRemaining Roof Allocation: {remaining_percentage:.1f}%")
            print("Select Surface Material:")
            for idx, (_, name) in enumerate(surface_options, 1):
                print(f"  {idx:2d}. {name}")

            s_choice = int(input(f"\nEnter choice [1-{len(surface_options)}]: "))
            selected_surface = surface_options[s_choice - 1][0]

            if remaining_percentage == 100.0:
                is_mixed = input("\nDoes your terrace have multiple flooring types? (y/n) [default: n]: ").strip().lower()
                if is_mixed != "y":
                    user_splits.append({"surface": selected_surface, "percentage": 100.0})
                    break

            pct = float(input(f"Enter percentage for this material (Max {remaining_percentage:.1f}%): "))
            if pct <= 0 or pct > remaining_percentage:
                print(f"[Error] Please enter a valid number between 1 and {remaining_percentage}%.")
                continue

            user_splits.append({"surface": selected_surface, "percentage": pct})
            remaining_percentage -= pct

        print("\n--- Select Soil Condition at Location ---")
        print(f"  Total soil options available: {len(soil_options)}")
        for idx, (_, name) in enumerate(soil_options, 1):
            print(f"  {idx:2d}. {name}")

        g_choice = int(input(f"\nEnter choice [1-{len(soil_options)}]: "))
        selected_soil = soil_options[g_choice - 1][0]

        user_water_table = float(
            input("\n4. Enter Depth to Groundwater Table (in meters) [e.g., 6.5]: ")
        )
        user_cost = float(
            input("5. Enter Local Water Cost (INR per 1,000 Liters / kL) [e.g., 60]: ")
        )

        audit_report = calculate_rtrwh_complete(
            roof_area_sqm=user_area,
            annual_rainfall_mm=user_rain,
            surface_splits=user_splits,
            soil_key=selected_soil,
            water_table_depth_m=user_water_table,
            roof_slope=slope_choice,
            water_cost_per_kl_inr=user_cost,
        )

        print("\n" + "=" * 25 + " FINAL SITE AUDIT REPORT " + "=" * 25)
        print(json.dumps(audit_report, indent=4))
        print("=" * 75 + "\n")

    except (ValueError, IndexError) as err:
        print(f"\n[Error] Invalid input entered ({err}). Please run again.")
