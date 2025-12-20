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
    debug: bool = False,
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
    scale_x = page_width / source_image_width
    scale_y = page_height / source_image_height
    
    for field in fields_data:
        entry_text = field.get('entry_text', {})
        text_content = entry_text.get('text', '')
        x_offset = field.get('x_offset', 0)
        y_offset = field.get('y_offset', 0)
        
        bbox = field.get('entry_bounding_box', [])
        if len(bbox) != 4:
            continue
            
        x_min, y_min, x_max, y_max = bbox
        
        # Scale the bounding box
        scaled_x_min = x_min * scale_x
        scaled_y_min = page_height - (y_min * scale_y)
        scaled_x_max = x_max * scale_x
        scaled_y_max = page_height - (y_max * scale_y)
        
        if debug:
            can.setStrokeColorRGB(1, 0, 0) # Red
            can.rect(scaled_x_min + x_offset, scaled_y_max + y_offset, scaled_x_max - scaled_x_min, scaled_y_min - scaled_y_max, stroke=1, fill=0)

        # Handle Image
        image_path = entry_text.get('image_path')
        if image_path and Path(image_path).exists():
            # Calculate width/height of the box
            box_width = scaled_x_max - scaled_x_min
            box_height = scaled_y_min - scaled_y_max
            
            # Draw image (preserve aspect ratio usually, but here we just fit to box or center?)
            # Let's clean up coordinate calculation first
            img_x = scaled_x_min + x_offset
            img_y = scaled_y_max + y_offset # ReportLab draws from bottom-up, scaled_y_max is actually the bottom of the box in PDF coords
            
            try:
                can.drawImage(image_path, img_x, img_y, width=box_width, height=box_height, mask='auto', preserveAspectRatio=True, anchor='c')
            except Exception as e:
                print(f"Error drawing image {image_path}: {e}")
            continue

        if not text_content:
            continue
            
        font_size = entry_text.get('font_size', 11)
            
        # For text drawing, we specify the baseline.
        x = scaled_x_min + 2 + x_offset
        y = scaled_y_min - (font_size * 0.7) + y_offset
        
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
            source_image_width=float(source_image_width),
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
