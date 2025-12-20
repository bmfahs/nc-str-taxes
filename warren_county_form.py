#!/usr/bin/env python3
"""
Warren County Occupancy Tax Form Filler
Fills in the Warren County Occupancy Tax Report PDF form.
"""

import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Path to the PDF skill scripts (Legacy, unused)
# PDF_SKILL_PATH = "/mnt/skills/public/pdf/scripts"


def get_script_path():
    """Get the directory containing this script."""
    return Path(__file__).parent.resolve()


def fill_warren_county_form(
    output_path: str,
    report_month: str,  # e.g., "January 2025"
    gross_receipts: Decimal,
    third_party_collected: Decimal,
    adjustments: Decimal = Decimal('0.00'),
    property_name: str = "",
    mailing_address: str = "",
    city: str = "",
    state: str = "NC",
    zip_code: str = "",
    telephone: str = "",
    title: str = "Owner",
    date: str = None,
    signature_image_path: str = None,
    debug: bool = False,
) -> dict:
    """
    Fill in the Warren County Occupancy Tax Report PDF form.
    
    Returns dict with:
        - success: bool
        - output_path: str (path to filled PDF)
        - tax_due: Decimal
        - message: str
    """
    script_dir = get_script_path()
    template_pdf = script_dir / "warren_county_form_template.pdf"
    fields_template = script_dir / "warren_county_form_fields.json"
    
    if not template_pdf.exists():
        return {
            "success": False,
            "output_path": None,
            "tax_due": Decimal('0.00'),
            "message": f"Template PDF not found: {template_pdf}"
        }
    
    if not fields_template.exists():
        return {
            "success": False,
            "output_path": None,
            "tax_due": Decimal('0.00'),
            "message": f"Fields template not found: {fields_template}"
        }
    
    # Calculate form values
    net_taxable = gross_receipts - third_party_collected
    tax_due = (net_taxable * Decimal('0.05')).quantize(Decimal('0.01'))
    total_remitted = tax_due + adjustments
    
    if date is None:
        date = datetime.now().strftime("%m/%d/%Y")
    
    # Load fields template
    with open(fields_template, 'r') as f:
        fields_data = json.load(f)
    
    # Map field IDs to values
    field_values = {
        "name_of_accommodation": property_name,
        "mailing_address": mailing_address,
        "telephone": telephone,
        "city": city,
        "state": state,
        "zip": zip_code,
        "reporting_month": report_month,
        "line1_gross_receipts": f"{gross_receipts:,.2f}",
        "line2_third_party": f"{third_party_collected:,.2f}",
        "line3_net_taxable": f"{net_taxable:,.2f}",
        "line4_tax_due": f"{tax_due:,.2f}",
        "line5_adjustments": f"{adjustments:,.2f}" if adjustments else "",
        "line6_total_remitted": f"{total_remitted:,.2f}",
        "title": title,
        "date": date,
    }
    
    # Update fields with values
    for field in fields_data["form_fields"]:
        field_id = field.get("field_id", "")
        if field_id == "signature" and signature_image_path:
             field["entry_text"]["image_path"] = signature_image_path
        elif field_id in field_values:
            field["entry_text"]["text"] = field_values[field_id]
    
    # Fill the PDF using local utils
    try:
        from pdf_utils import fill_pdf_with_coordinates
        
        # Ensure output directory exists
        output_path = os.path.abspath(output_path)
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Get page dimensions from JSON if available
        page_config = fields_data.get("pages", [{}])[0]
        img_width = page_config.get("image_width", 772)
        img_height = page_config.get("image_height", 1000)

        success = fill_pdf_with_coordinates(
            template_path=template_pdf,
            output_path=output_path,
            fields_data=fields_data.get("form_fields", []),
            source_image_width=img_width,
            source_image_height=img_height
        )
        
        if not success:
             return {
                "success": False,
                "output_path": None,
                "tax_due": tax_due,
                "message": "Failed to generate PDF (check logs)"
            }

        return {
            "success": True,
            "output_path": output_path,
            "tax_due": tax_due,
            "total_remitted": total_remitted,
            "message": f"Form filled successfully. Tax due: ${tax_due:,.2f}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "output_path": None,
            "tax_due": tax_due,
            "message": f"Error filling form: {str(e)}"
        }


def main():
    """Test the form filler with sample data."""
    output_path = str(get_script_path() / "reports" / "warren_county_test.pdf")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    result = fill_warren_county_form(
        output_path=output_path,
        report_month="January 2025",
        gross_receipts=Decimal('3170.00'),
        third_party_collected=Decimal('2870.00'),
        property_name="Lakeside Tranquility",
        mailing_address="123 Main St",
        city="Warrenton",
        state="NC",
        zip_code="27589",
        telephone="650-469-3374",
    )
    
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
