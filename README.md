# NC Tax Reporter

Automated monthly tax reporting for North Carolina short-term rentals. Generates reports for:
- **NC E-500 Sales Tax Return** (filed at www.ncdor.gov)
- **Warren County Occupancy Tax** (auto-filled PDF form)

## Quick Start

1. **Setup configuration:**
   ```bash
   cp config.template.py config.py
   # Edit config.py with your personal details
   ```

2. **Choose your data source:**

   ### Option A: OwnerRez API (Recommended)
   If you use OwnerRez with Airbnb Transaction Sync enabled, this fetches ALL bookings automatically:
   
   1. Log into OwnerRez
   2. Go to: **Settings > Advanced Tools > Developer/API Settings**
   3. Create a **Personal Access Token**
   4. Copy the token (you only see it once!)
   5. Update `config.py`:
      ```python
      OWNERREZ_API = {
          "enabled": True,
          "email": "your.email@example.com",
          "token": "pt_your_token_here",
          "property_id": None,  # Optional
      }
      ```

   ### Option B: Manual CSV Export
   Export data manually each month:
   
   **Airbnb:**
   - Go to: https://www.airbnb.com/users/transaction_history/YOUR_USER_ID/paid
   - Export to CSV
   - Save as `./data/airbnb_transactions.csv`

   **VRBO/Direct (via OwnerRez):**
   - Go to OwnerRez → Reports → Booking Summary by Month
   - Export to CSV
   - Save as `./data/ownerrez_booking_summary.csv`

3. **Run the report:**
   ```bash
   # Report for previous month (default)
   python nc_tax_reporter.py
   
   # Report for specific month
   python nc_tax_reporter.py 2025 1    # January 2025
   ```

## How It Works

### Data Flow
```
┌─────────────────────────────────────────────────────────────┐
│                    OwnerRez API                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Airbnb    │ │    VRBO     │ │   Direct    │           │
│  │ Transaction │ │  Bookings   │ │  Bookings   │           │
│  │    Sync     │ │             │ │             │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         └───────────────┼───────────────┘                   │
│                         ▼                                   │
│              Single API Request                             │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  NC Tax Reporter                            │
│  ┌─────────────────┐  ┌──────────────────────────┐         │
│  │ E-500 Report    │  │ Warren County PDF Form   │         │
│  │ (Lines 1-3)     │  │ (Auto-filled)            │         │
│  └─────────────────┘  └──────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### E-500 Form Logic

| Line | Description | Calculation |
|------|-------------|-------------|
| Line 1 | NC Gross Receipts | Total from all NC rentals (Airbnb + VRBO + Direct) |
| Line 2 | Sales for Resale | Marketplace sales (Airbnb, VRBO) - these platforms collect tax |
| Line 3 | Net Taxable | Line 1 - Line 2 (your direct bookings only) |
| Lines 4-12 | Tax Due | Only on direct bookings where YOU collected tax |

**Key Point:** Airbnb and VRBO are "marketplace facilitators" in NC, meaning they collect and remit sales tax on your behalf. You only owe tax on direct bookings.

### Warren County Occupancy Tax (5%)

The program automatically generates a **filled PDF form** ready for submission:

| Line | Description | Calculation |
|------|-------------|-------------|
| Line 1 | Gross Room/Rental Receipts | Total rental income |
| Line 2 | Sales third party collected | Marketplace gross (Airbnb, VRBO) |
| Line 3 | Net Taxable | Line 1 - Line 2 |
| Line 4 | Tax Due | Line 3 × 5% |
| Line 6 | Total Remitted | Line 4 (unless adjustments) |

**Submission:**
- **Tax = $0**: Email the PDF to nikkidickerson@warrencountync.gov
- **Tax > $0**: Print PDF, sign, mail with check to:
  ```
  Warren County Finance Department
  548 West Ridgeway Street
  Warrenton, NC 27589
  ```

**Due Date:** 20th of the following month (must file even if $0 due)

## File Structure

```
nc_tax_reporter/
├── nc_tax_reporter.py              # Main program
├── warren_county_form.py           # PDF form filler module
├── warren_county_form_template.pdf # Blank Warren County form
├── warren_county_form_fields.json  # Form field positions
├── config.py                       # Your private config (gitignored)
├── config.template.py              # Template for config
├── .gitignore
├── README.md
├── data/
│   ├── airbnb_transactions.csv           # Your Airbnb export
│   ├── airbnb_transactions.sample.csv    # Sample format
│   ├── ownerrez_booking_summary.csv      # Your OwnerRez export
│   └── ownerrez_booking_summary.sample.csv
└── reports/
    ├── nc_tax_report_YYYY_MM.txt         # Generated text report
    └── warren_county_YYYY_MM.pdf         # Filled Warren County PDF form
```

## CSV Format Reference

### Airbnb Export
```csv
Confirmation code,Start date,End date,Gross earnings,Occupancy taxes
HMABCD1234,01/05/2025,01/08/2025,$450.00,$13.50
```

### OwnerRez Export
```csv
Confirmation,Arrive,Depart,Total,Source,Occupancy Tax,Property
VR-12345,01/02/2025,01/05/2025,380.00,VRBO,11.40,Lakeside Tranquility
```

## Monthly Workflow

1. **Early in the month:**
   - Export Airbnb transaction history for previous month
   - Export OwnerRez Booking Summary for previous month
   - Place CSVs in `./data/`

2. **Run the report:**
   ```bash
   python nc_tax_reporter.py
   ```

3. **File taxes:**
   - **E-500**: Log into NC DOR (www.ncdor.gov), enter Line 1, 2, 3 values
   - **Warren County**: Submit the generated PDF form:
     - If $0 due: Email `reports/warren_county_YYYY_MM.pdf`
     - If tax due: Print, sign, mail with check

4. **Save for records:**
   - Text reports and PDFs auto-save to `./reports/` folder

## Notes

- The program uses **start date** to determine which month a booking belongs to
- Amounts are rounded to the nearest cent
- The program handles various date formats automatically
- Direct bookings (not through Airbnb/VRBO) show tax you need to remit yourself

## Troubleshooting

**"No bookings found"**
- Check that CSV files exist in `./data/`
- Verify column headers match expected format (see samples)
- Check date range - bookings are filtered by month

**Wrong totals**
- Verify you're not double-counting (Airbnb export + OwnerRez export may overlap)
- For OwnerRez, filter to VRBO/Direct only if Airbnb is separate

## Security

The following are gitignored to protect your private information:
- `config.py` - Your personal details
- `data/*.csv` - Your financial data
- `reports/` - Generated reports
