from PIL import Image
import os

def make_white_background_transparent(image_path, output_path, threshold=200):
    """
    Makes the white background of an image transparent.

    Args:
        image_path (str): Path to the input image file.
        output_path (str): Path to save the output transparent image file.
        threshold (int): RGB value threshold to consider a pixel as "white".
                         Pixels with R, G, B values all above this threshold will be made transparent.
    """
    try:
        img = Image.open(image_path)
        img = img.convert("RGBA") # Ensure image is in RGBA mode for transparency

        datas = img.getdata()

        newData = []
        for item in datas:
            # If the pixel is close to white (R, G, B all above threshold)
            if item[0] > threshold and item[1] > threshold and item[2] > threshold:
                newData.append((255, 255, 255, 0)) # Change to transparent
            else:
                newData.append(item)
        
        img.putdata(newData)
        img.save(output_path, "PNG")
        print(f"Successfully created transparent image: {output_path}")

    except FileNotFoundError:
        print(f"Error: Input image file not found at {image_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    input_file = "data/signature.png"
    output_file = "data/signature_transparent.png"
    
    # Create the 'data' directory if it doesn't exist
    os.makedirs(os.path.dirname(input_file), exist_ok=True)

    # Example usage:
    # First, create a dummy signature.png for demonstration if it doesn't exist
    if not os.path.exists(input_file):
        try:
            # Create a simple dummy image with a white background and some black text
            dummy_img = Image.new('RGB', (200, 100), color = 'white')
            from PIL import ImageDraw, ImageFont
            d = ImageDraw.Draw(dummy_img)
            try:
                # Try to load a common font
                font = ImageFont.truetype("arial.ttf", 30)
            except IOError:
                # Fallback if arial.ttf is not found
                font = ImageFont.load_default()
            d.text((10,10), "Signature", fill=(0,0,0), font=font)
            dummy_img.save(input_file)
            print(f"Created dummy {input_file} for demonstration.")
        except Exception as e:
            print(f"Could not create dummy {input_file}: {e}")
            print("Please ensure data/signature.png exists or create it manually with a white background.")
            exit()

    make_white_background_transparent(input_file, output_file)
