#!/usr/bin/env python3
"""
Detailed Logo Vectorization Engine - Preserves fine details and curves
"""

import cv2
import numpy as np
from PIL import Image
from skimage import morphology, measure
import io
import base64
import math


class DetailedVectorizer:
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

    def create_detailed_mask(self, image_array):
        """Create a high-detail binary mask preserving fine features"""
        img_type, alpha, rgb_data = self.analyze_image_content(image_array)

        if img_type == "transparent_background":
            # Use alpha channel to determine logo areas
            # More sensitive threshold for fine details
            logo_mask = alpha > 30  # Lower threshold to catch semi-transparent edges

        else:
            # For images without transparency, use advanced edge-preserving thresholding
            if len(rgb_data.shape) == 3:
                # Convert to grayscale for analysis
                gray = cv2.cvtColor(rgb_data, cv2.COLOR_RGB2GRAY)
            else:
                gray = rgb_data

            # Use multiple thresholding approaches and combine them

            # Method 1: Otsu's thresholding
            threshold_value, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Method 2: Adaptive thresholding for local details
            binary_adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                   cv2.THRESH_BINARY, 15, 2)

            # Method 3: Edge-based approach for fine details
            edges = cv2.Canny(gray, 50, 150)
            # Dilate edges to create regions
            kernel = np.ones((3,3), np.uint8)
            edge_regions = cv2.dilate(edges, kernel, iterations=1)

            # Combine all methods
            # Start with Otsu
            combined = binary_otsu.copy()

            # Add adaptive threshold details
            white_ratio_otsu = np.sum(binary_otsu == 255) / binary_otsu.size
            white_ratio_adaptive = np.sum(binary_adaptive == 255) / binary_adaptive.size

            # If Otsu and adaptive disagree significantly, use adaptive for detail areas
            if abs(white_ratio_otsu - white_ratio_adaptive) > 0.2:
                # Use edge regions to guide where to apply adaptive threshold
                edge_mask = edge_regions > 0
                combined[edge_mask] = binary_adaptive[edge_mask]

            # Smart subject detection based on image characteristics
            logo_mask = self.detect_subject_areas(combined, gray, white_ratio_otsu)

        # Minimal cleanup to preserve details
        # Only remove very tiny artifacts
        cleaned_mask = morphology.remove_small_objects(logo_mask, min_size=5)
        cleaned_mask = morphology.remove_small_holes(cleaned_mask, area_threshold=10)

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
        center_y, center_x = height // 2, width // 2
        center_region = np.zeros_like(binary_image)

        # Create center-weighted mask (subjects often in center third)
        y_start, y_end = height // 3, 2 * height // 3
        x_start, x_end = width // 3, 2 * width // 3
        center_region[y_start:y_end, x_start:x_end] = 1

        white_center_ratio = np.sum((white_areas & center_region)) / np.sum(center_region) if np.sum(center_region) > 0 else 0
        black_center_ratio = np.sum((black_areas & center_region)) / np.sum(center_region) if np.sum(center_region) > 0 else 0

        # Method 3: Connected component analysis
        # Subjects often have fewer, larger connected components
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

    def extract_detailed_contours(self, logo_mask):
        """Extract contours with maximum detail preservation"""
        # Convert boolean mask to uint8
        mask_uint8 = (logo_mask * 255).astype(np.uint8)

        # Find ALL contours including internal ones
        contours, hierarchy = cv2.findContours(
            mask_uint8,
            cv2.RETR_TREE,  # Get all contours including holes
            cv2.CHAIN_APPROX_NONE  # Keep ALL points for maximum detail
        )

        # Filter contours more carefully
        min_area = 5  # Much smaller minimum area
        filtered_contours = []
        contour_hierarchy = []

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area >= min_area and len(contour) >= 3:
                # Check if it's a reasonable shape
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    # More lenient shape filtering
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.005:  # Very permissive
                        filtered_contours.append(contour)
                        contour_hierarchy.append(hierarchy[0][i] if hierarchy is not None and len(hierarchy) > 0 else None)

        return filtered_contours, contour_hierarchy

    def simplify_contours_detailed(self, contours, epsilon_factor=0.005):
        """Minimal simplification to preserve detail"""
        simplified_contours = []

        for contour in contours:
            if len(contour) < 3:
                continue

            # Much smaller epsilon for detail preservation
            epsilon = epsilon_factor * cv2.arcLength(contour, True)

            # Don't simplify if contour is already small
            if len(contour) <= 20:
                simplified_contours.append(contour)
            else:
                simplified = cv2.approxPolyDP(contour, epsilon, True)
                if len(simplified) >= 3:
                    simplified_contours.append(simplified)
                else:
                    # If simplification removes too much, keep original
                    simplified_contours.append(contour)

        return simplified_contours

    def create_bezier_path(self, contour):
        """Convert contour points to smooth Bezier curves"""
        if len(contour) < 4:
            # Too few points for curves, use straight lines
            return self.create_linear_path(contour)

        points = contour.reshape(-1, 2)

        # Start path
        path_data = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

        # Create smooth curves through points
        for i in range(1, len(points) - 2, 3):
            if i + 2 < len(points):
                # Cubic Bezier curve
                cp1 = points[i]
                cp2 = points[i + 1] if i + 1 < len(points) else points[i]
                end = points[i + 2] if i + 2 < len(points) else points[-1]

                path_data += f" C {cp1[0]:.2f} {cp1[1]:.2f}, {cp2[0]:.2f} {cp2[1]:.2f}, {end[0]:.2f} {end[1]:.2f}"
            else:
                # Line to remaining points
                for j in range(i, len(points)):
                    path_data += f" L {points[j][0]:.2f} {points[j][1]:.2f}"
                break

        # Close path
        path_data += " Z"
        return path_data

    def create_linear_path(self, contour):
        """Create linear path with all points"""
        points = contour.reshape(-1, 2)

        if len(points) == 0:
            return ""

        # Start path
        path_data = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

        # Add all points as lines
        for point in points[1:]:
            path_data += f" L {point[0]:.2f} {point[1]:.2f}"

        # Close path
        path_data += " Z"
        return path_data

    def create_detailed_svg(self, contours, hierarchy, image_shape, use_curves=True):
        """Create detailed SVG with curves and fine details"""
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
        vector-effect: non-scaling-stroke;
      }}
      .logo-hole {{
        fill: #ffffff;
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

            # Determine if this is a hole (inner contour)
            is_hole = False
            if hierarchy is not None and i < len(hierarchy):
                # Check hierarchy to determine if this is a hole
                h = hierarchy[i]
                if h is not None and len(h) > 3 and h[3] != -1:  # Has parent
                    is_hole = True

            # Create path data
            if use_curves and len(contour) > 10:
                path_data = self.create_bezier_path(contour)
            else:
                path_data = self.create_linear_path(contour)

            # Choose class based on whether it's a hole
            css_class = "logo-hole" if is_hole else "logo-path"

            svg_content += f'    <path d="{path_data}" class="{css_class}"/>\n'

        svg_content += '''  </g>
</svg>'''

        return svg_content

    def vectorize_detailed_logo(self, image_array, epsilon_factor=0.005, use_curves=True):
        """Complete detailed vectorization pipeline"""
        try:
            # Ensure we have a valid numpy array
            if not isinstance(image_array, np.ndarray):
                image_array = np.array(image_array)

            # Step 1: Create detailed mask
            logo_mask = self.create_detailed_mask(image_array)

            # Step 2: Extract detailed contours
            contours, hierarchy = self.extract_detailed_contours(logo_mask)

            if not contours:
                raise Exception("No logo contours found. The image might be too simple or complex.")

            # Step 3: Minimal simplification
            simplified_contours = self.simplify_contours_detailed(contours, epsilon_factor)

            if not simplified_contours:
                raise Exception("No valid contours after simplification.")

            # Step 4: Create detailed SVG
            svg_content = self.create_detailed_svg(simplified_contours, hierarchy, image_array.shape, use_curves)

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
                'original_contour_count': len(contours),
                'detail_level': 'high'
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