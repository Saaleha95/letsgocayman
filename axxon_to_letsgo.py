#!/usr/bin/env python3
"""
Poll Axxon for the Toyota Hiace (North Side / Cayman Kai shuttle) and push its
position to LetsGo.

  pip install requests
  export AXXON_KEY=99a8800d22cd02476c463ce7c6fd31727e8230d9
  python axxon_to_letsgo.py
"""
import os
import time
import requests

AXXON_URL = "https://app.axxon.co/api/v1/unit/list.json"
AXXON_KEY = os.environ.get("AXXON_KEY", "99a8800d22cd02476c463ce7c6fd31727e8230d9")
AXXON_UNIT_ID = os.environ.get("AXXON_UNIT_ID", "579187")
UNIT_LABEL = "Toyota Hiace"

LETSGO_URL = "https://www.letsgocayman.com/api/buses/coordinates"
BUS_ID = "EASTERN LINK \u2013 North Side Cayman Kai"  # en dash, must match the registered busId exactly

POLL_SECONDS = 5

LAT_KEYS = ("lat", "latitude")
LNG_KEYS = ("lng", "lon", "long", "longitude")


def find_unit(node, label):
    """Recursively find the dict whose 'label' equals `label`."""
    if isinstance(node, dict):
        if node.get("label") == label:
            return node
        for v in node.values():
            hit = find_unit(v, label)
            if hit:
                return hit
    elif isinstance(node, list):
        for item in node:
            hit = find_unit(item, label)
            if hit:
                return hit
    return None


def find_coords(node):
    """Recursively find a (lat, lng) pair inside the unit record."""
    if isinstance(node, dict):
        lat = next((node[k] for k in LAT_KEYS if k in node), None)
        lng = next((node[k] for k in LNG_KEYS if k in node), None)
        if lat is not None and lng is not None:
            try:
                return float(lat), float(lng)
            except (TypeError, ValueError):
                pass
        for v in node.values():
            hit = find_coords(v)
            if hit:
                return hit
    elif isinstance(node, list):
        for item in node:
            hit = find_coords(item)
            if hit:
                return hit
    return None


def fetch_position():
    r = requests.get(
        AXXON_URL,
        params={"key": AXXON_KEY, "unit_id": AXXON_UNIT_ID},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    unit = find_unit(data, UNIT_LABEL)
    if unit is None:
        raise ValueError(f'No unit with label "{UNIT_LABEL}" in Axxon response: {str(data)[:300]}')
    coords = find_coords(unit)
    if coords is None:
        raise ValueError(f"No lat/lng found in unit record: {str(unit)[:300]}")
    ms = find_key(unit, "movement_state")
    state = (ms.get("name") if isinstance(ms, dict) else ms) or ""
    driving = str(state).strip().lower() == "driving"
    return coords[0], coords[1], driving, state


def find_key(node, key):
    """Recursively find the value of `key`."""
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for v in node.values():
            hit = find_key(v, key)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for item in node:
            hit = find_key(item, key)
            if hit is not None:
                return hit
    return None


def push_position(lat, lng, active):
    r = requests.post(
        LETSGO_URL,
        json={"busId": BUS_ID, "lat": lat, "lng": lng, "active": active},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def main():
    print(f"Bridging Axxon unit {AXXON_UNIT_ID} ({UNIT_LABEL}) -> {BUS_ID}")
    last = None
    while True:
        try:
            lat, lng, driving, state = fetch_position()
            push_position(lat, lng, driving)
            cur = (lat, lng, driving)
            if cur != last:
                print(f"{time.strftime('%H:%M:%S')}  pushed {lat:.6f}, {lng:.6f}  "
                      f"state={state or 'unknown'}  active={driving}")
                last = cur
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')}  error: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
