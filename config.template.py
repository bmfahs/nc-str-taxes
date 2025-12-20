# NC Tax Reporter Configuration Template
# Copy this to config.py and fill in your details
# config.py is in .gitignore and won't be committed

# Personal Information
FILER_NAME = "Your Name"
FILER_EMAIL = "your.email@example.com"
FILER_PHONE = "555-555-5555"
SIGNER_TITLE = "Owner"
SIGNATURE_IMAGE_PATH = None  # Path to transparent PNG/JPG of signature

# NC DOR Account Details
NC_ACCOUNT_ID = "YOUR_ACCOUNT_ID"
NC_TAX_ID = "YOUR_TAX_ID"

# =============================================================================
# DATA SOURCE CONFIGURATION
# =============================================================================
# Choose ONE method: API (recommended) or CSV files

# Option 1: OwnerRez API (Recommended)
# ------------------------------------
# This fetches all bookings (Airbnb, VRBO, Direct) automatically from OwnerRez.
# Requires: OwnerRez account with API access and Airbnb Transaction Sync enabled.
#
# To set up:
# 1. Log into OwnerRez
# 2. Go to: Settings > Advanced Tools > Developer/API Settings
# 3. Create a Personal Access Token
# 4. Copy the token (starts with pt_) - you only see it once!
# 5. Fill in the values below

OWNERREZ_API = {
    "enabled": False,  # Set to True to use API instead of CSV files
    "email": "your.ownerrez.email@example.com",
    "token": "pt_your_personal_access_token_here",
    "property_id": None,  # Optional: filter to specific property ID
}

# Option 2: Manual CSV Files (Fallback)
# -------------------------------------
# If API is disabled or fails, the program will look for CSV files here.
# Export from Airbnb and OwnerRez manually each month.

DATA_PATHS = {
    "airbnb_csv": "./data/airbnb_transactions.csv",
    "ownerrez_csv": "./data/ownerrez_booking_summary.csv",
}

# Airbnb User ID (for CSV export URL reference)
AIRBNB_USER_ID = "YOUR_AIRBNB_USER_ID"

# =============================================================================
# TAX CONFIGURATION
# =============================================================================

# Marketplace Facilitators (these collect/remit tax on your behalf in NC)
# Sales through these platforms go on Line 2 as deductions
MARKETPLACE_FACILITATORS = [
    "Airbnb",
    "VRBO",
    "Booking.com",
]

# Warren County Configuration
WARREN_COUNTY = {
    "name": "Warren County",
    "state": "NC",
    "occupancy_tax_rate": 0.05,  # 5% per Warren County form
    "submission_email": "nikkidickerson@warrencountync.gov",
    "submission_address": "Warren County Finance Department\n548 West Ridgeway Street\nWarrenton, NC 27589",
}

# Property Information (for Warren County form)
PROPERTY = {
    "name": "Your Property Name",  # Name of Accommodation on form
    "address": "123 Main Street",  # Your mailing address
    "city": "Warrenton",
    "state": "NC",
    "zip": "27589",
}

# NC Tax Rates (verify current rates at ncdor.gov)
NC_TAX_RATES = {
    "state_sales_tax": 0.0475,
    "local_sales_tax": 0.0225,
    "combined_rate": 0.07,
}
