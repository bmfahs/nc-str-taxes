#!/usr/bin/env python3
"""
NC Tax Reporter - Automates monthly tax reporting for short-term rentals
Generates reports for:
  - NC E-500 Sales Tax Return (www.ncdor.gov)
  - Warren County Occupancy Tax (with auto-filled PDF form)

Data sources (in order of preference):
  1. OwnerRez API (includes Airbnb via Transaction Sync)
  2. Manual CSV files (fallback)
"""

import csv
import os
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import config
from warren_county_form import fill_warren_county_form


@dataclass
class Booking:
    """Represents a single booking/reservation."""
    confirmation_code: str
    start_date: datetime
    end_date: datetime
    gross_earnings: Decimal
    occupancy_taxes: Decimal
    source: str  # 'Airbnb', 'VRBO', 'Direct', etc.
    property_name: Optional[str] = None
    
    @property
    def is_marketplace_facilitated(self) -> bool:
        """Check if booking was through a marketplace that collects NC tax."""
        return self.source in config.MARKETPLACE_FACILITATORS


@dataclass
class MonthlyTaxReport:
    """Aggregated tax data for a specific month."""
    year: int
    month: int
    bookings: list = field(default_factory=list)
    
    @property
    def period_str(self) -> str:
        return f"{self.year}-{self.month:02d}"
    
    @property
    def period_display(self) -> str:
        return datetime(self.year, self.month, 1).strftime("%B %Y")
    
    # E-500 Line Items
    @property
    def line1_gross_receipts(self) -> Decimal:
        """Line 1: NC Gross Receipts - Total from all NC short-term rentals."""
        return sum(b.gross_earnings for b in self.bookings)
    
    @property
    def line2_sales_for_resale(self) -> Decimal:
        """Line 2: Sales for Resale - Marketplace-facilitated sales (deduction)."""
        return sum(b.gross_earnings for b in self.bookings if b.is_marketplace_facilitated)
    
    @property
    def line3_net_taxable(self) -> Decimal:
        """Line 3: Net taxable amount (Line 1 - Line 2)."""
        return self.line1_gross_receipts - self.line2_sales_for_resale
    
    @property
    def direct_booking_receipts(self) -> Decimal:
        """Direct bookings where YOU must collect/remit tax."""
        return sum(b.gross_earnings for b in self.bookings if not b.is_marketplace_facilitated)
    
    # Warren County Occupancy Tax
    @property
    def warren_county_gross(self) -> Decimal:
        """Total gross for Warren County occupancy tax."""
        return self.line1_gross_receipts
    
    @property
    def warren_county_tax_collected(self) -> Decimal:
        """Occupancy tax already collected by marketplaces."""
        return sum(b.occupancy_taxes for b in self.bookings if b.is_marketplace_facilitated)


def parse_currency(value: str) -> Decimal:
    """Parse currency string to Decimal."""
    if not value or value.strip() == '':
        return Decimal('0.00')
    # Remove currency symbols, commas, and whitespace
    cleaned = value.replace('$', '').replace(',', '').replace(' ', '').strip()
    if cleaned == '' or cleaned == '-':
        return Decimal('0.00')
    return Decimal(cleaned).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def parse_date(date_str: str) -> datetime:
    """Parse date string in various formats."""
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y/%m/%d",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")


def load_airbnb_csv(filepath: str) -> list[Booking]:
    """
    Load Airbnb transaction history CSV.
    Expected columns: Confirmation code, Start date, End date, Gross earnings, Occupancy taxes
    """
    bookings = []
    
    if not os.path.exists(filepath):
        print(f"Warning: Airbnb CSV not found at {filepath}")
        return bookings
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Handle various column name formats
            conf_code = row.get('Confirmation code', row.get('Confirmation Code', ''))
            start_date = row.get('Start date', row.get('Start Date', ''))
            end_date = row.get('End date', row.get('End Date', ''))
            gross = row.get('Gross earnings', row.get('Gross Earnings', '0'))
            taxes = row.get('Occupancy taxes', row.get('Occupancy Taxes', '0'))
            
            if not conf_code or not start_date:
                continue
                
            try:
                booking = Booking(
                    confirmation_code=conf_code.strip(),
                    start_date=parse_date(start_date),
                    end_date=parse_date(end_date) if end_date else parse_date(start_date),
                    gross_earnings=parse_currency(gross),
                    occupancy_taxes=parse_currency(taxes),
                    source='Airbnb'
                )
                bookings.append(booking)
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping row due to error: {e}")
                continue
    
    print(f"Loaded {len(bookings)} bookings from Airbnb CSV")
    return bookings


def load_ownerrez_csv(filepath: str) -> list[Booking]:
    """
    Load OwnerRez Booking Summary CSV.
    Adapts to OwnerRez export format - uses 'Total' field.
    """
    bookings = []
    
    if not os.path.exists(filepath):
        print(f"Warning: OwnerRez CSV not found at {filepath}")
        return bookings
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # OwnerRez column mappings (adjust based on your export)
            conf_code = row.get('Confirmation', row.get('Code', row.get('Booking ID', '')))
            start_date = row.get('Arrive', row.get('Check-in', row.get('Start', '')))
            end_date = row.get('Depart', row.get('Check-out', row.get('End', '')))
            total = row.get('Total', row.get('Gross', '0'))
            source = row.get('Source', row.get('Channel', 'VRBO'))
            taxes = row.get('Occupancy Tax', row.get('Taxes Collected', '0'))
            property_name = row.get('Property', row.get('Listing', ''))
            
            if not start_date:
                continue
            
            # Determine source - normalize common channel names
            source_normalized = source.strip().upper()
            if 'VRBO' in source_normalized or 'HOMEAWAY' in source_normalized:
                source = 'VRBO'
            elif 'AIRBNB' in source_normalized:
                source = 'Airbnb'
            elif 'DIRECT' in source_normalized or source_normalized == '':
                source = 'Direct'
            else:
                source = source.strip()
            
            try:
                booking = Booking(
                    confirmation_code=conf_code.strip() if conf_code else f"OR-{len(bookings)}",
                    start_date=parse_date(start_date),
                    end_date=parse_date(end_date) if end_date else parse_date(start_date),
                    gross_earnings=parse_currency(total),
                    occupancy_taxes=parse_currency(taxes),
                    source=source,
                    property_name=property_name
                )
                bookings.append(booking)
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping OwnerRez row due to error: {e}")
                continue
    
    print(f"Loaded {len(bookings)} bookings from OwnerRez CSV")
    return bookings


def load_bookings_from_api(year: int, month: int) -> tuple[list[Booking], bool]:
    """
    Load bookings from OwnerRez API for the specified month.
    
    If API is enabled and OwnerRez is connected to Airbnb (via Transaction Sync),
    this will return ALL bookings including Airbnb, VRBO, and Direct.
    
    Returns:
        Tuple of (list of bookings, success boolean)
    """
    # Check if API is configured
    api_config = getattr(config, 'OWNERREZ_API', {})
    if not api_config.get('enabled', False):
        return [], False
    
    try:
        from ownerrez_api import OwnerRezAPI, parse_ownerrez_bookings, AuthenticationError, APIError
    except ImportError:
        print("Warning: ownerrez_api module not found")
        return [], False
    
    email = api_config.get('email', '')
    token = api_config.get('token', '')
    property_id = api_config.get('property_id')
    
    if not email or not token:
        print("Warning: OwnerRez API credentials not configured")
        return [], False
    
    print("Fetching bookings from OwnerRez API...")
    
    try:
        api = OwnerRezAPI(email, token, property_id)
        raw_bookings = api.get_bookings_for_month(year, month)
        parsed = parse_ownerrez_bookings(raw_bookings)
        
        # Convert to our Booking dataclass format
        bookings = []
        for b in parsed:
            if not b.get('arrive'):
                continue
                
            try:
                booking = Booking(
                    confirmation_code=str(b.get('confirmation', '')),
                    start_date=datetime.combine(b['arrive'], datetime.min.time()),
                    end_date=datetime.combine(b.get('depart', b['arrive']), datetime.min.time()),
                    gross_earnings=Decimal(str(b.get('total', 0))).quantize(Decimal('0.01')),
                    occupancy_taxes=Decimal(str(b.get('occupancy_tax', 0))).quantize(Decimal('0.01')),
                    source=b.get('source', 'Direct'),
                    property_name=b.get('property', '')
                )
                bookings.append(booking)
            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping API booking due to error: {e}")
                continue
        
        print(f"✓ Loaded {len(bookings)} bookings from OwnerRez API")
        return bookings, True
        
    except AuthenticationError as e:
        print(f"API Authentication failed: {e}")
        print("  Check your email and token in config.py")
        return [], False
    except APIError as e:
        print(f"API Error: {e}")
        return [], False
    except Exception as e:
        print(f"Unexpected error fetching from API: {e}")
        return [], False


def filter_bookings_by_month(bookings: list[Booking], year: int, month: int) -> list[Booking]:
    """Filter bookings to those with start_date in the specified month."""
    return [b for b in bookings if b.start_date.year == year and b.start_date.month == month]


def generate_e500_report(report: MonthlyTaxReport) -> str:
    """Generate NC E-500 form data summary."""
    output = []
    output.append("=" * 70)
    output.append(f"NC E-500 SALES TAX RETURN - {report.period_display}")
    output.append("=" * 70)
    output.append(f"Filer: {config.FILER_NAME}")
    output.append(f"Account ID: {config.NC_ACCOUNT_ID}")
    output.append(f"Tax ID: {config.NC_TAX_ID}")
    output.append("-" * 70)
    output.append("")
    output.append("E-500 LINE ITEMS:")
    output.append("")
    output.append(f"  Line 1 - NC Gross Receipts:        ${report.line1_gross_receipts:>12,.2f}")
    output.append(f"           (Total from all NC STR)")
    output.append("")
    output.append(f"  Line 2 - Sales for Resale:         ${report.line2_sales_for_resale:>12,.2f}")
    output.append(f"           (Marketplace-facilitated: Airbnb, VRBO)")
    output.append("")
    output.append(f"  Line 3 - Net Taxable (L1 - L2):    ${report.line3_net_taxable:>12,.2f}")
    output.append(f"           (Direct bookings YOU must remit tax on)")
    output.append("")
    output.append("-" * 70)
    output.append("BREAKDOWN BY SOURCE:")
    
    by_source = {}
    for b in report.bookings:
        by_source.setdefault(b.source, Decimal('0.00'))
        by_source[b.source] += b.gross_earnings
    
    for source, total in sorted(by_source.items()):
        facilitated = "✓ Marketplace" if source in config.MARKETPLACE_FACILITATORS else "  Direct"
        output.append(f"  {source:20} ${total:>12,.2f}  {facilitated}")
    
    output.append("")
    
    if report.line3_net_taxable > 0:
        tax_due = report.line3_net_taxable * Decimal(str(config.NC_TAX_RATES['combined_rate']))
        output.append(f"ESTIMATED TAX DUE (Direct @ {config.NC_TAX_RATES['combined_rate']*100:.2f}%): ${tax_due:,.2f}")
    else:
        output.append("TAX DUE: $0.00 (All sales marketplace-facilitated)")
    
    output.append("")
    return "\n".join(output)


def generate_warren_county_report(report: MonthlyTaxReport) -> str:
    """Generate Warren County Occupancy Tax report."""
    # Calculate values per Warren County form logic
    line1_gross = report.line1_gross_receipts
    line2_third_party = report.warren_county_tax_collected  # This is occupancy tax collected by OTAs
    
    # For Warren County form, Line 2 is "Sales a third party has collected" (the gross, not tax)
    # Meaning marketplace-facilitated sales
    line2_sales = report.line2_sales_for_resale  # Marketplace sales (Airbnb, VRBO gross)
    line3_net = line1_gross - line2_sales
    line4_tax_due = (line3_net * Decimal('0.05')).quantize(Decimal('0.01'))
    
    output = []
    output.append("=" * 70)
    output.append(f"WARREN COUNTY OCCUPANCY TAX - {report.period_display}")
    output.append("=" * 70)
    output.append(f"Filer: {config.FILER_NAME}")
    output.append(f"Email: {config.FILER_EMAIL}")
    output.append(f"Phone: {config.FILER_PHONE}")
    output.append("-" * 70)
    output.append("")
    output.append("WARREN COUNTY FORM VALUES:")
    output.append("")
    output.append(f"  (1) Gross Room/Rental Receipts:    ${line1_gross:>12,.2f}")
    output.append(f"  (2) Sales third party collected:   ${line2_sales:>12,.2f}")
    output.append(f"      (Airbnb + VRBO gross sales)")
    output.append(f"  (3) Net Taxable (1) - (2):         ${line3_net:>12,.2f}")
    output.append(f"  (4) Occupancy Tax Due (3) x 5%:    ${line4_tax_due:>12,.2f}")
    output.append(f"  (5) Adjustments:                   $        0.00")
    output.append(f"  (6) Total Remitted:                ${line4_tax_due:>12,.2f}")
    output.append("")
    
    if line4_tax_due == 0:
        output.append(">>> TAX DUE: $0.00 - Email form to:")
        output.append(f"    {config.WARREN_COUNTY['submission_email']}")
    else:
        output.append(f">>> TAX DUE: ${line4_tax_due:,.2f} - Mail form with check to:")
        output.append(f"    {config.WARREN_COUNTY['submission_address']}")
    
    output.append("")
    output.append("-" * 70)
    output.append("AIRBNB TRANSACTIONS:")
    output.append("")
    
    airbnb_bookings = [b for b in report.bookings if b.source == 'Airbnb']
    for b in sorted(airbnb_bookings, key=lambda x: x.start_date):
        output.append(f"  {b.confirmation_code:15} {b.start_date.strftime('%m/%d/%Y'):>10} - "
                     f"{b.end_date.strftime('%m/%d/%Y'):>10}  "
                     f"${b.gross_earnings:>10,.2f}  Tax: ${b.occupancy_taxes:>8,.2f}")
    
    if not airbnb_bookings:
        output.append("  (No Airbnb bookings this period)")
    
    output.append("")
    output.append("-" * 70)
    output.append("VRBO/OTHER TRANSACTIONS:")
    output.append("")
    
    other_bookings = [b for b in report.bookings if b.source != 'Airbnb']
    for b in sorted(other_bookings, key=lambda x: x.start_date):
        output.append(f"  {b.confirmation_code:15} {b.start_date.strftime('%m/%d/%Y'):>10} - "
                     f"{b.end_date.strftime('%m/%d/%Y'):>10}  "
                     f"${b.gross_earnings:>10,.2f}  Tax: ${b.occupancy_taxes:>8,.2f}")
    
    if not other_bookings:
        output.append("  (No VRBO/other bookings this period)")
    
    output.append("")
    return "\n".join(output)


def generate_booking_detail(report: MonthlyTaxReport) -> str:
    """Generate detailed booking list for records."""
    output = []
    output.append("=" * 70)
    output.append(f"BOOKING DETAIL - {report.period_display}")
    output.append("=" * 70)
    output.append(f"{'Conf Code':<15} {'Dates':<25} {'Source':<10} {'Gross':>12} {'Tax':>10}")
    output.append("-" * 70)
    
    for b in sorted(report.bookings, key=lambda x: x.start_date):
        dates = f"{b.start_date.strftime('%m/%d')} - {b.end_date.strftime('%m/%d/%Y')}"
        output.append(f"{b.confirmation_code:<15} {dates:<25} {b.source:<10} "
                     f"${b.gross_earnings:>10,.2f} ${b.occupancy_taxes:>8,.2f}")
    
    output.append("-" * 70)
    output.append(f"{'TOTALS':<15} {'':<25} {'':<10} "
                 f"${report.line1_gross_receipts:>10,.2f} ${report.warren_county_tax_collected:>8,.2f}")
    output.append("")
    return "\n".join(output)


def main():
    """Main entry point."""
    print("\n" + "=" * 70)
    print("NC TAX REPORTER - Short-Term Rental Tax Filing Assistant")
    print("=" * 70 + "\n")
    
    # Determine report period
    if len(sys.argv) >= 3:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
    else:
        # Default to previous month
        today = datetime.now()
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
    
    print(f"Generating reports for: {datetime(year, month, 1).strftime('%B %Y')}\n")
    
    # Load booking data - try API first, then CSV fallback
    all_bookings = []
    data_source = "CSV"
    
    # Try OwnerRez API first (includes Airbnb via Transaction Sync)
    api_bookings, api_success = load_bookings_from_api(year, month)
    
    if api_success and api_bookings:
        # Filter API results to be certain we are only using the reporting month
        all_bookings = filter_bookings_by_month(api_bookings, year, month)
        data_source = "OwnerRez API"
    else:
        # Fallback to CSV files
        if api_success:
            print("No bookings found via API, trying CSV files...")
        else:
            api_config = getattr(config, 'OWNERREZ_API', {})
            if api_config.get('enabled', False):
                print("API fetch failed, falling back to CSV files...")
            
        airbnb_path = config.DATA_PATHS.get('airbnb_csv', './data/airbnb_transactions.csv')
        ownerrez_path = config.DATA_PATHS.get('ownerrez_csv', './data/ownerrez_booking_summary.csv')
        
        all_bookings.extend(load_airbnb_csv(airbnb_path))
        all_bookings.extend(load_ownerrez_csv(ownerrez_path))
        
        # Filter to reporting month (CSV files may contain multiple months)
        all_bookings = filter_bookings_by_month(all_bookings, year, month)
    
    if not all_bookings:
        print("\nNo bookings found! Please check your configuration:")
        api_config = getattr(config, 'OWNERREZ_API', {})
        print("\nOption 1: Enable OwnerRez API (recommended)")
        if not api_config.get('enabled', False):
            print("  Set OWNERREZ_API['enabled'] = True in config.py")
            print("  Add your email and API token")
            print("  (Get token from: OwnerRez > Settings > Developer/API Settings)")
        else:
            print("  API is enabled but no bookings were returned")
            print("  Check your credentials and property settings")
        
        print("\nOption 2: Use CSV files")
        print(f"  - Airbnb CSV: {config.DATA_PATHS.get('airbnb_csv')}")
        print(f"  - OwnerRez CSV: {config.DATA_PATHS.get('ownerrez_csv')}")
        print("\n  Export steps:")
        print("  1. Export Airbnb transactions from:")
        airbnb_user_id = getattr(config, 'AIRBNB_USER_ID', 'YOUR_USER_ID')
        print(f"     https://www.airbnb.com/users/transaction_history/{airbnb_user_id}/paid")
        print("  2. Export OwnerRez Booking Summary by Month")
        print("  3. Place CSV files in the paths configured in config.py")
        sys.exit(1)
    
    print(f"\nData source: {data_source}")
    print(f"Bookings for {datetime(year, month, 1).strftime('%B %Y')}: {len(all_bookings)}")
    
    # Create report (API bookings are already filtered to the month)
    report = MonthlyTaxReport(year=year, month=month, bookings=all_bookings)
    
    # Generate and print reports
    print(generate_e500_report(report))
    print(generate_warren_county_report(report))
    print(generate_booking_detail(report))
    
    # Save reports to file
    output_dir = Path('./reports')
    output_dir.mkdir(exist_ok=True)
    
    report_filename = output_dir / f"nc_tax_report_{year}_{month:02d}.txt"
    with open(report_filename, 'w') as f:
        f.write(generate_e500_report(report))
        f.write("\n")
        f.write(generate_warren_county_report(report))
        f.write("\n")
        f.write(generate_booking_detail(report))
    
    print(f"Report saved to: {report_filename}")
    
    # Generate Warren County PDF form
    print("\n" + "-" * 70)
    print("GENERATING WARREN COUNTY PDF FORM...")
    print("-" * 70)
    
    # Get property info from config (with defaults)
    property_info = getattr(config, 'PROPERTY', {})
    warren_info = getattr(config, 'WARREN_COUNTY', {})
    
    # Calculate Warren County form values
    line2_sales = report.line2_sales_for_resale  # Marketplace sales
    
    pdf_filename = output_dir / f"warren_county_{year}_{month:02d}.pdf"
    pdf_result = fill_warren_county_form(
        output_path=str(pdf_filename),
        report_month=report.period_display,
        gross_receipts=report.line1_gross_receipts,
        third_party_collected=line2_sales,
        property_name=property_info.get('name', 'Short-Term Rental'),
        mailing_address=property_info.get('address', ''),
        city=property_info.get('city', ''),
        state=property_info.get('state', 'NC'),
        zip_code=property_info.get('zip', ''),
        telephone=config.FILER_PHONE,
        title="Owner",
    )
    
    if pdf_result['success']:
        print(f"✓ Warren County PDF form saved to: {pdf_filename}")
        print(f"  Tax due: ${pdf_result['tax_due']:,.2f}")
        
        if pdf_result['tax_due'] == 0:
            print(f"\n  ACTION: Email the PDF to {warren_info.get('submission_email', 'Warren County')}")
        else:
            print(f"\n  ACTION: Print, sign, and mail with ${pdf_result['tax_due']:,.2f} check to:")
            print(f"          {warren_info.get('submission_address', 'Warren County Finance')}")
    else:
        print(f"✗ Failed to generate PDF: {pdf_result['message']}")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print(f"1. File E-500 at: https://www.ncdor.gov")
    print(f"   - Log in with Account ID: {config.NC_ACCOUNT_ID}")
    print(f"2. Submit Warren County Occupancy Tax form (PDF generated above)")
    print(f"3. Keep this report for your records")
    print("")


if __name__ == "__main__":
    main()
