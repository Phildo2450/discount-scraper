import re

with open('templates/index.html', 'r') as f:
    content = f.read()

# 1. Modify copyCode function signature to accept url parameter
content = content.replace(
    'function copyCode(code, dealId, retailer) {',
    'function copyCode(code, dealId, retailer, url) {'
)

# 2. Add redirect after successful copy in .then() block
# Find the spawnJustUsed line in .then() and add redirect after it
# The .then() block ends with spawnJustUsed then closing braces
old_spawn = "spawnJustUsed(`Just copied ${retailer} code!`);\n    }).catch(() => {"
new_spawn = """spawnJustUsed(`Just copied ${retailer} code!`);
    // Redirect to retailer website so user can verify/apply the code
    if (url && url !== '#') { setTimeout(() => { window.open(url, '_blank'); }, 800); }
    }).catch(() => {"""
content = content.replace(old_spawn, new_spawn)

# 3. Add redirect in .catch() fallback too - find the second spawnJustUsed
# The catch block ends with spawnJustUsed then });  }
old_catch_spawn = "spawnJustUsed(`Just copied ${retailer} code!`);\n});\n}"
new_catch_spawn = """spawnJustUsed(`Just copied ${retailer} code!`);
    // Redirect to retailer website so user can verify/apply the code
    if (url && url !== '#') { setTimeout(() => { window.open(url, '_blank'); }, 800); }
});
}"""
content = content.replace(old_catch_spawn, new_catch_spawn)

# 4. Update button onclick to pass URL - main deal cards
content = content.replace(
    """onclick="copyCode('${esc(d.code)}','${d.id}','${esc(d.retailer)}')" """,
    """onclick="copyCode('${esc(d.code)}','${d.id}','${esc(d.retailer)}','${esc(d.affiliateUrl||d.url||\"#\")}')" """
)

# 5. Update featured deal onclick
content = content.replace(
    "copyCode(deal.code || deal.description, deal.id, deal.retailer)",
    "copyCode(deal.code || deal.description, deal.id, deal.retailer, deal.affiliateUrl || deal.url || '#')"
)

# 6. Update trending/other card onclick patterns
content = content.replace(
    """onclick="copyCode('${esc(d.code||d.description)}','${d.id}','${esc(d.retailer)}')" """,
    """onclick="copyCode('${esc(d.code||d.description)}','${d.id}','${esc(d.retailer)}','${esc(d.affiliateUrl||d.url||\"#\")}')" """
)

# 7. Add tooltip to code-box
content = content.replace(
    '<div class="code-box">',
    '<div class="code-box" title="Click to copy code and visit retailer">'
)

with open('templates/index.html', 'w') as f:
    f.write(content)

print('SUCCESS: Front-end updated with click-to-redirect feature')
print(f'File size: {len(content)} chars')
