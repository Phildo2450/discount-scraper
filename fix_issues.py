import re

with open('app.py', 'r') as f:
    content = f.read()

# Fix 1: Add CVS and Macys to RETAILERS list
uber_line = '    {"name": "Uber Eats",'
uber_idx = content.find(uber_line)
if uber_idx >= 0:
    uber_end = content.find('\n', uber_idx)
    insert_pos = uber_end + 1
    new_entries = '    {"name": "CVS",         "domain": "cvs.com",            "color": "#CC0000", "icon": "\\U0001f48a", "category": "health",  "slug": "cvs"},\n    {"name": "Macys",       "domain": "macys.com",          "color": "#E21A2C", "icon": "\\U0001f6cd", "category": "fashion", "slug": "macys"},\n'
    content = content[:insert_pos] + new_entries + content[insert_pos:]
    print("Fix 1: Added CVS and Macys to RETAILERS")
else:
    print("ERROR: Could not find Uber Eats in RETAILERS")

# Fix 2: Add CVS and Macys to KEYWORD_MAP
uber_kw = '"ubereats": "Uber Eats",'
uber_kw_idx = content.find(uber_kw)
if uber_kw_idx >= 0:
    line_end = content.find('\n', uber_kw_idx)
    insert_pos = line_end + 1
    new_keywords = '    "cvs": "CVS", "cvs pharmacy": "CVS",\n    "macys": "Macys", "macy\'s": "Macys", "macys.com": "Macys",\n'
    content = content[:insert_pos] + new_keywords + content[insert_pos:]
    print("Fix 2: Added CVS and Macys to KEYWORD_MAP")
else:
    print("ERROR: Could not find ubereats in KEYWORD_MAP")

# Fix 3: In api_deals, add domain field AND fix Macy's code
old_loop = '    for deal in deals:\n        if not deal.get("url"):\n            retailer = deal.get("retailer", "")\n            domain = domain_map.get(retailer.lower(), "")\n            if domain:\n                deal["url"] = f"https://www.{domain}"\n    return jsonify(data)'

new_loop = '    for deal in deals:\n        retailer = deal.get("retailer", "")\n        domain = domain_map.get(retailer.lower(), "")\n        if domain:\n            deal["domain"] = domain\n            if not deal.get("url"):\n                deal["url"] = f"https://www.{domain}"\n        # Fix Macy\'s code: BEST1521 should be SHOP1521\n        if retailer.lower() == "macys" and deal.get("code") == "BEST1521":\n            deal["code"] = "SHOP1521"\n    return jsonify(data)'

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    print("Fix 3: Fixed api_deals to add domain and fix Macy's code")
else:
    print("ERROR: Could not find api_deals loop")

# Fix 4: In api_deals_trending, add domain field and fix Macy's code
old_trending = '    if deals:\n        domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}\n        for deal in deals:\n            if deal.get("code"):\n                if not deal.get("url"):\n                    domain = domain_map.get(deal.get("retailer", "").lower(), "")\n                    if domain:\n                        deal["url"] = f"https://www.{domain}"\n                return jsonify(deal)'

new_trending = '    if deals:\n        domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}\n        for deal in deals:\n            if deal.get("code"):\n                retailer = deal.get("retailer", "")\n                domain = domain_map.get(retailer.lower(), "")\n                if domain:\n                    deal["domain"] = domain\n                    if not deal.get("url"):\n                        deal["url"] = f"https://www.{domain}"\n                if retailer.lower() == "macys" and deal.get("code") == "BEST1521":\n                    deal["code"] = "SHOP1521"\n                return jsonify(deal)'

if old_trending in content:
    content = content.replace(old_trending, new_trending)
    print("Fix 4: Fixed api_deals_trending")
else:
    print("ERROR: Could not find api_deals_trending pattern")

# Fix 5: In api_deals_featured, add domain field and fix Macy's code
old_featured = '        domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}\n        for deal in deals:\n            if deal.get("code"):\n                if not deal.get("url"):\n                    domain = domain_map.get(deal.get("retailer", "").lower(), "")'

new_featured = '        domain_map = {r["name"].lower(): r["domain"] for r in RETAILERS}\n        for deal in deals:\n            if deal.get("code"):\n                retailer = deal.get("retailer", "")\n                domain = domain_map.get(retailer.lower(), "")\n                if domain:\n                    deal["domain"] = domain\n                if retailer.lower() == "macys" and deal.get("code") == "BEST1521":\n                    deal["code"] = "SHOP1521"\n                if not deal.get("url"):\n                    domain = domain_map.get(deal.get("retailer", "").lower(), "")'

if old_featured in content:
    content = content.replace(old_featured, new_featured)
    print("Fix 5: Fixed api_deals_featured")
else:
    print("ERROR: Could not find api_deals_featured pattern")

with open('app.py', 'w') as f:
    f.write(content)

print(f"\nAll fixes applied! File size: {len(content)} chars")
