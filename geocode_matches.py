#!/usr/bin/env python3
"""
Build the Match Explorer website from your residency-match sheet.
Everything runs on your own computer.

    pip install pandas openpyxl          (add geopy only for exact hospital lookups)
    python geocode_matches.py matches.xlsx --offline

That creates index.html next to your sheet and opens it in your browser.
Double-click index.html any time to open it again. It needs no internet
and no server, and you can copy it to a USB drive or host it anywhere.

Input columns (any order, any capitalization):
    Year, Last Name, First Name, Program, Institution, City, State

Two modes:
    --offline   No internet at all. Pins sit at each city's center, using the
                city list built into the page.
    (default)   Looks up each institution once on OpenStreetMap (needs internet
                for that step only) so pins land on the actual hospital. Results
                are saved in geocode_cache.json, so later runs are instant.
                Hospitals it can't find fall back to the city center.

To fix a pin by hand, add a row to manual_locations.csv with the columns
Institution, City, State, Latitude, Longitude, then run again.

Other options:
    --email you@school.edu   contact address sent to OpenStreetMap (polite)
    --no-open                don't open the browser when done
    --template FILE          page template (default: match-explorer-template.html
                             in the same folder as this script)
    --site FILE              output page name (default: index.html)
    --out FILE               output CSV name (default: <sheet>_geocoded.csv)
"""
import argparse
import json
import re
import sys
import webbrowser
from pathlib import Path

import pandas as pd

CACHE_FILE = Path("geocode_cache.json")
MANUAL_FILE = Path("manual_locations.csv")
HERE = Path(__file__).resolve().parent


def find_col(df, *needles):
    for col in df.columns:
        low = str(col).strip().lower()
        if any(n in low for n in needles):
            return col
    return None


def read_sheet(path):
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p, dtype=str).fillna("")
    return pd.read_csv(p, dtype=str, sep=None, engine="python", encoding="utf-8-sig").fillna("")


def in_us(lat, lon):
    return 17 <= lat <= 72 and (-180 <= lon <= -64 or lon >= 172)


def make_geocoder(email):
    try:
        from geopy.geocoders import Nominatim
        from geopy.extra.rate_limiter import RateLimiter
    except ImportError:
        sys.exit("Exact lookups need geopy: pip install geopy   (or rerun with --offline)")
    agent = f"residency-match-map ({email})" if email else "residency-match-map"
    geo = Nominatim(user_agent=agent, timeout=10)
    return RateLimiter(geo.geocode, min_delay_seconds=1.1, max_retries=2,
                       error_wait_seconds=5, swallow_exceptions=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--email", default="")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--template", default=str(HERE / "match-explorer-template.html"))
    ap.add_argument("--site", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    df = read_sheet(args.sheet)
    inst_c = find_col(df, "institution", "hospital")
    city_c = find_col(df, "city")
    state_c = find_col(df, "state")
    if not (inst_c and city_c and state_c):
        sys.exit("Couldn't find Institution, City, and State columns. Check the header row.")

    df["_inst"] = df[inst_c].str.strip()
    df["_city"] = df[city_c].str.strip()
    df["_state"] = df[state_c].str.strip()
    keys = df[["_inst", "_city", "_state"]].drop_duplicates().values.tolist()

    cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    manual = {}
    if MANUAL_FILE.exists():
        m = pd.read_csv(MANUAL_FILE, dtype=str).fillna("")
        for _, r in m.iterrows():
            k = "|".join(x.strip().lower() for x in (r["Institution"], r["City"], r["State"]))
            manual[k] = [float(r["Latitude"]), float(r["Longitude"]), "manual"]

    geocode, results, todo = None, {}, 0
    for i, (inst, city, state) in enumerate(keys, 1):
        k = "|".join(x.lower() for x in (inst, city, state))
        if k in manual:
            results[k] = manual[k]
        elif k in cache and cache[k][2] != "none":
            results[k] = cache[k]
        elif args.offline:
            results[k] = [None, None, "none"]
        else:
            geocode = geocode or make_geocoder(args.email)
            todo += 1
            print(f"[{i}/{len(keys)}] {inst}, {city}, {state}")
            hit = None
            if inst:
                loc = geocode(f"{inst}, {city}, {state}, USA")
                if loc and in_us(loc.latitude, loc.longitude):
                    hit = [loc.latitude, loc.longitude, "institution"]
            if hit is None and city:
                loc = geocode(f"{city}, {state}, USA")
                if loc and in_us(loc.latitude, loc.longitude):
                    hit = [loc.latitude, loc.longitude, "city"]
            results[k] = cache[k] = hit or [None, None, "none"]
            CACHE_FILE.write_text(json.dumps(cache, indent=1))

    lat, lon, src = [], [], []
    for inst, city, state in df[["_inst", "_city", "_state"]].values:
        la, lo, s = results["|".join(x.lower() for x in (inst, city, state))]
        lat.append(la); lon.append(lo); src.append(s)
    df["Latitude"], df["Longitude"], df["LocationSource"] = lat, lon, src
    df = df.drop(columns=["_inst", "_city", "_state"])

    sheet = Path(args.sheet)
    out = Path(args.out) if args.out else sheet.with_name(sheet.stem + "_geocoded.csv")
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"Wrote {out} ({len(df)} rows). Locations: {df['LocationSource'].value_counts().to_dict()}")

    tpl = Path(args.template)
    if tpl.exists():
        page = tpl.read_text(encoding="utf-8")
        blob = json.dumps(df.to_csv(index=False)).replace("</", "<\\/")
        page, n = re.subn(r"/\*CSV_START\*/.*?/\*CSV_END\*/",
                          lambda m: "/*CSV_START*/" + blob + "/*CSV_END*/", page, flags=re.S)
        if n != 1:
            sys.exit(f"Couldn't find the CSV_START/CSV_END markers in {tpl}")
        site = Path(args.site) if args.site else sheet.with_name("index.html")
        site.write_text(page, encoding="utf-8")
        print(f"Built {site}")
        if not args.no_open:
            webbrowser.open(site.resolve().as_uri())
    else:
        print(f"Template not found ({tpl}). Put match-explorer-template.html next to this script.")

    if not args.offline:
        bad = df[df["LocationSource"].isin(["none", "city"])][[inst_c, city_c, state_c, "LocationSource"]].drop_duplicates()
        if len(bad):
            print("\nPlaced at the city center (or not found). To pin exactly, add them to")
            print("manual_locations.csv (Institution,City,State,Latitude,Longitude) and rerun:")
            print(bad.to_string(index=False))


if __name__ == "__main__":
    main()
