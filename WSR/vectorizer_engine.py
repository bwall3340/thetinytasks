#!/usr/bin/env python3
"""
Improved Logo Vectorization Engine
"""

import cv2
import numpy as np
from PIL import Image
from skimage import morphology
import io
import base64


class ImprovedVectorizer:
    def __init__(self):
        pass

    def analyze_image_content(self, image_array):
        """Analyze image to determine best vectorization approach"""
        if len(image_array.shape) == 3 and image_array.shape[2] == 4:
            # RGBA image - has transparency
            alpha = image_array[:, :, 3]
            rgb = image_array[:, :, :3]

            # Check if there are actually transparent pixels
            has_transparency = (alpha < 255).any()

            if has_transparency:
                return "transparent_background", alpha, rgb
            else:
                return "solid_background", None, rgb
        else:
            # RGB or grayscale - no transparency
            return "solid_background", None, image_array

    def create_logo_mask(self, image_array):
        """Create a proper binary mask of the logo areas"""
        img_type, alpha, rgb_data = self.analyze_image_content(image_array)

        if img_type == "transparent_background":
            # Use alpha channel to determine logo areas
            # Logo areas are where alpha > threshold
            logo_mask = alpha > 50  # Adjust threshold as needed

        else:
            # For images without transparency, use intelligent thresholding
            if len(rgb_data.shape) == 3:
                # Convert to grayscale for analysis
                gray = cv2.cvtColor(rgb_data, cv2.COLOR_RGB2GRAY)
            else:
                gray = rgb_data

            # Use adaptive thresholding or Otsu's method
            # First try Otsu's automatic thresholding
            threshold_value, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # If the threshold seems wrong (too much or too little), use adaptive
            white_ratio = np.sum(binary == 255) / binary.size

            if white_ratio > 0.8 or white_ratio < 0.1:
                # Use adaptive thresholding
                binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                             cv2.THRESH_BINARY, 11, 2)

            # For logos, we usually want dark areas to be the logo
            # So invert if needed based on which areas are likely logo
            if white_ratio > 0.5:
                binary = 255 - binary  # Invert

            logo_mask = binary == 255

        # Clean up the mask
        # Remove small noise but preserve main shapes
        cleaned_mask = morphology.remove_small_objects(logo_mask, min_size=50)
        cleaned_mask = morphology.remove_small_holes(cleaned_mask, area_threshold=200)

        return cleaned_mask

    def extract_logo_contours(self, logo_mask):
        """Extract contours from the logo mask"""
        # Convert boolean mask to uint8
        mask_uint8 = (logo_mask * 255).astype(np.uint8)

        # Find contours
        contours, hierarchy = cv2.findContours(
            mask_uint8,
            cv2.RETR_EXTERNAL,  # Only external contours
            cv2.CHAIN_APPROX_SIMPLE
        )

        # Filter contours by area and perimeter
        min_area = 100
        filtered_contours = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                # Also check if contour is not too thin/weird
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    # Accept reasonable shapes (not super thin lines)
                    if circularity > 0.01:  # Adjust as needed
                        filtered_contours.append(contour)

        return filtered_contours

    def simplify_contours(self, contours, epsilon_factor=0.02):
        """Simplify contours for cleaner vectors"""
        simplified_contours = []

        for contour in contours:
            # Calculate epsilon based on contour perimeter
            epsilon = epsilon_factor * cv2.arcLength(contour, True)

            # Simplify the contour
            simplified = cv2.approxPolyDP(contour, epsilon, True)

            # Only keep contours with at least 3 points
            if len(simplified) >= 3:
                simplified_contours.append(simplified)

        return simplified_contours

    def create_svg(self, contours, image_shape, stroke_width=0):
        """Create SVG from contours with proper styling"""
        height, width = image_shape[:2]

        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .logo-shape {{
        fill: #000000;
        stroke: none;
        fill-rule: evenodd;
      }}
    </style>
  </defs>
  <g class="logo-group">
'''

        for i, contour in enumerate(contours):
            if len(contour) < 3:
                continue

            # Build path data
            path_parts = []

            # Move to first point
            first_point = contour[0][0]
            path_parts.append(f"M {first_point[0]:.1f} {first_point[1]:.1f}")

            # Add lines to subsequent points
            for j in range(1, len(contour)):
                point = contour[j][0]
                path_parts.append(f"L {point[0]:.1f} {point[1]:.1f}")

            # Close path
            path_parts.append("Z")

            path_data = " ".join(path_parts)

            svg_content += f'    <path d="{path_data}" class="logo-shape"/>\n'

        svg_content += '''  </g>
</svg>'''

        return svg_content

    def vectorize_logo(self, image_array, epsilon_factor=0.02):
        """Complete vectorization pipeline"""
        try:
            # Step 1: Create logo mask
            logo_mask = self.create_logo_mask(image_array)

            # Step 2: Extract contours
            contours = self.extract_logo_contours(logo_mask)

            if not contours:
                raise Exception("No logo contours found. The image might be too simple or complex.")

            # Step 3: Simplify contours
            simplified_contours = self.simplify_contours(contours, epsilon_factor)

            if not simplified_contours:
                raise Exception("No valid contours after simplification.")

            # Step 4: Create SVG
            svg_content = self.create_svg(simplified_contours, image_array.shape)

            # Step 5: Create preview images
            preview_mask = (logo_mask * 255).astype(np.uint8)

            # Create colored preview if original was colored
            if len(image_array.shape) == 3 and image_array.shape[2] >= 3:
                # Create RGBA preview
                preview_rgba = np.zeros((image_array.shape[0], image_array.shape[1], 4), dtype=np.uint8)
                preview_rgba[:, :, :3] = image_array[:, :, :3] if image_array.shape[2] >= 3 else np.stack([image_array]*3, axis=2)
                preview_rgba[:, :, 3] = np.where(logo_mask, 255, 0)
            else:
                preview_rgba = np.zeros((image_array.shape[0], image_array.shape[1], 4), dtype=np.uint8)
                gray_data = image_array if len(image_array.shape) == 2 else image_array[:,:,0]
                preview_rgba[:, :, :3] = np.stack([gray_data]*3, axis=2)
                preview_rgba[:, :, 3] = np.where(logo_mask, 255, 0)

            return {
                'success': True,
                'svg_content': svg_content,
                'preview_rgba': preview_rgba,
                'binary_mask': preview_mask,
                'contour_count': len(simplified_contours),
                'original_contour_count': len(contours)
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def image_to_base64(self, image_array):
        """Convert numpy array to base64 string"""
        if len(image_array.shape) == 3 and image_array.shape[2] == 4:
            # RGBA
            image = Image.fromarray(image_array, 'RGBA')
        elif len(image_array.shape) == 3:
            # RGB
            image = Image.fromarray(image_array, 'RGB')
        else:
            # Grayscale
            image = Image.fromarray(image_array, 'L')

        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()