"""
PDF Utilities for NC Tax Reporter.
Handles overlaying text onto existing PDF templates using pypdf and reportlab.
"""

import io
from pathlib import Path
from typing import Dict, List, Union

from pypdf import PdfReader, PdfWriter, PageObject
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def create_overlay_pdf(
    fields_data: List[Dict],
    page_width: float = 612.0,  # Standard letter width in points
    page_height: float = 792.0, # Standard letter height in points
    source_image_height: float = 1000.0, # Height of coordinate system in JSON
    source_image_width: float = 772.0,   # Width of coordinate system in JSON
) -> io.BytesIO:
    """
    Create a temporary PDF containing only the text fields.
    
    Args:
        fields_data: List of field dicts containing 'entry_text' and 'entry_bounding_box'
        page_width: Width of the target PDF page (points)
        page_height: Height of the target PDF page (points)
        source_image_height: Height of the source coordinate system (to flip Y axis)
        source_image_width: Width of the source coordinate system (to scale X axis)
    
    Returns:
        BytesIO object containing the overlay PDF
    """
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    # Calculate scaling factors
    # The JSON coordinates are based on an image analysis (772x1000)
    # The PDF page is likely Letter (612x792) or similar
    # We need to scale the coordinates to match the PDF page size
    scale_x = page_width / source_image_width
    scale_y = page_height / source_image_height
    
    for field in fields_data:
        entry_text = field.get('entry_text', {})
        text_content = entry_text.get('text', '')
        
        if not text_content:
            continue
            
        bbox = field.get('entry_bounding_box', [])
        if len(bbox) != 4:
            continue
            
        # JSON Source: [x_min, y_min, x_max, y_max] (Top-Left Origin)
        # x_min, y_min is top-left corner of box
        x_json = bbox[0]
        y_json_bottom = bbox[3] # y_max in JSON is the bottom of the box in Top-Left coords
        
        # Convert to ReportLab (Bottom-Left Origin) and Scale
        # In ReportLab, (0,0) is bottom-left.
        # scaled_y = page_height - (y_json * scale_y)
        
        # Calculate x position
        # Add a small padding (e.g., 2px scaled)
        x = (x_json * scale_x) + 2
        
        # Calculate y position
        # For text drawing, we specify the baseline.
        # The box bottom in JSON (y_max) corresponds to the baseline area roughly.
        # We flip Y: new_y = Height - old_y
        y = page_height - (y_json_bottom * scale_y) + 2 # Add explicit padding for baseline adjustment
        
        font_size = entry_text.get('font_size', 11)
        
        # Setup font
        can.setFont("Helvetica", font_size)
        can.drawString(x, y, str(text_content))
        
    can.save()
    packet.seek(0)
    return packet


def fill_pdf_with_coordinates(
    template_path: Union[str, Path],
    output_path: Union[str, Path],
    fields_data: List[Dict],
    source_image_width: int = 772,
    source_image_height: int = 1000,
) -> bool:
    """
    Overlay text onto a PDF template based on coordinates.
    """
    try:
        # Load the template
        template_pdf = PdfReader(template_path)
        if len(template_pdf.pages) < 1:
            raise ValueError("Template PDF has no pages")
            
        first_page = template_pdf.pages[0]
        page_width = float(first_page.mediabox.width)
        page_height = float(first_page.mediabox.height)
        
        # Generate the overlay
        overlay_pdf_stream = create_overlay_pdf(
            fields_data=fields_data,
            page_width=page_width,
            page_height=page_height,
            source_image_height=float(source_image_height),
            source_image_width=float(source_image_width)
        )
        overlay_pdf = PdfReader(overlay_pdf_stream)
        overlay_page = overlay_pdf.pages[0]
        
        # Merge overlay onto template
        first_page.merge_page(overlay_page)
        
        # Write output
        writer = PdfWriter()
        writer.add_page(first_page)
        
        # Add remaining pages if any
        for i in range(1, len(template_pdf.pages)):
            writer.add_page(template_pdf.pages[i])
            
        with open(output_path, 'wb') as f:
            writer.write(f)
            
        return True
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return False
