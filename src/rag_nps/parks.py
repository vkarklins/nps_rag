"""
Lookup of the parks in the incident data: park code, park name, and the state(s) each park touches.

Hand-entered (the scraped data has no state information) and to be checked against the official
NPS list. park_code and park_name match the `incidents` table (62 codes; Sequoia and Kings Canyon
share SEKI). States are two-letter postal codes; AS and VI are territories.

A state means "parks that touch that state": for multi-state parks (DEVA, GRSM, YELL) the source
does not say which state an incident happened in, so state lookups over-include for those parks.
"""

PARKS = {
    "ACAD": {"name": "Acadia National Park", "states": ["ME"]},
    "ARCH": {"name": "Arches National Park", "states": ["UT"]},
    "BADL": {"name": "Badlands National Park", "states": ["SD"]},
    "BIBE": {"name": "Big Bend National Park", "states": ["TX"]},
    "BISC": {"name": "Biscayne National Park", "states": ["FL"]},
    "BLCA": {"name": "Black Canyon of the Gunnison National Park", "states": ["CO"]},
    "BRCA": {"name": "Bryce Canyon National Park", "states": ["UT"]},
    "CANY": {"name": "Canyonlands National Park", "states": ["UT"]},
    "CARE": {"name": "Capitol Reef National Park", "states": ["UT"]},
    "CAVE": {"name": "Carlsbad Caverns National Park", "states": ["NM"]},
    "CHIS": {"name": "Channel Islands National Park", "states": ["CA"]},
    "CONG": {"name": "Congaree National Park", "states": ["SC"]},
    "CRLA": {"name": "Crater Lake National Park", "states": ["OR"]},
    "CUVA": {"name": "Cuyahoga Valley National Park", "states": ["OH"]},
    "DENA": {"name": "Denali National Park and Preserve", "states": ["AK"]},
    "DEVA": {"name": "Death Valley National Park", "states": ["CA", "NV"]},
    "DRTO": {"name": "Dry Tortugas National Park", "states": ["FL"]},
    "EVER": {"name": "Everglades National Park", "states": ["FL"]},
    "GAAR": {"name": "Gates of the Arctic National Park and Preserve", "states": ["AK"]},
    "GLAC": {"name": "Glacier National Park", "states": ["MT"]},
    "GLBA": {"name": "Glacier Bay National Park and Preserve", "states": ["AK"]},
    "GRBA": {"name": "Great Basin National Park", "states": ["NV"]},
    "GRCA": {"name": "Grand Canyon National Park", "states": ["AZ"]},
    "GRSA": {"name": "Great Sand Dunes National Park and Preserve", "states": ["CO"]},
    "GRSM": {"name": "Great Smoky Mountains National Park", "states": ["NC", "TN"]},
    "GRTE": {"name": "Grand Teton National Park", "states": ["WY"]},
    "GUMO": {"name": "Guadalupe Mountains National Park", "states": ["TX"]},
    "HALE": {"name": "Haleakala National Park", "states": ["HI"]},
    "HAVO": {"name": "Hawaii Volcanoes National Park", "states": ["HI"]},
    "HOSP": {"name": "Hot Springs National Park", "states": ["AR"]},
    "INDU": {"name": "Indiana Dunes National Park", "states": ["IN"]},
    "ISRO": {"name": "Isle Royale National Park", "states": ["MI"]},
    "JEFF": {"name": "Gateway Arch National Park", "states": ["MO"]},
    "JOTR": {"name": "Joshua Tree National Park", "states": ["CA"]},
    "KATM": {"name": "Katmai National Park and Preserve", "states": ["AK"]},
    "KEFJ": {"name": "Kenai Fjords National Park", "states": ["AK"]},
    "KOVA": {"name": "Kobuk Valley National Park", "states": ["AK"]},
    "LACL": {"name": "Lake Clark National Park and Preserve", "states": ["AK"]},
    "LAVO": {"name": "Lassen Volcanic National Park", "states": ["CA"]},
    "MACA": {"name": "Mammoth Cave National Park", "states": ["KY"]},
    "MEVE": {"name": "Mesa Verde National Park", "states": ["CO"]},
    "MORA": {"name": "Mount Rainier National Park", "states": ["WA"]},
    "NERI": {"name": "New River Gorge National Park and Preserve", "states": ["WV"]},
    "NOCA": {"name": "North Cascades National Park", "states": ["WA"]},
    "NPSA": {"name": "National Park of American Samoa", "states": ["AS"]},
    "OLYM": {"name": "Olympic National Park", "states": ["WA"]},
    "PEFO": {"name": "Petrified Forest National Park", "states": ["AZ"]},
    "PINN": {"name": "Pinnacles National Park", "states": ["CA"]},
    "REDW": {"name": "Redwood National and State Parks", "states": ["CA"]},
    "ROMO": {"name": "Rocky Mountain National Park", "states": ["CO"]},
    "SAGU": {"name": "Saguaro National Park", "states": ["AZ"]},
    "SEKI": {"name": "Sequoia and Kings Canyon National Parks", "states": ["CA"]},
    "SHEN": {"name": "Shenandoah National Park", "states": ["VA"]},
    "THRO": {"name": "Theodore Roosevelt National Park", "states": ["ND"]},
    "VIIS": {"name": "Virgin Islands National Park", "states": ["VI"]},
    "VOYA": {"name": "Voyageurs National Park", "states": ["MN"]},
    "WHSA": {"name": "White Sands National Park", "states": ["NM"]},
    "WICA": {"name": "Wind Cave National Park", "states": ["SD"]},
    "WRST": {"name": "Wrangell-St. Elias National Park and Preserve", "states": ["AK"]},
    "YELL": {"name": "Yellowstone National Park", "states": ["WY", "MT", "ID"]},
    "YOSE": {"name": "Yosemite National Park", "states": ["CA"]},
    "ZION": {"name": "Zion National Park", "states": ["UT"]},
}


def park_codes_for_states(states):
    """Return the sorted park codes for parks that touch any of the given state codes."""
    wanted = set(states)
    return sorted(code for code, park in PARKS.items() if wanted & set(park["states"]))


def format_park_table():
    """Build the 'code — name (states)' lines used in the router's system prompt."""
    lines = []
    for code in sorted(PARKS):
        info = PARKS[code]
        states = ", ".join(info["states"])
        lines.append(f"{code} — {info['name']} ({states})")
    return "\n".join(lines)
