#!/usr/bin/env python3
"""
Extreme Detail Logo Vectorization Engine - Pixel-perfect vectorization
"""

import cv2
import numpy as np
from PIL import Image
from skimage import morphology, measure
import io
import base64
import math


class ExtremeDetailVectorizer:
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

    def create_pixel_perfect_mask(self, image_array):
        """Create a pixel-perfect binary mask with zero loss of detail"""
        img_type, alpha, rgb_data = self.analyze_image_content(image_array)

        if img_type == "transparent_background":
            # Use alpha channel to determine logo areas
            # Extremely sensitive threshold for maximum detail
            logo_mask = alpha > 5  # Catch even 2% opacity pixels

        else:
            # For images without transparency, use the most detailed approach possible
            if len(rgb_data.shape) == 3:
                # Convert to grayscale for analysis
                gray = cv2.cvtColor(rgb_data, cv2.COLOR_RGB2GRAY)
            else:
                gray = rgb_data

            # Multi-level detailed thresholding approach

            # Method 1: Otsu's thresholding
            threshold_value, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Method 2: Triangle thresholding (good for uneven illumination)
            threshold_triangle, binary_triangle = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_TRIANGLE)

            # Method 3: Multiple adaptive thresholds with different block sizes
            adaptive_small = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                 cv2.THRESH_BINARY, 7, 2)  # Small features
            adaptive_medium = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                  cv2.THRESH_BINARY, 15, 2)  # Medium features
            adaptive_large = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                 cv2.THRESH_BINARY, 31, 2)  # Large features

            # Method 4: Canny edge detection for ultra-fine details
            edges = cv2.Canny(gray, 30, 100)  # Lower thresholds for more edges

            # Dilate edges slightly to create regions
            kernel_small = np.ones((2,2), np.uint8)
            edge_regions = cv2.dilate(edges, kernel_small, iterations=1)

            # Method 5: Gradient-based approach
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
            gradient_binary = (gradient_magnitude > np.percentile(gradient_magnitude, 70)).astype(np.uint8) * 255

            # Combine all methods intelligently
            # Start with the best global method
            white_ratio_otsu = np.sum(binary_otsu == 255) / binary_otsu.size
            white_ratio_triangle = np.sum(binary_triangle == 255) / binary_triangle.size

            # Choose the best base method
            if abs(white_ratio_otsu - 0.5) < abs(white_ratio_triangle - 0.5):
                base_binary = binary_otsu
                base_ratio = white_ratio_otsu
            else:
                base_binary = binary_triangle
                base_ratio = white_ratio_triangle

            # Create final combination
            combined = base_binary.copy()

            # Add details from adaptive thresholds
            # Use smaller block size results where there are edges
            edge_mask = edge_regions > 0
            combined[edge_mask] = adaptive_small[edge_mask]

            # Add gradient information for very fine details
            gradient_mask = gradient_binary > 0
            strong_edges = edge_regions > 0
            fine_detail_mask = gradient_mask & ~strong_edges  # Fine details not captured by edges
            combined[fine_detail_mask] = 0  # Assume fine details are dark (logo parts)

            # Smart subject detection based on image characteristics
            logo_mask = self.detect_subject_areas(combined, gray, base_ratio)

        # Absolutely minimal cleanup - preserve every possible detail
        # Only remove single isolated pixels
        cleaned_mask = morphology.remove_small_objects(logo_mask, min_size=1)
        # Don't fill any holes - preserve internal structure

        return cleaned_mask

    def detect_subject_areas(self, binary_image, gray_image, white_ratio):
        """Intelligently detect which areas represent the subject vs background"""

        # Analyze image characteristics to determine subject
        height, width = binary_image.shape

        # Method 1: Edge density analysis
        # Subjects typically have more edges/detail than plain backgrounds
        edges = cv2.Canny(gray_image, 30, 100)

        # Create masks for white and black areas
        white_areas = binary_image == 255
        black_areas = binary_image == 0

        # Count edges in each area type
        white_edge_density = np.sum(edges[white_areas]) / np.sum(white_areas) if np.sum(white_areas) > 0 else 0
        black_edge_density = np.sum(edges[black_areas]) / np.sum(black_areas) if np.sum(black_areas) > 0 else 0

        # Method 2: Center bias - subjects are often more centered
        center_region = np.zeros_like(binary_image)

        # Create center-weighted mask (subjects often in center third)
        y_start, y_end = height // 3, 2 * height // 3
        x_start, x_end = width // 3, 2 * width // 3
        center_region[y_start:y_end, x_start:x_end] = 1

        white_center_ratio = np.sum((white_areas & center_region)) / np.sum(center_region) if np.sum(center_region) > 0 else 0
        black_center_ratio = np.sum((black_areas & center_region)) / np.sum(center_region) if np.sum(center_region) > 0 else 0

        # Method 3: Connected component analysis
        white_labels, white_num = measure.label(white_areas, return_num=True)
        black_labels, black_num = measure.label(black_areas, return_num=True)

        # Calculate average component size
        white_avg_size = np.sum(white_areas) / white_num if white_num > 0 else 0
        black_avg_size = np.sum(black_areas) / black_num if black_num > 0 else 0

        # Decision logic: combine all factors
        subject_is_white = False

        # Factor 1: Edge density (subjects usually have more detail)
        edge_score = white_edge_density - black_edge_density

        # Factor 2: Center positioning
        center_score = white_center_ratio - black_center_ratio

        # Factor 3: Component size (subjects often have larger connected areas)
        size_score = white_avg_size - black_avg_size

        # Factor 4: Area ratio (slight bias against extremely dominant areas)
        area_bias = 0.5 - white_ratio  # Favor minority if extreme ratio

        # Weighted decision
        total_score = (edge_score * 2.0 + center_score * 1.5 + size_score * 0.001 + area_bias * 0.5)

        if total_score > 0:
            subject_is_white = True

        # Return the appropriate mask
        if subject_is_white:
            return white_areas
        else:
            return black_areas

    def extract_extreme_detail_contours(self, logo_mask):
        """Extract contours with absolute maximum detail preservation"""
        # Convert boolean mask to uint8
        mask_uint8 = (logo_mask * 255).astype(np.uint8)

        # Find ALL contours including the tiniest details
        contours, hierarchy = cv2.findContours(
            mask_uint8,
            cv2.RETR_TREE,  # Get everything including nested structures
            cv2.CHAIN_APPROX_NONE  # Keep EVERY single point
        )

        # Minimal filtering - keep almost everything
        min_area = 1  # Keep even single-pixel features
        filtered_contours = []
        contour_hierarchy = []

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area >= min_area and len(contour) >= 3:
                # Very permissive filtering
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    # Accept almost any shape
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.001:  # Extremely permissive
                        filtered_contours.append(contour)
                        contour_hierarchy.append(hierarchy[0][i] if hierarchy is not None and len(hierarchy) > 0 else None)
                    else:
                        # Even accept weird shapes if they have decent area
                        if area > 5:
                            filtered_contours.append(contour)
                            contour_hierarchy.append(hierarchy[0][i] if hierarchy is not None and len(hierarchy) > 0 else None)

        return filtered_contours, contour_hierarchy

    def no_simplify_contours(self, contours, epsilon_factor=0.0001):
        """Minimal or no simplification to preserve every detail"""
        simplified_contours = []

        for contour in contours:
            if len(contour) < 3:
                continue

            # Ultra-minimal epsilon for absolute detail preservation
            epsilon = epsilon_factor * cv2.arcLength(contour, True)

            # For extreme detail, often don't simplify at all
            if len(contour) <= 10 or epsilon_factor <= 0.0001:
                # Keep original contour
                simplified_contours.append(contour)
            else:
                simplified = cv2.approxPolyDP(contour, epsilon, True)
                if len(simplified) >= 3:
                    simplified_contours.append(simplified)
                else:
                    # If simplification destroys the contour, keep original
                    simplified_contours.append(contour)

        return simplified_contours

    def create_extreme_detail_svg(self, contours, hierarchy, image_shape):
        """Create SVG with maximum possible detail preservation"""
        height, width = image_shape[:2]

        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .logo-path {{
        fill: #000000;
        stroke: none;
        fill-rule: evenodd;
        shape-rendering: geometricPrecision;
        vector-effect: non-scaling-stroke;
      }}
      .logo-hole {{
        fill: #ffffff;
        stroke: none;
        fill-rule: evenodd;
        shape-rendering: geometricPrecision;
      }}
    </style>
  </defs>
  <g class="logo-group">
'''

        for i, contour in enumerate(contours):
            if len(contour) < 3:
                continue

            # Determine if this is a hole
            is_hole = False
            if hierarchy is not None and i < len(hierarchy):
                h = hierarchy[i]
                if h is not None and len(h) > 3 and h[3] != -1:
                    is_hole = True

            # Create ultra-precise path data
            points = contour.reshape(-1, 2)

            if len(points) == 0:
                continue

            # Start path with maximum precision
            path_data = f"M {points[0][0]:.3f} {points[0][1]:.3f}"

            # Add every single point as a line (no curves to avoid any loss)
            for point in points[1:]:
                path_data += f" L {point[0]:.3f} {point[1]:.3f}"

            # Close path
            path_data += " Z"

            # Choose class based on whether it's a hole
            css_class = "logo-hole" if is_hole else "logo-path"

            svg_content += f'    <path d="{path_data}" class="{css_class}"/>\n'

        svg_content += '''  </g>
</svg>'''

        return svg_content

    def vectorize_extreme_detail_logo(self, image_array, epsilon_factor=0.0001):
        """Complete extreme detail vectorization pipeline"""
        try:
            # Ensure we have a valid numpy array
            if not isinstance(image_array, np.ndarray):
                image_array = np.array(image_array)

            # Step 1: Create pixel-perfect mask
            logo_mask = self.create_pixel_perfect_mask(image_array)

            # Step 2: Extract extreme detail contours
            contours, hierarchy = self.extract_extreme_detail_contours(logo_mask)

            if not contours:
                raise Exception("No logo contours found. The image might be completely transparent or uniform.")

            # Step 3: No/minimal simplification
            simplified_contours = self.no_simplify_contours(contours, epsilon_factor)

            if not simplified_contours:
                raise Exception("No valid contours after processing.")

            # Step 4: Create extreme detail SVG
            svg_content = self.create_extreme_detail_svg(simplified_contours, hierarchy, image_array.shape)

            # Step 5: Create preview images
            preview_mask = (logo_mask * 255).astype(np.uint8)

            # Create colored preview
            if len(image_array.shape) == 3 and image_array.shape[2] >= 3:
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
                'original_contour_count': len(contours),
                'detail_level': 'extreme'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def image_to_base64(self, image_array):
        """Convert numpy array to base64 string"""
        if len(image_array.shape) == 3 and image_array.shape[2] == 4:
            image = Image.fromarray(image_array, 'RGBA')
        elif len(image_array.shape) == 3:
            image = Image.fromarray(image_array, 'RGB')
        else:
            image = Image.fromarray(image_array, 'L')

        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()