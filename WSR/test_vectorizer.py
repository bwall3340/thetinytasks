#!/usr/bin/env python3
"""
Advanced Test Vectorization Engine - Clean and Sharp Logo Edges
Implements sophisticated edge smoothing and curve optimization
"""

import cv2
import numpy as np
from PIL import Image
from skimage import morphology, measure, filters
import io
import base64
import math
from scipy import ndimage
from scipy.interpolate import splprep, splev
from scipy.spatial.distance import pdist, squareform


class AdvancedTestVectorizer:
    def __init__(self):
        self.smoothing_enabled = True
        self.corner_detection_enabled = True
        self.curve_optimization_enabled = True

    def analyze_image_content(self, image_array):
        """Enhanced image analysis with edge detection"""
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

    def create_enhanced_mask(self, image_array):
        """Create high-quality mask with edge preservation and gap-aware smoothing"""
        img_type, alpha, rgb_data = self.analyze_image_content(image_array)

        if img_type == "transparent_background":
            # Use alpha channel with edge enhancement
            logo_mask = alpha > 10  # Slightly higher threshold for cleaner edges

            # Apply morphological smoothing to alpha edges
            if self.smoothing_enabled:
                # Smooth the alpha channel itself before creating mask
                alpha_smooth = filters.gaussian(alpha.astype(float), sigma=0.5)
                logo_mask = alpha_smooth > 25
        else:
            # Advanced thresholding with edge preservation
            if len(rgb_data.shape) == 3:
                gray = cv2.cvtColor(rgb_data, cv2.COLOR_RGB2GRAY)
            else:
                gray = rgb_data

            # Multi-scale edge-preserving thresholding

            # 1. Edge detection for structure preservation
            edges = cv2.Canny(gray, 30, 80)

            # 2. Bilateral filter for edge-preserving smoothing
            gray_smooth = cv2.bilateralFilter(gray, 9, 75, 75)

            # 3. Adaptive thresholding on smoothed image
            binary_adaptive = cv2.adaptiveThreshold(
                gray_smooth, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 15, 2
            )

            # 4. Otsu on original for global structure
            _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # 5. Combine with edge information
            # Use edges to guide which threshold to trust
            edge_dilated = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=1)

            # Start with Otsu
            combined = binary_otsu.copy()

            # Use adaptive threshold in edge regions for detail preservation
            edge_mask = edge_dilated > 0
            combined[edge_mask] = binary_adaptive[edge_mask]

            # Determine if we need to invert (logos are usually dark)
            white_ratio = np.sum(combined == 255) / combined.size
            if white_ratio > 0.6:
                combined = 255 - combined

            logo_mask = combined == 255

        # Advanced morphological cleaning with gap-aware edge preservation
        # Fix black output: Use moderate mask smoothing, rely on iterative contour smoothing
        if self.smoothing_enabled:
            if hasattr(self, 'iterative_passes') and self.iterative_passes > 2:
                # For high/extreme modes, use minimal mask smoothing and rely on contour iteration
                logo_mask = self.smooth_mask_edges_conservative(logo_mask)
            else:
                # For medium/low modes, use full gap-aware smoothing
                logo_mask = self.smooth_mask_edges_gap_aware(logo_mask)

        return logo_mask

    def smooth_mask_edges(self, mask):
        """Apply sophisticated edge smoothing while preserving sharp corners and fine details"""
        # Convert to float for sub-pixel operations
        mask_float = mask.astype(np.float32)

        # 1. Multi-scale detail detection
        detail_map = self.detect_fine_details(mask_float)

        # 2. Adaptive smoothing based on local complexity
        mask_smooth = self.adaptive_gaussian_smoothing(mask_float, detail_map)

        # 3. Detect corners and important features to preserve
        if self.corner_detection_enabled:
            corners = self.detect_important_corners(mask)

            # Create preservation mask around corners
            corner_preserve = np.zeros_like(mask, dtype=np.uint8)
            if len(corners) > 0:
                for corner in corners:
                    coords = corner.ravel()
                    if len(coords) >= 2:
                        x, y = int(coords[0]), int(coords[1])
                        # Ensure coordinates are within image bounds
                        if 0 <= x < mask.shape[1] and 0 <= y < mask.shape[0]:
                            cv2.circle(corner_preserve, (x, y), 3, 1, -1)

            # Blend: use original near corners, smoothed elsewhere
            mask_smooth = np.where(corner_preserve, mask_float, mask_smooth)

        # 4. Preserve fine details identified in detail map
        detail_threshold = 0.3  # Preserve areas with >30% detail complexity
        high_detail_areas = detail_map > detail_threshold
        mask_smooth = np.where(high_detail_areas, mask_float, mask_smooth)

        # 3. Apply threshold with hysteresis for clean edges
        mask_clean = np.zeros_like(mask_smooth, dtype=bool)

        # High threshold for definite foreground
        high_thresh = 0.7
        # Low threshold for weak edges connected to strong edges
        low_thresh = 0.3

        strong_edges = mask_smooth > high_thresh
        weak_edges = (mask_smooth > low_thresh) & (mask_smooth <= high_thresh)

        # Label connected components of strong edges
        strong_labeled = measure.label(strong_edges)

        # Add weak edges that are connected to strong edges
        for label_id in np.unique(strong_labeled)[1:]:  # Skip 0 (background)
            component = strong_labeled == label_id

            # Dilate the strong component slightly
            dilated = ndimage.binary_dilation(component, iterations=2)

            # Add connected weak edges
            connected_weak = weak_edges & dilated
            mask_clean |= component | connected_weak

        # 4. Final morphological refinement
        # Remove small artifacts
        mask_clean = morphology.remove_small_objects(mask_clean, min_size=20)

        # Fill small holes
        mask_clean = morphology.remove_small_holes(mask_clean, area_threshold=50)

        # Light opening to smooth small irregularities
        kernel = morphology.disk(1)
        mask_clean = morphology.opening(mask_clean, kernel)

        return mask_clean

    def detect_important_corners(self, mask):
        """Detect important corners and sharp features to preserve"""
        try:
            # Convert mask to uint8
            mask_uint8 = (mask * 255).astype(np.uint8)

            # Harris corner detection
            gray_float = mask_uint8.astype(np.float32)
            corners_harris = cv2.cornerHarris(gray_float, 2, 3, 0.04)

            # Check if we found any corners
            if corners_harris.max() == 0:
                return np.array([]).reshape(0, 1, 2)

            # Threshold for corner detection
            corner_threshold = 0.01 * corners_harris.max()
            corner_locations = np.argwhere(corners_harris > corner_threshold)

            if len(corner_locations) == 0:
                return np.array([]).reshape(0, 1, 2)

            # Convert to cv2 format (x, y) and ensure integer coordinates
            corners = corner_locations[:, [1, 0]].astype(np.int32).reshape(-1, 1, 2)

            return corners
        except Exception as e:
            # Return empty array if corner detection fails
            return np.array([]).reshape(0, 1, 2)

    def detect_fine_details(self, mask_float):
        """Detect fine details and small features that need preservation"""
        try:
            # 1. Multi-scale edge detection to find details at different sizes
            edges_fine = cv2.Canny((mask_float * 255).astype(np.uint8), 20, 60)  # Fine edges
            edges_medium = cv2.Canny((mask_float * 255).astype(np.uint8), 40, 120)  # Medium edges
            edges_coarse = cv2.Canny((mask_float * 255).astype(np.uint8), 80, 200)  # Coarse edges

            # 2. Local variance detection for texture details
            kernel_size = 5
            kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size * kernel_size)
            local_mean = cv2.filter2D(mask_float, -1, kernel)
            local_variance = cv2.filter2D(mask_float**2, -1, kernel) - local_mean**2

            # 3. Gradient magnitude for edge strength
            grad_x = cv2.Sobel(mask_float, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(mask_float, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)

            # 4. Laplacian for fine detail detection
            laplacian = cv2.Laplacian(mask_float, cv2.CV_64F, ksize=3)
            laplacian_abs = np.abs(laplacian)

            # 5. Combine all detail indicators
            detail_map = np.zeros_like(mask_float)

            # Normalize each component
            if edges_fine.max() > 0:
                detail_map += (edges_fine / 255.0) * 0.3
            if edges_medium.max() > 0:
                detail_map += (edges_medium / 255.0) * 0.2
            if local_variance.max() > 0:
                detail_map += (local_variance / local_variance.max()) * 0.25
            if gradient_magnitude.max() > 0:
                detail_map += (gradient_magnitude / gradient_magnitude.max()) * 0.15
            if laplacian_abs.max() > 0:
                detail_map += (laplacian_abs / laplacian_abs.max()) * 0.1

            # 6. Apply morphological operations to clean up detail map
            kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            detail_map = cv2.morphologyEx(detail_map, cv2.MORPH_CLOSE, kernel_clean)

            # 7. Smooth the detail map slightly to avoid harsh transitions
            detail_map = filters.gaussian(detail_map, sigma=0.5)

            return np.clip(detail_map, 0, 1)

        except Exception as e:
            # Return zero detail map if detection fails
            return np.zeros_like(mask_float)

    def adaptive_gaussian_smoothing(self, mask_float, detail_map):
        """Apply adaptive Gaussian smoothing based on local detail complexity"""
        try:
            # Create multiple smoothing levels
            smooth_light = filters.gaussian(mask_float, sigma=0.3)    # Minimal smoothing
            smooth_medium = filters.gaussian(mask_float, sigma=0.7)   # Medium smoothing
            smooth_heavy = filters.gaussian(mask_float, sigma=1.2)    # Heavy smoothing

            # Create blending weights based on detail complexity
            # High detail areas get less smoothing, low detail areas get more smoothing
            detail_inverted = 1.0 - detail_map

            # Blend different smoothing levels
            # Areas with fine details (high detail_map) use light smoothing
            # Areas without details (low detail_map) use heavy smoothing
            weight_light = detail_map
            weight_medium = detail_inverted * (1 - detail_inverted)  # Peak at medium detail
            weight_heavy = detail_inverted**2

            # Normalize weights
            total_weight = weight_light + weight_medium + weight_heavy + 1e-8
            weight_light /= total_weight
            weight_medium /= total_weight
            weight_heavy /= total_weight

            # Blend the different smoothing levels
            result = (weight_light * smooth_light +
                     weight_medium * smooth_medium +
                     weight_heavy * smooth_heavy)

            return result

        except Exception as e:
            # Fallback to simple gaussian smoothing
            return filters.gaussian(mask_float, sigma=0.7)

    def smooth_mask_edges_gap_aware(self, mask):
        """Apply gap-aware smoothing that preserves intentional separations between shapes"""
        # Convert to float for sub-pixel operations
        mask_float = mask.astype(np.float32)

        # 1. Detect inter-shape gaps and boundaries
        gap_map, shape_boundaries = self.detect_inter_shape_gaps(mask)

        # 2. Multi-scale detail detection
        detail_map = self.detect_fine_details(mask_float)

        # 3. Adaptive smoothing that respects gaps
        mask_smooth = self.adaptive_gap_aware_smoothing(mask_float, detail_map, gap_map, shape_boundaries)

        # 4. Detect corners and important features to preserve
        if self.corner_detection_enabled:
            corners = self.detect_important_corners(mask)

            # Create preservation mask around corners
            corner_preserve = np.zeros_like(mask, dtype=np.uint8)
            if len(corners) > 0:
                for corner in corners:
                    coords = corner.ravel()
                    if len(coords) >= 2:
                        x, y = int(coords[0]), int(coords[1])
                        # Ensure coordinates are within image bounds
                        if 0 <= x < mask.shape[1] and 0 <= y < mask.shape[0]:
                            cv2.circle(corner_preserve, (x, y), 3, 1, -1)

            # Blend: use original near corners, smoothed elsewhere
            mask_smooth = np.where(corner_preserve, mask_float, mask_smooth)

        # 5. Preserve fine details identified in detail map
        detail_threshold = 0.3
        high_detail_areas = detail_map > detail_threshold
        mask_smooth = np.where(high_detail_areas, mask_float, mask_smooth)

        # 6. Critical: Preserve gap boundaries to maintain shape separation
        gap_boundary_preserve = gap_map > 0.5  # Strong gap indicators
        mask_smooth = np.where(gap_boundary_preserve, mask_float, mask_smooth)

        # 7. Apply threshold with hysteresis for clean edges
        mask_clean = np.zeros_like(mask_smooth, dtype=bool)

        # High threshold for definite foreground
        high_thresh = 0.7
        # Low threshold for weak edges connected to strong edges
        low_thresh = 0.3

        strong_edges = mask_smooth > high_thresh
        weak_edges = (mask_smooth > low_thresh) & (mask_smooth <= high_thresh)

        # Label connected components of strong edges
        strong_labeled = measure.label(strong_edges)

        # Add weak edges that are connected to strong edges
        for label_id in np.unique(strong_labeled)[1:]:  # Skip 0 (background)
            component = strong_labeled == label_id

            # Dilate the strong component slightly
            dilated = ndimage.binary_dilation(component, iterations=2)

            # Add connected weak edges
            connected_weak = weak_edges & dilated
            mask_clean |= component | connected_weak

        # 8. Final morphological refinement with gap preservation
        # Remove small artifacts but preserve intentional gaps
        mask_clean = morphology.remove_small_objects(mask_clean, min_size=20)

        # Fill small holes but NOT gaps between shapes
        # Use gap map to avoid filling intentional separations
        holes_to_fill = ~mask_clean & ~(gap_map > 0.3)  # Don't fill where gaps are detected
        filled_holes = morphology.remove_small_holes(holes_to_fill, area_threshold=50)
        mask_clean = mask_clean | (filled_holes & ~(gap_map > 0.3))

        # Light opening to smooth small irregularities, avoiding gap areas
        kernel = morphology.disk(1)
        mask_smooth_final = morphology.opening(mask_clean, kernel)

        # Restore gap boundaries that might have been affected
        mask_smooth_final = mask_smooth_final & ~(gap_map > 0.7)

        return mask_smooth_final

    def detect_inter_shape_gaps(self, mask):
        """Detect gaps between separate shapes that should be preserved (optimized)"""
        try:
            # 1. Find connected components (separate shapes)
            labeled_shapes = measure.label(mask)
            num_shapes = labeled_shapes.max()

            if num_shapes <= 1:
                # Single shape or no shapes - no gaps to preserve
                return np.zeros_like(mask, dtype=np.float32), []

            # Quick optimization: if image is too large, skip complex gap detection
            if mask.shape[0] * mask.shape[1] > 100000:  # 316x316 pixels
                print("Large image detected, using simplified gap detection")
                return self.detect_gaps_simplified(mask, labeled_shapes, num_shapes)

            # 2. Create distance transform to find gaps
            distance_from_fg = ndimage.distance_transform_edt(~mask)

            # 3. Optimized gap detection using vectorized operations
            gap_candidates = np.zeros_like(mask, dtype=np.float32)

            # Get all background pixels
            bg_coords = np.argwhere(~mask)

            # Limit processing to reasonable number of pixels
            if len(bg_coords) > 5000:
                # Sample background pixels for large images
                step = len(bg_coords) // 5000
                bg_coords = bg_coords[::step]

            for bg_y, bg_x in bg_coords:
                if distance_from_fg[bg_y, bg_x] > 0 and distance_from_fg[bg_y, bg_x] < 15:
                    # Check if this background pixel is between different shapes
                    search_radius = min(5, int(distance_from_fg[bg_y, bg_x]) + 1)

                    # Get neighborhood
                    y_min = max(0, bg_y - search_radius)
                    y_max = min(mask.shape[0], bg_y + search_radius + 1)
                    x_min = max(0, bg_x - search_radius)
                    x_max = min(mask.shape[1], bg_x + search_radius + 1)

                    neighborhood_mask = mask[y_min:y_max, x_min:x_max]
                    neighborhood_labels = labeled_shapes[y_min:y_max, x_min:x_max]

                    # Find unique shapes in neighborhood
                    nearby_shapes = set(neighborhood_labels[neighborhood_mask].flatten())
                    nearby_shapes.discard(0)  # Remove background

                    # If background pixel is near multiple shapes, it's likely a gap
                    if len(nearby_shapes) >= 2:
                        gap_strength = min(1.0, distance_from_fg[bg_y, bg_x] / 10.0)
                        gap_candidates[bg_y, bg_x] = gap_strength

            # 4. Smooth gap map to create coherent gap regions
            if gap_candidates.max() > 0:
                gap_map = filters.gaussian(gap_candidates, sigma=1.0)
            else:
                gap_map = gap_candidates

            # 5. Find shape boundaries for additional preservation
            shape_boundaries = []
            for shape_id in range(1, min(num_shapes + 1, 10)):  # Limit to 10 shapes max
                shape_mask = labeled_shapes == shape_id
                # Find boundary pixels using faster method
                eroded = ndimage.binary_erosion(shape_mask, iterations=1)
                boundary = shape_mask & ~eroded
                shape_boundaries.append(boundary)

            return gap_map, shape_boundaries

        except Exception as e:
            print(f"Gap detection error: {e}")
            return np.zeros_like(mask, dtype=np.float32), []

    def detect_gaps_simplified(self, mask, labeled_shapes, num_shapes):
        """Simplified gap detection for large images"""
        try:
            # Use morphological operations for faster gap detection
            gap_map = np.zeros_like(mask, dtype=np.float32)

            # For each pair of shapes, find the gap between them
            for i in range(1, min(num_shapes + 1, 5)):  # Limit to 5 shapes
                for j in range(i + 1, min(num_shapes + 1, 5)):
                    mask_i = labeled_shapes == i
                    mask_j = labeled_shapes == j

                    # Dilate both shapes slightly
                    dilated_i = ndimage.binary_dilation(mask_i, iterations=3)
                    dilated_j = ndimage.binary_dilation(mask_j, iterations=3)

                    # Find overlap of dilated regions (potential gap area)
                    overlap = dilated_i & dilated_j & ~mask

                    if overlap.any():
                        gap_map[overlap] = 0.5

            # Simple boundary detection
            shape_boundaries = []
            for shape_id in range(1, min(num_shapes + 1, 5)):
                shape_mask = labeled_shapes == shape_id
                boundary = shape_mask & ~ndimage.binary_erosion(shape_mask)
                shape_boundaries.append(boundary)

            return gap_map, shape_boundaries

        except Exception as e:
            print(f"Simplified gap detection error: {e}")
            return np.zeros_like(mask, dtype=np.float32), []

    def adaptive_gap_aware_smoothing(self, mask_float, detail_map, gap_map, shape_boundaries):
        """Apply adaptive smoothing that respects gaps between shapes"""
        try:
            # Create multiple smoothing levels
            smooth_light = filters.gaussian(mask_float, sigma=0.3)    # Minimal smoothing
            smooth_medium = filters.gaussian(mask_float, sigma=0.7)   # Medium smoothing
            smooth_heavy = filters.gaussian(mask_float, sigma=1.2)    # Heavy smoothing

            # Create blending weights based on detail complexity AND gap proximity
            detail_inverted = 1.0 - detail_map

            # Areas near gaps should get minimal smoothing to preserve separation
            gap_proximity = filters.gaussian(gap_map, sigma=2.0)  # Extend gap influence
            gap_protection = gap_proximity * 0.8  # Reduce smoothing near gaps

            # Blend different smoothing levels with gap awareness
            weight_light = detail_map + gap_protection  # High detail + near gaps = light smoothing
            weight_medium = detail_inverted * (1 - detail_inverted) * (1 - gap_protection)
            weight_heavy = (detail_inverted**2) * (1 - gap_protection)

            # Normalize weights
            total_weight = weight_light + weight_medium + weight_heavy + 1e-8
            weight_light /= total_weight
            weight_medium /= total_weight
            weight_heavy /= total_weight

            # Blend the different smoothing levels
            result = (weight_light * smooth_light +
                     weight_medium * smooth_medium +
                     weight_heavy * smooth_heavy)

            # Additional boundary preservation for shape edges
            for boundary in shape_boundaries:
                if boundary.any():
                    boundary_dilated = ndimage.binary_dilation(boundary, iterations=2)
                    # Use original values near shape boundaries
                    result = np.where(boundary_dilated, mask_float, result)

            return result

        except Exception as e:
            # Fallback to simple gaussian smoothing
            return filters.gaussian(mask_float, sigma=0.7)

    def smooth_mask_edges_conservative(self, mask):
        """Conservative mask smoothing that preserves shape integrity for iterative smoothing"""
        try:
            # Convert to float for sub-pixel operations
            mask_float = mask.astype(np.float32)

            # Very light gaussian smoothing to reduce aliasing
            mask_smooth = filters.gaussian(mask_float, sigma=0.3)

            # Simple threshold to maintain crisp edges
            mask_clean = mask_smooth > 0.5

            # Minimal morphological cleaning
            # Remove only tiny artifacts
            mask_clean = morphology.remove_small_objects(mask_clean, min_size=5)

            # Very light opening to smooth minor irregularities
            kernel = morphology.disk(1)
            mask_clean = morphology.opening(mask_clean, kernel)

            return mask_clean

        except Exception as e:
            print(f"Conservative mask smoothing error: {e}")
            # Return original mask if smoothing fails
            return mask

    def extract_smooth_contours(self, logo_mask):
        """Extract contours with advanced gap-aware smoothing and optimization"""
        # Convert boolean mask to uint8
        mask_uint8 = (logo_mask * 255).astype(np.uint8)

        # Find contours with maximum detail initially
        contours, hierarchy = cv2.findContours(
            mask_uint8,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_NONE  # Get all points first
        )

        # Analyze shape relationships for gap awareness
        shape_relationships = self.analyze_shape_relationships(logo_mask, contours)

        # Filter and smooth contours with gap awareness
        filtered_contours = []
        contour_hierarchy = []

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area >= 10 and len(contour) >= 5:  # Minimum requirements

                # Apply gap-aware contour smoothing
                if self.curve_optimization_enabled:
                    # Get shape relationship info for this contour
                    relationship_info = shape_relationships.get(i, {})
                    smoothed_contour = self.smooth_contour_gap_aware(contour, relationship_info)
                else:
                    smoothed_contour = contour

                if len(smoothed_contour) >= 3:
                    filtered_contours.append(smoothed_contour)
                    contour_hierarchy.append(hierarchy[0][i] if hierarchy is not None and len(hierarchy) > 0 else None)

        return filtered_contours, contour_hierarchy

    def analyze_shape_relationships(self, mask, contours):
        """Analyze relationships between shapes to understand gaps and proximity (optimized)"""
        try:
            relationships = {}

            if len(contours) <= 1:
                return relationships

            # Limit analysis for performance
            max_contours = min(10, len(contours))
            contours_to_analyze = contours[:max_contours]

            # Quick area check - only analyze reasonably sized contours
            valid_contours = []
            for i, contour in enumerate(contours_to_analyze):
                area = cv2.contourArea(contour)
                if area >= 50 and len(contour) >= 5:  # Higher minimum area
                    valid_contours.append((i, contour))

            if len(valid_contours) <= 1:
                return relationships

            # Create simplified bounding boxes instead of full masks for initial distance calculation
            contour_bounds = []
            for i, contour in valid_contours:
                x, y, w, h = cv2.boundingRect(contour)
                contour_bounds.append((i, (x, y, w, h)))

            # Analyze each contour's relationship to others
            for idx, (i, contour) in enumerate(valid_contours):
                relationship_info = {
                    'nearby_shapes': [],
                    'min_distances': [],
                    'gap_regions': [],
                    'isolation_level': 0.0
                }

                current_bounds = contour_bounds[idx][1]

                # Find nearby shapes using bounding box distance first
                for other_idx, (j, other_contour) in enumerate(valid_contours):
                    if i == j:
                        continue

                    other_bounds = contour_bounds[other_idx][1]

                    # Quick bounding box distance check
                    bbox_distance = self.calculate_bbox_distance(current_bounds, other_bounds)

                    if bbox_distance < 100:  # Within reasonable proximity
                        # Only do expensive distance calculation for nearby shapes
                        min_distance = self.calculate_contour_distance_fast(contour, other_contour)

                        if min_distance < 50:
                            relationship_info['nearby_shapes'].append(j)
                            relationship_info['min_distances'].append(min_distance)

                            # Simplified gap detection for nearby shapes
                            if min_distance < 30:
                                gap_region = np.ones((10, 10), dtype=bool)  # Placeholder
                                relationship_info['gap_regions'].append(gap_region)

                # Calculate isolation level (how separated this shape is)
                if relationship_info['min_distances']:
                    avg_distance = np.mean(relationship_info['min_distances'])
                    relationship_info['isolation_level'] = min(1.0, avg_distance / 30.0)
                else:
                    relationship_info['isolation_level'] = 1.0  # Completely isolated

                relationships[i] = relationship_info

            return relationships

        except Exception as e:
            print(f"Shape relationship analysis error: {e}")
            return {}

    def calculate_bbox_distance(self, bbox1, bbox2):
        """Calculate distance between two bounding boxes"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        # Calculate center points
        center1 = (x1 + w1/2, y1 + h1/2)
        center2 = (x2 + w2/2, y2 + h2/2)

        # Return distance between centers
        return np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

    def calculate_contour_distance_fast(self, contour1, contour2):
        """Fast approximation of distance between contours using sampling"""
        try:
            # Sample points from contours for speed
            points1 = contour1.reshape(-1, 2)[::5]  # Every 5th point
            points2 = contour2.reshape(-1, 2)[::5]

            if len(points1) == 0 or len(points2) == 0:
                return float('inf')

            # Calculate minimum distance using broadcasting
            distances = np.sqrt(np.sum((points1[:, np.newaxis] - points2[np.newaxis, :])**2, axis=2))
            return np.min(distances)

        except Exception as e:
            return float('inf')

    def calculate_shape_distance(self, mask1, mask2):
        """Calculate minimum distance between two shape masks"""
        try:
            # Get boundary pixels for both shapes
            boundary1 = cv2.findContours((mask1 * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
            boundary2 = cv2.findContours((mask2 * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]

            if not boundary1 or not boundary2:
                return float('inf')

            boundary1_points = boundary1[0].reshape(-1, 2)
            boundary2_points = boundary2[0].reshape(-1, 2)

            # Calculate minimum distance between any two boundary points
            min_dist = float('inf')
            for p1 in boundary1_points[::5]:  # Sample every 5th point for efficiency
                for p2 in boundary2_points[::5]:
                    dist = np.linalg.norm(p1 - p2)
                    min_dist = min(min_dist, dist)

            return min_dist

        except Exception as e:
            return float('inf')

    def find_gap_region_between_shapes(self, mask1, mask2, min_distance):
        """Find the specific region that forms a gap between two shapes"""
        try:
            if min_distance > 30:  # Too far apart
                return None

            # Create combined mask
            combined = mask1 | mask2

            # Find the region between the shapes
            # Use distance transform to find the "valley" between shapes
            distance_from_combined = ndimage.distance_transform_edt(~combined)

            # The gap region is where distance is significant but not too large
            gap_region = (distance_from_combined > 1) & (distance_from_combined < min_distance * 0.7)

            if gap_region.any():
                return gap_region
            else:
                return None

        except Exception as e:
            return None

    def smooth_contour_gap_aware(self, contour, relationship_info):
        """Smooth contour while being aware of nearby shapes and gaps"""
        if len(contour) < 5:
            return contour

        # Convert contour to points array
        points = contour.reshape(-1, 2).astype(np.float32)

        # Adjust smoothing strategy based on shape relationships
        isolation_level = relationship_info.get('isolation_level', 0.5)
        nearby_shapes = relationship_info.get('nearby_shapes', [])

        # 1. Analyze contour complexity and detail density
        detail_complexity = self.analyze_contour_complexity(points)

        # 2. Detect corners in the contour
        corners = self.detect_contour_corners(points)

        # 3. Detect fine detail regions along the contour
        detail_regions = self.detect_contour_detail_regions(points)

        # 4. Gap-aware analysis: identify contour segments that face nearby shapes
        gap_facing_segments = self.identify_gap_facing_segments(points, relationship_info)

        # 5. Split contour at corners, details, and gap-facing boundaries
        critical_points = []

        # Add corner indices
        for corner in corners:
            distances = np.sum((points - corner)**2, axis=1)
            corner_idx = np.argmin(distances)
            critical_points.append(('corner', corner_idx))

        # Add detail region boundaries
        for start_idx, end_idx in detail_regions:
            critical_points.append(('detail_start', start_idx))
            critical_points.append(('detail_end', end_idx))

        # Add gap-facing segment boundaries
        for start_idx, end_idx in gap_facing_segments:
            critical_points.append(('gap_start', start_idx))
            critical_points.append(('gap_end', end_idx))

        if len(critical_points) > 0:
            # Sort by index position
            critical_points = sorted(set([(pt[1], pt[0]) for pt in critical_points]))
            critical_indices = [idx for idx, _ in critical_points]

            smoothed_segments = []

            # Smooth segments between critical points
            for i in range(len(critical_indices)):
                start_idx = critical_indices[i]
                end_idx = critical_indices[(i + 1) % len(critical_indices)]

                if start_idx < end_idx:
                    segment = points[start_idx:end_idx+1]
                else:
                    # Handle wrap-around
                    segment = np.vstack([points[start_idx:], points[:end_idx+1]])

                if len(segment) > 3:
                    # Determine smoothing strength based on all factors
                    segment_detail_level = self.calculate_gap_aware_detail_level(
                        segment, start_idx, end_idx, detail_regions, gap_facing_segments, isolation_level
                    )
                    smoothed_segment = self.smooth_curve_segment_adaptive(segment, segment_detail_level)
                    smoothed_segments.append(smoothed_segment)
                else:
                    smoothed_segments.append(segment)

            # Combine smoothed segments
            if smoothed_segments:
                smoothed_points = np.vstack(smoothed_segments)
            else:
                smoothed_points = points
        else:
            # No critical points, use isolation-aware smoothing for entire contour
            avg_detail_level = np.mean(detail_complexity) if len(detail_complexity) > 0 else 0.5
            # Isolated shapes can be smoothed more, shapes near gaps should be preserved
            isolation_factor = isolation_level * 0.3  # Reduce detail preservation for isolated shapes
            final_detail_level = max(0.2, avg_detail_level - isolation_factor)
            smoothed_points = self.smooth_curve_segment_adaptive(points, final_detail_level)

        # Remove duplicate points and ensure minimum spacing
        smoothed_points = self.remove_duplicate_points(smoothed_points)

        # Convert back to contour format
        smoothed_contour = smoothed_points.astype(np.int32).reshape(-1, 1, 2)

        return smoothed_contour

    def identify_gap_facing_segments(self, points, relationship_info):
        """Identify segments of contour that face toward gaps with other shapes"""
        try:
            gap_facing_segments = []
            nearby_shapes = relationship_info.get('nearby_shapes', [])
            gap_regions = relationship_info.get('gap_regions', [])

            if not nearby_shapes or not gap_regions:
                return gap_facing_segments

            # For each point on the contour, check if it's facing a gap
            gap_facing_points = []

            for i, point in enumerate(points):
                # Check if this point is near any gap region
                is_gap_facing = False

                for gap_region in gap_regions:
                    if gap_region is not None:
                        # Find closest gap pixel to this contour point
                        gap_coords = np.argwhere(gap_region)
                        if len(gap_coords) > 0:
                            distances = np.sum((gap_coords - point)**2, axis=1)
                            min_gap_distance = np.sqrt(np.min(distances))

                            if min_gap_distance < 15:  # Within gap influence
                                is_gap_facing = True
                                break

                gap_facing_points.append(is_gap_facing)

            # Find continuous segments of gap-facing points
            in_gap_segment = False
            segment_start = 0

            for i, is_gap_facing in enumerate(gap_facing_points):
                if is_gap_facing and not in_gap_segment:
                    # Start of gap-facing segment
                    segment_start = i
                    in_gap_segment = True
                elif not is_gap_facing and in_gap_segment:
                    # End of gap-facing segment
                    if i - segment_start >= 3:  # Minimum segment size
                        gap_facing_segments.append((segment_start, i - 1))
                    in_gap_segment = False

            # Handle case where gap-facing segment extends to end
            if in_gap_segment and len(points) - segment_start >= 3:
                gap_facing_segments.append((segment_start, len(points) - 1))

            return gap_facing_segments

        except Exception as e:
            return []

    def calculate_gap_aware_detail_level(self, segment, start_idx, end_idx, detail_regions, gap_facing_segments, isolation_level):
        """Calculate detail level considering gaps, details, and shape isolation"""
        try:
            segment_length = len(segment)
            if segment_length < 3:
                return 0.8  # High preservation for small segments

            # Start with base detail level calculation
            detail_overlap = 0
            for detail_start, detail_end in detail_regions:
                overlap_start = max(start_idx, detail_start)
                overlap_end = min(end_idx, detail_end)
                if overlap_start < overlap_end:
                    overlap_length = overlap_end - overlap_start
                    segment_range = end_idx - start_idx
                    if segment_range > 0:
                        detail_overlap += overlap_length / segment_range

            # Check gap-facing overlap
            gap_overlap = 0
            for gap_start, gap_end in gap_facing_segments:
                overlap_start = max(start_idx, gap_start)
                overlap_end = min(end_idx, gap_end)
                if overlap_start < overlap_end:
                    overlap_length = overlap_end - overlap_start
                    segment_range = end_idx - start_idx
                    if segment_range > 0:
                        gap_overlap += overlap_length / segment_range

            # Combine factors
            base_detail_level = 0.2 + (detail_overlap * 0.75)
            gap_preservation = gap_overlap * 0.6  # Strong preservation for gap-facing segments
            isolation_reduction = isolation_level * 0.2  # Isolated shapes can be smoothed more

            # Final detail level
            final_detail_level = base_detail_level + gap_preservation - isolation_reduction

            return min(0.95, max(0.15, final_detail_level))

        except Exception as e:
            return 0.5

    def smooth_contour_advanced(self, contour):
        """Advanced contour smoothing with corner and fine detail preservation"""
        if len(contour) < 5:
            return contour

        # Convert contour to points array
        points = contour.reshape(-1, 2).astype(np.float32)

        # 1. Analyze contour complexity and detail density
        detail_complexity = self.analyze_contour_complexity(points)

        # 2. Detect corners in the contour
        corners = self.detect_contour_corners(points)

        # 3. Detect fine detail regions along the contour
        detail_regions = self.detect_contour_detail_regions(points)

        # 4. Split contour at corners and detail boundaries for adaptive smoothing
        if len(corners) > 2 or len(detail_regions) > 0:
            smoothed_segments = []

            # Combine corner points and detail region boundaries
            critical_points = []

            # Add corner indices
            for corner in corners:
                distances = np.sum((points - corner)**2, axis=1)
                corner_idx = np.argmin(distances)
                critical_points.append(('corner', corner_idx))

            # Add detail region boundaries
            for start_idx, end_idx in detail_regions:
                critical_points.append(('detail_start', start_idx))
                critical_points.append(('detail_end', end_idx))

            # Sort by index position
            critical_points = sorted(set([(pt[1], pt[0]) for pt in critical_points]))
            critical_indices = [idx for idx, _ in critical_points]

            if len(critical_indices) == 0:
                critical_indices = [0, len(points) - 1]

            # Smooth segments between critical points
            for i in range(len(critical_indices)):
                start_idx = critical_indices[i]
                end_idx = critical_indices[(i + 1) % len(critical_indices)]

                if start_idx < end_idx:
                    segment = points[start_idx:end_idx+1]
                else:
                    # Handle wrap-around
                    segment = np.vstack([points[start_idx:], points[:end_idx+1]])

                if len(segment) > 3:
                    # Determine smoothing strength based on segment characteristics
                    segment_detail_level = self.calculate_segment_detail_level(segment, start_idx, end_idx, detail_regions)
                    smoothed_segment = self.smooth_curve_segment_adaptive(segment, segment_detail_level)
                    smoothed_segments.append(smoothed_segment)
                else:
                    smoothed_segments.append(segment)

            # Combine smoothed segments
            if smoothed_segments:
                smoothed_points = np.vstack(smoothed_segments)
            else:
                smoothed_points = points
        else:
            # No significant corners or details, use adaptive smoothing for entire contour
            avg_detail_level = np.mean(detail_complexity) if len(detail_complexity) > 0 else 0.5
            smoothed_points = self.smooth_curve_segment_adaptive(points, avg_detail_level)

        # 5. Remove duplicate points and ensure minimum spacing
        smoothed_points = self.remove_duplicate_points(smoothed_points)

        # Convert back to contour format
        smoothed_contour = smoothed_points.astype(np.int32).reshape(-1, 1, 2)

        return smoothed_contour

    def analyze_contour_complexity(self, points):
        """Analyze the complexity and detail density along a contour"""
        if len(points) < 3:
            return np.array([0.5])

        try:
            complexity = []
            window_size = min(5, len(points) // 3)

            for i in range(len(points)):
                # Get local window of points
                start_idx = max(0, i - window_size)
                end_idx = min(len(points), i + window_size + 1)
                local_points = points[start_idx:end_idx]

                if len(local_points) < 3:
                    complexity.append(0.5)
                    continue

                # Calculate local curvature variation
                curvatures = []
                for j in range(1, len(local_points) - 1):
                    p1, p2, p3 = local_points[j-1], local_points[j], local_points[j+1]

                    v1 = p2 - p1
                    v2 = p3 - p2

                    v1_norm = np.linalg.norm(v1)
                    v2_norm = np.linalg.norm(v2)

                    if v1_norm > 1e-6 and v2_norm > 1e-6:
                        v1_unit = v1 / v1_norm
                        v2_unit = v2 / v2_norm
                        dot_product = np.clip(np.dot(v1_unit, v2_unit), -1.0, 1.0)
                        angle = np.arccos(dot_product)
                        curvatures.append(angle)

                if len(curvatures) > 0:
                    # High variance in curvature indicates fine details
                    curvature_variance = np.var(curvatures)
                    complexity.append(min(1.0, curvature_variance * 10))  # Scale and clamp
                else:
                    complexity.append(0.5)

            return np.array(complexity)

        except Exception as e:
            return np.full(len(points), 0.5)

    def detect_contour_detail_regions(self, points):
        """Detect regions along contour that contain fine details"""
        if len(points) < 10:
            return []

        try:
            complexity = self.analyze_contour_complexity(points)

            # Find regions with high complexity (fine details)
            detail_threshold = np.percentile(complexity, 70)  # Top 30% complexity
            high_detail_mask = complexity > detail_threshold

            # Find continuous regions of high detail
            detail_regions = []
            in_detail_region = False
            region_start = 0

            for i, is_detail in enumerate(high_detail_mask):
                if is_detail and not in_detail_region:
                    # Start of detail region
                    region_start = i
                    in_detail_region = True
                elif not is_detail and in_detail_region:
                    # End of detail region
                    if i - region_start >= 3:  # Minimum region size
                        detail_regions.append((region_start, i - 1))
                    in_detail_region = False

            # Handle case where detail region extends to end
            if in_detail_region and len(points) - region_start >= 3:
                detail_regions.append((region_start, len(points) - 1))

            return detail_regions

        except Exception as e:
            return []

    def calculate_segment_detail_level(self, segment, start_idx, end_idx, detail_regions):
        """Calculate the detail level for a specific contour segment"""
        try:
            # Check if this segment overlaps with any detail regions
            segment_length = len(segment)
            if segment_length < 3:
                return 0.8  # High preservation for small segments

            detail_overlap = 0
            for detail_start, detail_end in detail_regions:
                # Calculate overlap between segment and detail region
                overlap_start = max(start_idx, detail_start)
                overlap_end = min(end_idx, detail_end)

                if overlap_start < overlap_end:
                    overlap_length = overlap_end - overlap_start
                    segment_range = end_idx - start_idx
                    if segment_range > 0:
                        detail_overlap += overlap_length / segment_range

            # Clamp detail level between 0.2 (heavy smoothing) and 0.95 (minimal smoothing)
            detail_level = 0.2 + (detail_overlap * 0.75)
            return min(0.95, max(0.2, detail_level))

        except Exception as e:
            return 0.5  # Default medium detail level

    def smooth_curve_segment_adaptive(self, points, detail_level):
        """Smooth a curve segment with adaptive strength based on detail level"""
        if len(points) < 4:
            return points

        try:
            # Adjust smoothing strength based on detail level
            # High detail_level (0.8-0.95) = minimal smoothing (strength 0.1-0.3)
            # Low detail_level (0.2-0.4) = heavy smoothing (strength 0.8-1.2)
            smoothing_strength = (1.0 - detail_level) * 1.5

            return self.smooth_curve_segment(points, strength=smoothing_strength)

        except Exception as e:
            # Fallback to simple smoothing
            return self.smooth_curve_simple(points)

    def detect_contour_corners(self, points):
        """Detect corners in a contour using curvature analysis"""
        if len(points) < 5:
            return np.array([]).reshape(0, 2)

        try:
            # Smooth points slightly for curvature calculation
            points_smooth = self.smooth_curve_segment(points, strength=0.3)

            # Calculate curvature at each point
            curvatures = []
            window = min(3, len(points_smooth) // 3)  # Ensure window size is appropriate

            for i in range(len(points_smooth)):
                # Get neighboring points
                prev_idx = (i - window) % len(points_smooth)
                next_idx = (i + window) % len(points_smooth)

                prev_point = points_smooth[prev_idx]
                curr_point = points_smooth[i]
                next_point = points_smooth[next_idx]

                # Calculate angle
                v1 = prev_point - curr_point
                v2 = next_point - curr_point

                # Normalize vectors
                v1_norm = np.linalg.norm(v1)
                v2_norm = np.linalg.norm(v2)

                if v1_norm > 1e-6 and v2_norm > 1e-6:  # Avoid division by very small numbers
                    v1 = v1 / v1_norm
                    v2 = v2 / v2_norm

                    # Calculate angle (curvature)
                    dot_product = np.clip(np.dot(v1, v2), -1.0, 1.0)
                    angle = np.arccos(dot_product)
                    curvatures.append(angle)
                else:
                    curvatures.append(0)

            # Find points with high curvature (corners)
            curvatures = np.array(curvatures)
            if len(curvatures) == 0 or curvatures.max() == 0:
                return np.array([]).reshape(0, 2)

            threshold = np.percentile(curvatures, 85)  # Top 15% curvature

            corner_indices = np.where(curvatures > max(threshold, 0.5))[0]  # At least 0.5 radians

            if len(corner_indices) == 0:
                return np.array([]).reshape(0, 2)

            # Return corner points
            corners = points[corner_indices]

            return corners
        except Exception as e:
            return np.array([]).reshape(0, 2)

    def smooth_curve_segment(self, points, strength=0.5):
        """Smooth a curve segment using spline interpolation"""
        if len(points) < 4:
            return points

        try:
            # Ensure points are closed if it's a closed contour
            if np.allclose(points[0], points[-1]):
                # Closed contour - use periodic spline
                points_work = points[:-1]  # Remove duplicate last point

                # Parameterize by arc length
                distances = np.sqrt(np.sum(np.diff(points_work, axis=0)**2, axis=1))
                distances = np.concatenate([[0], np.cumsum(distances)])

                if len(distances) >= 4:
                    # Fit spline
                    tck, u = splprep([points_work[:, 0], points_work[:, 1]],
                                   u=distances, s=strength * len(points_work), per=1)

                    # Evaluate spline at higher resolution
                    u_new = np.linspace(0, distances[-1], max(len(points_work), 20))
                    smoothed = splev(u_new, tck)
                    smoothed_points = np.column_stack(smoothed)

                    # Close the contour
                    smoothed_points = np.vstack([smoothed_points, smoothed_points[0]])
                else:
                    smoothed_points = points
            else:
                # Open curve
                distances = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
                distances = np.concatenate([[0], np.cumsum(distances)])

                if len(distances) >= 4:
                    tck, u = splprep([points[:, 0], points[:, 1]],
                                   u=distances, s=strength * len(points))

                    u_new = np.linspace(0, distances[-1], max(len(points), 20))
                    smoothed = splev(u_new, tck)
                    smoothed_points = np.column_stack(smoothed)
                else:
                    smoothed_points = points

        except Exception:
            # Fallback to simple averaging if spline fails
            smoothed_points = self.smooth_curve_simple(points)

        return smoothed_points

    def smooth_curve_simple(self, points):
        """Simple curve smoothing using moving average"""
        if len(points) < 3:
            return points

        smoothed = points.copy().astype(np.float32)

        # Apply multiple passes of light smoothing
        for _ in range(2):
            for i in range(1, len(points) - 1):
                smoothed[i] = 0.5 * smoothed[i] + 0.25 * (smoothed[i-1] + smoothed[i+1])

        return smoothed

    def remove_duplicate_points(self, points, min_distance=1.0):
        """Remove points that are too close together"""
        if len(points) < 2:
            return points

        filtered_points = [points[0]]

        for i in range(1, len(points)):
            distance = np.linalg.norm(points[i] - filtered_points[-1])
            if distance >= min_distance:
                filtered_points.append(points[i])

        return np.array(filtered_points)

    def create_optimized_svg(self, contours, hierarchy, image_shape, use_curves=True):
        """Create SVG with advanced curve optimization and clean edges"""
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

            # Create optimized path data
            if use_curves and len(contour) > 6:
                path_data = self.create_smooth_bezier_path(contour)
            else:
                path_data = self.create_optimized_linear_path(contour)

            # Choose class based on whether it's a hole
            css_class = "logo-hole" if is_hole else "logo-path"

            svg_content += f'    <path d="{path_data}" class="{css_class}"/>\n'

        svg_content += '''  </g>
</svg>'''

        return svg_content

    def create_smooth_bezier_path(self, contour):
        """Create smooth Bezier curves from contour points"""
        points = contour.reshape(-1, 2)

        if len(points) < 4:
            return self.create_optimized_linear_path(contour)

        # Start path
        path_data = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

        # Create smooth curves using cubic Bezier
        # Use every 3rd point as anchor, interpolate control points

        i = 1
        while i < len(points) - 2:
            # Current anchor point
            if i + 2 < len(points):
                # Calculate control points for smooth curve
                p0 = points[i-1] if i > 0 else points[0]
                p1 = points[i]
                p2 = points[i+1]
                p3 = points[i+2] if i+2 < len(points) else points[-1]

                # Calculate smooth control points
                cp1 = p1 + 0.3 * (p2 - p0)
                cp2 = p2 - 0.3 * (p3 - p1)

                path_data += f" C {cp1[0]:.2f} {cp1[1]:.2f}, {cp2[0]:.2f} {cp2[1]:.2f}, {p2[0]:.2f} {p2[1]:.2f}"
                i += 1
            else:
                # Line to remaining points
                for j in range(i, len(points)):
                    path_data += f" L {points[j][0]:.2f} {points[j][1]:.2f}"
                break

        # Close path smoothly
        path_data += " Z"
        return path_data

    def create_optimized_linear_path(self, contour):
        """Create optimized linear path with Douglas-Peucker simplification"""
        points = contour.reshape(-1, 2)

        if len(points) == 0:
            return ""

        # Apply light Douglas-Peucker simplification for cleaner lines
        epsilon = 0.5  # Very small epsilon to maintain detail
        simplified = cv2.approxPolyDP(contour, epsilon, True)
        points = simplified.reshape(-1, 2)

        # Start path
        path_data = f"M {points[0][0]:.2f} {points[0][1]:.2f}"

        # Add lines with optimized precision
        for point in points[1:]:
            path_data += f" L {point[0]:.2f} {point[1]:.2f}"

        # Close path
        path_data += " Z"
        return path_data

    def vectorize_test_logo(self, image_array, epsilon_factor=0.001, smoothing_level="high"):
        """Complete test vectorization pipeline with advanced smoothing (optimized)"""
        import time
        start_time = time.time()

        try:
            print(f"Starting test vectorization with smoothing level: {smoothing_level}")

            # Ensure we have a valid numpy array
            if not isinstance(image_array, np.ndarray):
                image_array = np.array(image_array)

            print(f"Image shape: {image_array.shape}")

            # Check image size and adjust complexity accordingly
            total_pixels = image_array.shape[0] * image_array.shape[1]
            is_large_image = total_pixels > 100000

            # Configure smoothing based on level and image size
            # Fix for black output: use iterative approach instead of over-aggressive smoothing
            if smoothing_level == "extreme":
                self.smoothing_enabled = True
                self.corner_detection_enabled = True
                self.curve_optimization_enabled = True
                self.iterative_passes = 5  # Multiple passes for extreme smoothing
                self.smoothing_strength = 0.3  # Moderate strength per pass
            elif smoothing_level == "high":
                self.smoothing_enabled = True
                self.corner_detection_enabled = True
                self.curve_optimization_enabled = True
                self.iterative_passes = 3  # Multiple passes for high smoothing
                self.smoothing_strength = 0.4  # Moderate strength per pass
            elif smoothing_level == "medium":
                self.smoothing_enabled = True
                self.corner_detection_enabled = False
                self.curve_optimization_enabled = True
                self.iterative_passes = 2  # Fewer passes for medium
                self.smoothing_strength = 0.5
            else:  # low or off
                self.smoothing_enabled = False
                self.corner_detection_enabled = False
                self.curve_optimization_enabled = False
                self.iterative_passes = 1
                self.smoothing_strength = 0.2

            # Step 1: Create enhanced mask with edge smoothing
            print("Creating enhanced mask...")
            try:
                logo_mask = self.create_enhanced_mask(image_array)
                print(f"Mask created, time elapsed: {time.time() - start_time:.2f}s")
            except Exception as e:
                print(f"Mask creation failed, using fallback: {e}")
                # Fallback to simple thresholding
                if len(image_array.shape) == 3 and image_array.shape[2] == 4:
                    logo_mask = image_array[:, :, 3] > 50
                else:
                    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY) if len(image_array.shape) == 3 else image_array
                    _, logo_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    logo_mask = logo_mask == 255

            # Timeout check
            if time.time() - start_time > 30:  # 30 second timeout
                raise Exception("Processing timeout - image too complex")

            # Step 2: Extract and iteratively smooth contours
            print("Extracting contours...")
            try:
                contours, hierarchy = self.extract_smooth_contours(logo_mask)
                print(f"Contours extracted: {len(contours)}, time elapsed: {time.time() - start_time:.2f}s")

                # Apply iterative smoothing for stair-step elimination
                if self.smoothing_enabled and self.iterative_passes > 1:
                    print(f"Applying iterative smoothing ({self.iterative_passes} passes)...")
                    contours = self.apply_iterative_smoothing(contours, self.iterative_passes)
                    print(f"Iterative smoothing completed, time elapsed: {time.time() - start_time:.2f}s")

            except Exception as e:
                print(f"Advanced contour extraction failed, using simple method: {e}")
                # Fallback to simple contour extraction
                mask_uint8 = (logo_mask * 255).astype(np.uint8)
                contours, hierarchy = cv2.findContours(mask_uint8, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                # Simple filtering
                contours = [c for c in contours if cv2.contourArea(c) >= 50]

            if not contours:
                raise Exception("No logo contours found after processing.")

            # Timeout check
            if time.time() - start_time > 30:
                raise Exception("Processing timeout during contour extraction")

            # Step 3: Create optimized SVG with smooth curves
            print("Creating SVG...")
            try:
                svg_content = self.create_optimized_svg(contours, hierarchy, image_array.shape, use_curves=True)
            except Exception as e:
                print(f"Advanced SVG creation failed, using simple method: {e}")
                # Fallback to basic SVG creation
                svg_content = self.create_simple_svg_fallback(contours, image_array.shape)

            # Step 4: Create preview images
            print("Creating preview...")
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

            total_time = time.time() - start_time
            print(f"Test vectorization completed in {total_time:.2f}s")

            return {
                'success': True,
                'svg_content': svg_content,
                'preview_rgba': preview_rgba,
                'binary_mask': preview_mask,
                'contour_count': len(contours),
                'detail_level': 'test_advanced',
                'smoothing_level': smoothing_level,
                'processing_time': total_time
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Test vectorization error: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }

    def create_simple_svg_fallback(self, contours, image_shape):
        """Simple SVG creation fallback"""
        height, width = image_shape[:2]

        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg">
  <g fill="black">
'''

        for contour in contours:
            if len(contour) < 3:
                continue

            points = contour.reshape(-1, 2)
            path_data = f"M {points[0][0]} {points[0][1]}"

            for point in points[1:]:
                path_data += f" L {point[0]} {point[1]}"

            path_data += " Z"
            svg_content += f'    <path d="{path_data}"/>\n'

        svg_content += '  </g>\n</svg>'
        return svg_content

    def apply_iterative_smoothing(self, contours, num_passes):
        """Apply intelligent smoothing that preserves straight lines and sharp angles"""
        try:
            print(f"Starting intelligent iterative smoothing with {num_passes} passes")

            smoothed_contours = []

            for contour_idx, contour in enumerate(contours):
                if len(contour) < 5:
                    smoothed_contours.append(contour)
                    continue

                # Convert to points for analysis
                points = contour.reshape(-1, 2).astype(np.float32)

                # Step 1: Analyze contour geometry
                geometry_analysis = self.analyze_contour_geometry(points)

                # Step 2: Apply selective smoothing based on geometry
                smoothed_points = self.apply_selective_smoothing(points, geometry_analysis, num_passes)

                # Convert back to contour format
                if len(smoothed_points) >= 3:
                    smoothed_contour = smoothed_points.astype(np.int32).reshape(-1, 1, 2)
                    smoothed_contours.append(smoothed_contour)
                else:
                    smoothed_contours.append(contour)

            return smoothed_contours

        except Exception as e:
            print(f"Iterative smoothing error: {e}")
            return contours  # Return original contours if smoothing fails

    def analyze_contour_geometry(self, points):
        """Analyze contour to identify straight lines, curves, and sharp angles"""
        try:
            if len(points) < 5:
                return {'segments': [{'type': 'curve', 'start': 0, 'end': len(points)-1}]}

            segments = []
            current_segment_start = 0
            current_segment_type = None

            # Analyze each point to determine local geometry
            for i in range(len(points)):
                geometry_type = self.classify_local_geometry(points, i)

                if current_segment_type is None:
                    current_segment_type = geometry_type
                    current_segment_start = i
                elif current_segment_type != geometry_type:
                    # Segment type changed, save current segment
                    if i > current_segment_start:
                        segments.append({
                            'type': current_segment_type,
                            'start': current_segment_start,
                            'end': i - 1
                        })
                    current_segment_type = geometry_type
                    current_segment_start = i

            # Add final segment
            if current_segment_start < len(points) - 1:
                segments.append({
                    'type': current_segment_type,
                    'start': current_segment_start,
                    'end': len(points) - 1
                })

            # Merge short segments to avoid discontinuity
            merged_segments = self.merge_short_segments(segments, min_length=5)

            return {'segments': merged_segments}

        except Exception as e:
            print(f"Geometry analysis error: {e}")
            return {'segments': [{'type': 'curve', 'start': 0, 'end': len(points)-1}]}

    def classify_local_geometry(self, points, index):
        """Classify the local geometry at a specific point"""
        try:
            window_size = min(6, len(points) // 4)
            start_idx = max(0, index - window_size)
            end_idx = min(len(points), index + window_size + 1)

            if end_idx - start_idx < 3:
                return 'curve'

            local_points = points[start_idx:end_idx]

            # Calculate straightness using linear regression
            straightness = self.calculate_straightness(local_points)

            # Calculate angle variation
            angle_variation = self.calculate_angle_variation(local_points)

            # Classification thresholds
            if straightness > 0.95 and angle_variation < 0.1:
                return 'straight'
            elif angle_variation > 0.8:
                return 'corner'
            else:
                return 'curve'

        except Exception as e:
            return 'curve'

    def calculate_straightness(self, points):
        """Calculate how straight a line segment is (0-1, 1 = perfectly straight)"""
        try:
            if len(points) < 3:
                return 1.0

            # Fit a line through the points
            x_coords = points[:, 0]
            y_coords = points[:, 1]

            # Calculate line from first to last point
            start_point = points[0]
            end_point = points[-1]

            if np.allclose(start_point, end_point):
                return 0.0  # Closed loop

            # Calculate distance from each point to the line
            line_vec = end_point - start_point
            line_length = np.linalg.norm(line_vec)

            if line_length < 1e-6:
                return 0.0

            total_deviation = 0.0
            for point in points[1:-1]:  # Skip first and last points
                point_vec = point - start_point
                # Project onto line
                projection_length = np.dot(point_vec, line_vec) / line_length
                projection_point = start_point + (projection_length / line_length) * line_vec
                deviation = np.linalg.norm(point - projection_point)
                total_deviation += deviation

            # Normalize by number of points and line length
            avg_deviation = total_deviation / max(1, len(points) - 2)
            straightness = max(0.0, 1.0 - (avg_deviation / max(1.0, line_length * 0.1)))

            return straightness

        except Exception as e:
            return 0.5

    def calculate_angle_variation(self, points):
        """Calculate variation in angles between consecutive segments"""
        try:
            if len(points) < 4:
                return 0.0

            angles = []
            for i in range(1, len(points) - 1):
                v1 = points[i] - points[i-1]
                v2 = points[i+1] - points[i]

                v1_norm = np.linalg.norm(v1)
                v2_norm = np.linalg.norm(v2)

                if v1_norm > 1e-6 and v2_norm > 1e-6:
                    cos_angle = np.dot(v1, v2) / (v1_norm * v2_norm)
                    cos_angle = np.clip(cos_angle, -1, 1)
                    angle = np.arccos(cos_angle)
                    angles.append(angle)

            if not angles:
                return 0.0

            angle_variation = np.std(angles) / np.pi  # Normalize by pi
            return min(1.0, angle_variation)

        except Exception as e:
            return 0.0

    def merge_short_segments(self, segments, min_length=5):
        """Merge short segments to avoid discontinuity"""
        try:
            if len(segments) <= 1:
                return segments

            merged = []
            i = 0

            while i < len(segments):
                current_segment = segments[i]
                segment_length = current_segment['end'] - current_segment['start']

                if segment_length < min_length and len(merged) > 0:
                    # Merge with previous segment
                    merged[-1]['end'] = current_segment['end']
                    # Choose dominant type
                    prev_length = merged[-1]['end'] - merged[-1]['start']
                    if segment_length > prev_length:
                        merged[-1]['type'] = current_segment['type']
                else:
                    merged.append(current_segment)

                i += 1

            return merged

        except Exception as e:
            return segments

    def apply_selective_smoothing(self, points, geometry_analysis, num_passes):
        """Apply appropriate smoothing based on geometry analysis"""
        try:
            segments = geometry_analysis['segments']
            smoothed_points = points.copy()

            for pass_num in range(num_passes):
                print(f"  Selective pass {pass_num + 1}/{num_passes}")

                for segment in segments:
                    start_idx = segment['start']
                    end_idx = segment['end']
                    segment_type = segment['type']

                    if end_idx <= start_idx:
                        continue

                    segment_points = smoothed_points[start_idx:end_idx + 1]

                    if len(segment_points) < 3:
                        continue

                    if segment_type == 'straight':
                        # Minimal smoothing for straight lines
                        smoothed_segment = self.smooth_straight_line(segment_points, pass_num)
                    elif segment_type == 'corner':
                        # Preserve corners with very light smoothing
                        smoothed_segment = self.smooth_corner_preserve(segment_points, pass_num)
                    else:  # curve
                        # Full smoothing for curves
                        smoothed_segment = self.smooth_curve_segment_intelligent(segment_points, pass_num)

                    # Update the points
                    smoothed_points[start_idx:end_idx + 1] = smoothed_segment

            return smoothed_points

        except Exception as e:
            print(f"Selective smoothing error: {e}")
            return points

    def smooth_straight_line(self, points, pass_num):
        """Smooth straight line segments while preserving linearity"""
        try:
            if len(points) < 3:
                return points

            # For straight lines, only reduce stair-stepping while maintaining direction
            start_point = points[0]
            end_point = points[-1]

            # Fit all points to the line between start and end
            line_vec = end_point - start_point
            line_length = np.linalg.norm(line_vec)

            if line_length < 1e-6:
                return points

            smoothed = points.copy()
            strength = 0.3 / (pass_num + 1)  # Reduce strength with each pass

            for i in range(1, len(points) - 1):
                # Project point onto line
                point_vec = points[i] - start_point
                projection_length = np.dot(point_vec, line_vec) / line_length
                projection_point = start_point + (projection_length / line_length) * line_vec

                # Blend original point with projection
                smoothed[i] = points[i] * (1 - strength) + projection_point * strength

            return smoothed

        except Exception as e:
            return points

    def smooth_corner_preserve(self, points, pass_num):
        """Light smoothing that preserves corner sharpness"""
        try:
            if len(points) < 3:
                return points

            # Very light smoothing only
            smoothed = points.copy()
            strength = 0.1 / (pass_num + 1)  # Very light and decreasing

            # Only smooth middle points, preserve endpoints
            for i in range(1, len(points) - 1):
                neighbor_avg = (points[i-1] + points[i+1]) / 2
                smoothed[i] = points[i] * (1 - strength) + neighbor_avg * strength

            return smoothed

        except Exception as e:
            return points

    def smooth_curve_segment_intelligent(self, points, pass_num):
        """Full smoothing for curve segments"""
        try:
            if len(points) < 4:
                return self.smooth_corner_preserve(points, pass_num)

            # Use different techniques based on pass number
            if pass_num == 0:
                return self.smooth_contour_gentle(points)
            elif pass_num == 1:
                return self.smooth_curve_spline(points)
            else:
                return self.smooth_contour_progressive(points, pass_num)

        except Exception as e:
            return points

    def smooth_curve_spline(self, points):
        """Smooth curves using spline fitting"""
        try:
            if len(points) < 4:
                return points

            # Use scipy spline if available
            try:
                from scipy.interpolate import splprep, splev

                # Parameterize by arc length
                distances = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
                distances = np.concatenate([[0], np.cumsum(distances)])

                # Fit spline
                tck, u = splprep([points[:, 0], points[:, 1]], u=distances, s=len(points) * 0.5)

                # Evaluate spline at original parameter values
                smoothed = splev(distances, tck)
                return np.column_stack(smoothed).astype(np.float32)

            except ImportError:
                # Fallback to simple smoothing
                return self.smooth_contour_gentle(points)

        except Exception as e:
            return points

    def smooth_contour_gentle(self, points):
        """First pass: Gentle smoothing to preserve overall shape"""
        try:
            if len(points) < 5:
                return points

            # Apply lightweight moving average
            smoothed = points.copy().astype(np.float32)

            # Multiple light passes
            for _ in range(2):
                for i in range(1, len(points) - 1):
                    # Weighted average with neighbors
                    smoothed[i] = (0.25 * smoothed[i-1] +
                                 0.5 * smoothed[i] +
                                 0.25 * smoothed[i+1])

            # Handle closed contour (first and last points)
            if len(points) > 3:
                smoothed[0] = (0.25 * smoothed[-1] + 0.5 * smoothed[0] + 0.25 * smoothed[1])
                smoothed[-1] = (0.25 * smoothed[-2] + 0.5 * smoothed[-1] + 0.25 * smoothed[0])

            return smoothed

        except Exception as e:
            return points

    def smooth_contour_curve_fitting(self, points):
        """Second pass: Curve fitting to eliminate stair-steps"""
        try:
            if len(points) < 6:
                return points

            # Use polynomial fitting for smooth curves
            smoothed_points = []
            window_size = min(7, len(points) // 3)

            for i in range(len(points)):
                # Get local window
                start_idx = max(0, i - window_size // 2)
                end_idx = min(len(points), i + window_size // 2 + 1)
                local_points = points[start_idx:end_idx]

                if len(local_points) >= 3:
                    # Fit polynomial curve through local points
                    t = np.linspace(0, 1, len(local_points))

                    try:
                        # Fit 2nd degree polynomial
                        poly_x = np.polyfit(t, local_points[:, 0], min(2, len(local_points) - 1))
                        poly_y = np.polyfit(t, local_points[:, 1], min(2, len(local_points) - 1))

                        # Evaluate at center point
                        center_t = 0.5
                        smooth_x = np.polyval(poly_x, center_t)
                        smooth_y = np.polyval(poly_y, center_t)

                        smoothed_points.append([smooth_x, smooth_y])
                    except:
                        # Fallback to original point
                        smoothed_points.append(points[i])
                else:
                    smoothed_points.append(points[i])

            return np.array(smoothed_points, dtype=np.float32)

        except Exception as e:
            return points

    def smooth_contour_bezier_approximation(self, points):
        """Third pass: Bezier approximation for smooth curves"""
        try:
            if len(points) < 8:
                return points

            # Create smooth Bezier approximation
            smoothed_points = []

            # Process in segments
            segment_size = 6
            for i in range(0, len(points), segment_size // 2):
                end_idx = min(i + segment_size, len(points))
                segment = points[i:end_idx]

                if len(segment) >= 4:
                    # Create Bezier curve through segment
                    bezier_points = self.create_bezier_segment(segment)

                    # Add points, avoiding duplicates
                    if i == 0:
                        smoothed_points.extend(bezier_points)
                    else:
                        smoothed_points.extend(bezier_points[1:])  # Skip first point to avoid duplicate
                else:
                    # Add remaining points directly
                    if i == 0:
                        smoothed_points.extend(segment)
                    else:
                        smoothed_points.extend(segment[1:])

            return np.array(smoothed_points, dtype=np.float32)

        except Exception as e:
            return points

    def create_bezier_segment(self, segment_points):
        """Create a smooth Bezier curve through a segment of points"""
        try:
            if len(segment_points) < 4:
                return segment_points

            # Use first, middle, and last points as control points
            start = segment_points[0]
            end = segment_points[-1]

            # Calculate control points
            third = len(segment_points) // 3
            two_third = 2 * len(segment_points) // 3

            control1 = segment_points[third]
            control2 = segment_points[two_third]

            # Generate Bezier curve points
            num_points = len(segment_points)
            t_values = np.linspace(0, 1, num_points)

            bezier_points = []
            for t in t_values:
                # Cubic Bezier formula
                point = ((1-t)**3 * start +
                        3*(1-t)**2*t * control1 +
                        3*(1-t)*t**2 * control2 +
                        t**3 * end)
                bezier_points.append(point)

            return bezier_points

        except Exception as e:
            return segment_points.tolist()

    def smooth_contour_progressive(self, points, pass_number):
        """Additional passes: Progressive refinement"""
        try:
            if len(points) < 4:
                return points

            # Reduce smoothing strength with each pass
            strength = self.smoothing_strength * (0.8 ** (pass_number - 2))

            # Apply adaptive smoothing based on local curvature
            smoothed = points.copy().astype(np.float32)

            for i in range(1, len(points) - 1):
                # Calculate local curvature
                prev_point = points[i - 1]
                curr_point = points[i]
                next_point = points[i + 1]

                # Vector from previous to current
                v1 = curr_point - prev_point
                # Vector from current to next
                v2 = next_point - curr_point

                # Calculate angle between vectors (curvature indicator)
                try:
                    v1_norm = np.linalg.norm(v1)
                    v2_norm = np.linalg.norm(v2)

                    if v1_norm > 1e-6 and v2_norm > 1e-6:
                        cos_angle = np.dot(v1, v2) / (v1_norm * v2_norm)
                        cos_angle = np.clip(cos_angle, -1, 1)
                        angle = np.arccos(cos_angle)

                        # Higher curvature = less smoothing
                        curvature_factor = angle / np.pi
                        local_strength = strength * (1 - curvature_factor * 0.5)

                        # Apply weighted smoothing
                        neighbor_avg = (prev_point + next_point) / 2
                        smoothed[i] = curr_point * (1 - local_strength) + neighbor_avg * local_strength

                except:
                    # Fallback to simple averaging
                    smoothed[i] = (prev_point + curr_point + next_point) / 3

            return smoothed

        except Exception as e:
            return points

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