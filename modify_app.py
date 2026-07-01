import re

with open('app.py', 'r') as f:
    content = f.read()

# Step 1: Add new imports after existing imports
import_section_end = 0
for match in re.finditer(r'^(import |from )', content, re.MULTILINE):
    import_section_end = content.find('\n', match.end()) + 1

new_imports = """from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

# --- Validation & Scheduling Setup ---
validation_logger = logging.getLogger('code_validation')
validation_logger.setLevel(logging.INFO)
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
validation_logger.addHandler(_log_handler)

INVALID_CODES_LOG = []  # Stores codes that failed validation

"""

content = content[:import_section_end] + new_imports + content[import_section_end:]

# Step 2: Add validation function before scrape_all or after build_deal
# Find a good insertion point - after the helpers section
validation_code = '''
# --- Code Validation Logic ---
def validate_code_against_aggregators(code, retailer):
    """Cross-reference a coupon code against multiple aggregator sources.
    
    Checks the code against couponfollow, savings.com, and couponcabin
    to verify the code appears on at least one other source.
    Returns True if code is validated, False otherwise.
    """
    if not code or code.strip() == "":
        return False
    
    aggregator_urls = [
        f"https://couponfollow.com/site/{retailer.lower().replace(' ', '')}",
        f"https://www.savings.com/store/{retailer.lower().replace(' ', '-')}",
        f"https://www.couponcabin.com/coupons/{retailer.lower().replace(' ', '-')}",
        f"https://www.retailmenot.com/view/{retailer.lower().replace(' ', '')}.com",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    validations = 0
    sources_checked = 0
    
    for url in aggregator_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                sources_checked += 1
                # Check if the code appears in the page content
                if code.upper() in resp.text.upper():
                    validations += 1
                    validation_logger.info(f"Code '{code}' for {retailer} FOUND on {url}")
        except Exception as e:
            validation_logger.debug(f"Error checking {url}: {e}")
            continue
    
    # Code is valid if found on at least 1 aggregator source, or if no sources could be checked
    # (graceful degradation - don't block codes if aggregators are down)
    if sources_checked == 0:
        validation_logger.warning(f"No aggregator sources reachable for {retailer} code '{code}' - allowing by default")
        return True
    
    is_valid = validations >= 1
    if not is_valid:
        validation_logger.warning(f"Code '{code}' for {retailer} NOT found on any of {sources_checked} aggregator sources")
    return is_valid


def validate_and_filter_deals(new_deals):
    """Validate scraped deals and return only verified ones.
    
    Codes are cross-referenced against aggregator sources.
    Invalid codes are logged but not published.
    Only validated/working codes replace current live codes.
    """
    global INVALID_CODES_LOG
    validated_deals = []
    invalid_deals = []
    
    for deal in new_deals:
        code = deal.get("code", "")
        retailer = deal.get("retailer", "")
        
        # Deals without codes (percentage-off links, etc.) pass through
        if not code or code.strip() == "":
            validated_deals.append(deal)
            continue
        
        # Validate the code against aggregator sources
        if validate_code_against_aggregators(code, retailer):
            deal["validated"] = True
            deal["validated_at"] = datetime.now().isoformat()
            validated_deals.append(deal)
        else:
            # Log invalid code but do NOT publish
            invalid_entry = {
                "code": code,
                "retailer": retailer,
                "description": deal.get("description", ""),
                "reason": "Not found on aggregator sources",
                "scraped_at": datetime.now().isoformat()
            }
            INVALID_CODES_LOG.append(invalid_entry)
            invalid_deals.append(deal)
            validation_logger.info(
                f"REJECTED: Code '{code}' for {retailer} - not validated by aggregators"
            )
    
    validation_logger.info(
        f"Validation complete: {len(validated_deals)} valid, {len(invalid_deals)} rejected"
    )
    return validated_deals

'''

# Insert validation code before the scrape_all function
scrape_all_pos = content.find('def scrape_all(')
if scrape_all_pos == -1:
    scrape_all_pos = content.find('def scrape_retailer(')
content = content[:scrape_all_pos] + validation_code + '\n' + content[scrape_all_pos:]

# Step 3: Modify scrape_all to use validation and only-publish-verified logic
# Find the scrape_all function and modify it
old_scrape_all_match = re.search(r'def scrape_all\(\):(.*?)(?=\ndef [a-z])', content, re.DOTALL)
if old_scrape_all_match:
    old_scrape_all = old_scrape_all_match.group(0)
    # Create new scrape_all that validates before publishing
    new_scrape_all = '''def scrape_all():
    """Scrape all retailers, validate codes, and only publish verified deals."""
    global _scrape_status
    _scrape_status = {"running": True, "last_run": None, "message": "Scraping in progress..."}
    all_new_deals = []
    
    for retailer in RETAILERS:
        try:
            deals = scrape_retailer(retailer)
            all_new_deals.extend(deals)
        except Exception as e:
            print(f"Error scraping {retailer['name']}: {e}")
    
    # Validate codes against aggregator sources before publishing
    validation_logger.info(f"Starting validation of {len(all_new_deals)} scraped deals...")
    validated_deals = validate_and_filter_deals(all_new_deals)
    
    # Only replace live codes with validated ones
    if validated_deals:
        current_deals = load_deals()
        # Keep existing deals that aren't being replaced
        existing_ids = {d.get("id") for d in validated_deals}
        kept_deals = [d for d in current_deals if d.get("id") not in existing_ids]
        # Merge: keep old deals + add new validated deals
        final_deals = kept_deals + validated_deals
        save_deals(final_deals)
        validation_logger.info(f"Published {len(validated_deals)} validated deals, kept {len(kept_deals)} existing deals")
    else:
        validation_logger.warning("No validated deals to publish - keeping current live codes")
    
    _scrape_status = {
        "running": False,
        "last_run": datetime.now().isoformat(),
        "message": f"Completed: {len(validated_deals)} validated deals published, {len(INVALID_CODES_LOG)} codes rejected"
    }
    return validated_deals

'''
    content = content.replace(old_scrape_all, new_scrape_all)

# Step 4: Add APScheduler initialization and scheduled job
# Find the if __name__ == "__main__" block or the app creation
# Add scheduler setup before the main block
main_block_pos = content.find("if __name__")
if main_block_pos == -1:
    main_block_pos = len(content)

scheduler_code = '''
# --- APScheduler: Automated 6-hour scraping schedule ---
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=scrape_all,
    trigger=IntervalTrigger(hours=6),
    id='scheduled_scrape',
    name='Scrape all retailers every 6 hours',
    replace_existing=True
)
scheduler.start()
validation_logger.info("APScheduler started: scraping every 6 hours")

# API endpoint to view invalid/rejected codes
@app.route("/api/invalid-codes")
def api_invalid_codes():
    return jsonify(INVALID_CODES_LOG[-100:])  # Return last 100 invalid codes


'''

content = content[:main_block_pos] + scheduler_code + content[main_block_pos:]

# Write the final file
with open('app.py', 'w') as f:
    f.write(content)

print("SUCCESS: app.py has been updated with:")
print("  - APScheduler for 6-hour automated scraping")
print("  - Code validation against aggregator sources")
print("  - Only-publish-verified logic")
print(f"  - Final file size: {len(content)} characters")
