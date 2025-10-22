#!/usr/bin/env python3
"""
Advanced Logo Upscaling Engine - High-quality image scaling with edge preservation
"""

import cv2
import numpy as np
from PIL import Image
import io
import base64
from scipy import ndimage
from skimage import filters, morphology


class LogoUpscaler:
    def __init__(self):
        self.edge_threshold = 30  # Threshold for edge detection
        self.contrast_boost = 1.2  # Contrast enhancement factor

    def upscale_logo(self, image_array, scale_factor=2, method="smart_edge", preserve_contrast=True, logo_type="styled"):
        """
        Upscale logo with multiple advanced methods

        Methods:
        - smart_edge: Edge-preserving with contrast enhancement
        - super_resolution: AI-like super resolution simulation
        - pixel_art: Sharp pixel-perfect scaling for pixel art logos
        - hybrid: Combination of methods
        """
        try:
            print(f"Starting logo upscaling: {scale_factor}x using {method}")

            # Ensure we have a valid numpy array
            if not isinstance(image_array, np.ndarray):
                image_array = np.array(image_array)

            original_shape = image_array.shape
            print(f"Original size: {original_shape}")

            # Choose upscaling method
            if method == "smart_edge":
                upscaled = self.smart_edge_upscaling(image_array, scale_factor, logo_type)
            elif method == "super_resolution":
                upscaled = self.super_resolution_upscaling(image_array, scale_factor, logo_type)
            elif method == "pixel_art":
                upscaled = self.pixel_art_upscaling(image_array, scale_factor)
            elif method == "hybrid":
                upscaled = self.hybrid_upscaling(image_array, scale_factor, logo_type)
            else:
                # Fallback to smart edge
                upscaled = self.smart_edge_upscaling(image_array, scale_factor, logo_type)

            # Apply contrast preservation if requested
            if preserve_contrast:
                upscaled = self.preserve_contrast(upscaled, image_array)

            # Final edge enhancement
            upscaled = self.enhance_edges(upscaled)

            print(f"Upscaling completed: {upscaled.shape}")

            return {
                'success': True,
                'upscaled_image': upscaled,
                'original_size': f"{original_shape[1]}x{original_shape[0]}",
                'new_size': f"{upscaled.shape[1]}x{upscaled.shape[0]}",
                'scale_factor': scale_factor,
                'method': method
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def smart_edge_upscaling(self, image_array, scale_factor, logo_type="styled"):
        """Smart edge-preserving upscaling optimized for logos"""
        try:
            # Step 1: Detect edges
            edges = self.detect_logo_edges(image_array)

            # Step 2: Create edge map for guidance
            edge_guidance = self.create_edge_guidance_map(edges, scale_factor)

            # Step 3: Choose processing path based on logo type
            if logo_type == "flat_color":
                # For flat color logos: analyze original, pre-sharpen, upscale intelligently, post-sharpen
                upscaled = self.flat_color_sharpening(image_array, scale_factor)
            else:
                # For styled logos: traditional high-quality upscaling with edge refinement
                if len(image_array.shape) == 3:
                    # Color image
                    upscaled = cv2.resize(
                        image_array,
                        (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                        interpolation=cv2.INTER_LANCZOS4
                    )
                else:
                    # Grayscale
                    upscaled = cv2.resize(
                        image_array,
                        (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                        interpolation=cv2.INTER_LANCZOS4
                    )

                # Apply edge-guided refinement for styled logos
                upscaled = self.refine_with_edges(upscaled, edge_guidance)

            return upscaled

        except Exception as e:
            print(f"Smart edge upscaling error: {e}")
            # Fallback to simple interpolation
            return cv2.resize(image_array,
                            (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                            interpolation=cv2.INTER_LANCZOS4)

    def detect_logo_edges(self, image_array):
        """Detect edges specifically optimized for logos"""
        try:
            # Convert to grayscale for edge detection
            if len(image_array.shape) == 3:
                if image_array.shape[2] == 4:  # RGBA
                    # Use alpha channel for transparent images
                    alpha = image_array[:, :, 3]
                    gray = cv2.cvtColor(image_array[:, :, :3], cv2.COLOR_RGB2GRAY)
                    # Combine RGB edges with alpha edges
                    alpha_edges = cv2.Canny(alpha, 50, 150)
                    rgb_edges = cv2.Canny(gray, 50, 150)
                    edges = cv2.bitwise_or(alpha_edges, rgb_edges)
                else:  # RGB
                    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
                    edges = cv2.Canny(gray, 50, 150)
            else:
                # Already grayscale
                edges = cv2.Canny(image_array, 50, 150)

            # Enhance edges for logos
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

            return edges

        except Exception as e:
            print(f"Edge detection error: {e}")
            return np.zeros(image_array.shape[:2], dtype=np.uint8)

    def create_edge_guidance_map(self, edges, scale_factor):
        """Create guidance map for edge-preserving upscaling"""
        try:
            # Upscale edge map
            upscaled_edges = cv2.resize(edges,
                                      (edges.shape[1] * scale_factor, edges.shape[0] * scale_factor),
                                      interpolation=cv2.INTER_NEAREST)

            # Create distance field from edges
            distance_from_edges = cv2.distanceTransform(255 - upscaled_edges, cv2.DIST_L2, 5)

            # Normalize and invert (closer to edge = higher value)
            max_dist = distance_from_edges.max()
            if max_dist > 0:
                edge_guidance = 1.0 - (distance_from_edges / max_dist)
            else:
                edge_guidance = np.ones_like(distance_from_edges)

            return edge_guidance

        except Exception as e:
            print(f"Edge guidance error: {e}")
            return np.ones((edges.shape[0] * scale_factor, edges.shape[1] * scale_factor))

    def refine_with_edges(self, upscaled_image, edge_guidance):
        """Refine upscaled image using edge guidance"""
        try:
            # Apply edge-preserving filter
            refined = upscaled_image.copy()

            if len(upscaled_image.shape) == 3:
                for channel in range(upscaled_image.shape[2]):
                    # Apply bilateral filter with edge guidance
                    channel_data = upscaled_image[:, :, channel]

                    # Stronger filtering away from edges, lighter near edges
                    filter_strength = (1.0 - edge_guidance) * 20 + 5

                    # Apply adaptive bilateral filtering
                    for i in range(0, channel_data.shape[0], 50):
                        for j in range(0, channel_data.shape[1], 50):
                            end_i = min(i + 50, channel_data.shape[0])
                            end_j = min(j + 50, channel_data.shape[1])

                            local_strength = int(np.mean(filter_strength[i:end_i, j:end_j]))
                            local_patch = channel_data[i:end_i, j:end_j]

                            refined_patch = cv2.bilateralFilter(local_patch, 9, local_strength, local_strength)
                            refined[i:end_i, j:end_j, channel] = refined_patch
            else:
                # Grayscale
                filter_strength = (1.0 - edge_guidance) * 20 + 5
                refined = cv2.bilateralFilter(upscaled_image, 9,
                                            int(np.mean(filter_strength)),
                                            int(np.mean(filter_strength)))

            return refined

        except Exception as e:
            print(f"Edge refinement error: {e}")
            return upscaled_image

    def super_resolution_upscaling(self, image_array, scale_factor, logo_type="styled"):
        """Advanced super-resolution for styled logos with gradients and effects"""
        try:
            print(f"Advanced super-resolution upscaling: {scale_factor}x...")

            # Use progressive upscaling for large scale factors
            if scale_factor > 3:
                # Multi-stage upscaling for better quality
                current_image = image_array.copy()
                remaining_scale = scale_factor

                while remaining_scale > 1:
                    step_scale = min(2, remaining_scale)
                    current_image = self.high_quality_step_upscale(current_image, step_scale)
                    remaining_scale = remaining_scale / step_scale

                return current_image
            else:
                # Single-stage for smaller scales
                return self.high_quality_step_upscale(image_array, scale_factor)

        except Exception as e:
            print(f"Super-resolution error: {e}")
            return cv2.resize(image_array,
                            (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                            interpolation=cv2.INTER_LANCZOS4)

    def high_quality_step_upscale(self, image_array, step_scale):
        """High-quality single step upscaling"""
        try:
            # Use LANCZOS4 with post-processing enhancement
            upscaled = cv2.resize(
                image_array,
                (int(image_array.shape[1] * step_scale), int(image_array.shape[0] * step_scale)),
                interpolation=cv2.INTER_LANCZOS4
            )

            # Apply enhancement for styled logos
            enhanced = self.enhance_styled_logo(upscaled)
            return enhanced

        except Exception as e:
            print(f"Step upscaling error: {e}")
            return cv2.resize(image_array,
                            (int(image_array.shape[1] * step_scale), int(image_array.shape[0] * step_scale)),
                            interpolation=cv2.INTER_LANCZOS4)

    def enhance_styled_logo(self, image_array):
        """Enhancement specifically for styled logos with gradients"""
        try:
            if len(image_array.shape) == 3:
                channels = image_array.shape[2]
                result = image_array.copy().astype(np.float32)

                for c in range(min(3, channels)):
                    channel = result[:, :, c]

                    # Gentle enhancement that preserves gradients
                    # Use very mild unsharp masking
                    blurred = cv2.GaussianBlur(channel, (5, 5), 1.5)
                    enhanced = channel + 0.3 * (channel - blurred)

                    result[:, :, c] = np.clip(enhanced, 0, 255)

                return result.astype(np.uint8)
            else:
                # Grayscale
                blurred = cv2.GaussianBlur(image_array.astype(np.float32), (5, 5), 1.5)
                enhanced = image_array.astype(np.float32) + 0.3 * (image_array.astype(np.float32) - blurred)
                return np.clip(enhanced, 0, 255).astype(np.uint8)

        except Exception as e:
            print(f"Styled logo enhancement error: {e}")
            return image_array

            # If scale factor is large, do it in steps
            steps = []
            remaining_scale = scale_factor

            while remaining_scale > 1:
                if remaining_scale >= 4:
                    steps.append(2)
                    remaining_scale = remaining_scale / 2
                elif remaining_scale >= 2:
                    steps.append(2)
                    remaining_scale = remaining_scale / 2
                else:
                    steps.append(remaining_scale)
                    remaining_scale = 1

            print(f"Super-resolution steps: {steps}")

            for step_scale in steps:
                # High-quality initial upscaling
                if len(current_image.shape) == 3:
                    new_size = (int(current_image.shape[1] * step_scale),
                               int(current_image.shape[0] * step_scale))
                    upscaled = cv2.resize(current_image, new_size, interpolation=cv2.INTER_CUBIC)
                else:
                    new_size = (int(current_image.shape[1] * step_scale),
                               int(current_image.shape[0] * step_scale))
                    upscaled = cv2.resize(current_image, new_size, interpolation=cv2.INTER_CUBIC)

                # Apply super-resolution enhancement
                upscaled = self.apply_super_resolution_enhancement(upscaled, current_image)

                current_image = upscaled

            return current_image

        except Exception as e:
            print(f"Super-resolution error: {e}")
            return cv2.resize(image_array,
                            (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                            interpolation=cv2.INTER_CUBIC)

    def apply_super_resolution_enhancement(self, upscaled, original):
        """Apply enhancement techniques mimicking super-resolution"""
        try:
            # 1. Sharpening filter
            kernel_sharpen = np.array([[-1,-1,-1],
                                     [-1, 9,-1],
                                     [-1,-1,-1]])

            if len(upscaled.shape) == 3:
                enhanced = upscaled.copy()
                for channel in range(upscaled.shape[2]):
                    enhanced[:, :, channel] = cv2.filter2D(upscaled[:, :, channel], -1, kernel_sharpen)
            else:
                enhanced = cv2.filter2D(upscaled, -1, kernel_sharpen)

            # 2. Blend with original for natural look
            enhanced = cv2.addWeighted(upscaled, 0.7, enhanced, 0.3, 0)

            # 3. Edge enhancement
            if len(enhanced.shape) == 3:
                gray = cv2.cvtColor(enhanced, cv2.COLOR_RGB2GRAY)
            else:
                gray = enhanced

            edges = cv2.Canny(gray, 100, 200)
            edges = cv2.dilate(edges, np.ones((2,2), np.uint8))

            # Enhance edges
            if len(enhanced.shape) == 3:
                for channel in range(enhanced.shape[2]):
                    enhanced[:, :, channel] = np.where(edges > 0,
                                                     np.clip(enhanced[:, :, channel] * 1.1, 0, 255),
                                                     enhanced[:, :, channel])
            else:
                enhanced = np.where(edges > 0,
                                  np.clip(enhanced * 1.1, 0, 255),
                                  enhanced)

            return enhanced.astype(np.uint8)

        except Exception as e:
            print(f"Super-resolution enhancement error: {e}")
            return upscaled

    def pixel_art_upscaling(self, image_array, scale_factor):
        """Perfect pixel art upscaling for sharp logos"""
        try:
            # Use nearest neighbor for pixel-perfect scaling
            upscaled = cv2.resize(image_array,
                                (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                                interpolation=cv2.INTER_NEAREST)

            # Apply advanced pixel art techniques
            upscaled = self.apply_pixel_art_enhancement(upscaled, scale_factor)

            return upscaled

        except Exception as e:
            print(f"Pixel art upscaling error: {e}")
            return cv2.resize(image_array,
                            (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                            interpolation=cv2.INTER_NEAREST)

    def apply_pixel_art_enhancement(self, upscaled, scale_factor):
        """Apply pixel art enhancement techniques"""
        try:
            # For pixel art, we want to maintain crisp edges but smooth out aliasing
            enhanced = upscaled.copy()

            # Light anti-aliasing only on diagonal edges
            if len(upscaled.shape) == 3:
                gray = cv2.cvtColor(upscaled, cv2.COLOR_RGB2GRAY)
            else:
                gray = upscaled

            # Detect diagonal edges
            kernel_diag1 = np.array([[1, 0, -1],
                                   [0, 0, 0],
                                   [-1, 0, 1]])
            kernel_diag2 = np.array([[-1, 0, 1],
                                   [0, 0, 0],
                                   [1, 0, -1]])

            diag_edges1 = cv2.filter2D(gray, -1, kernel_diag1)
            diag_edges2 = cv2.filter2D(gray, -1, kernel_diag2)

            diag_edges = np.abs(diag_edges1) + np.abs(diag_edges2)
            diag_mask = diag_edges > 30

            # Apply light smoothing only to diagonal edges
            if len(enhanced.shape) == 3:
                for channel in range(enhanced.shape[2]):
                    smoothed_channel = cv2.GaussianBlur(enhanced[:, :, channel], (3, 3), 0.5)
                    enhanced[:, :, channel] = np.where(diag_mask,
                                                     (enhanced[:, :, channel] * 0.7 + smoothed_channel * 0.3).astype(np.uint8),
                                                     enhanced[:, :, channel])
            else:
                smoothed = cv2.GaussianBlur(enhanced, (3, 3), 0.5)
                enhanced = np.where(diag_mask,
                                  (enhanced * 0.7 + smoothed * 0.3).astype(np.uint8),
                                  enhanced)

            return enhanced

        except Exception as e:
            print(f"Pixel art enhancement error: {e}")
            return upscaled

    def hybrid_upscaling(self, image_array, scale_factor, logo_type="styled"):
        """Hybrid approach combining multiple methods"""
        try:
            # Analyze image to determine best approach
            analysis = self.analyze_image_characteristics(image_array)

            print(f"Image analysis: {analysis}")

            if analysis['is_pixel_art']:
                primary_result = self.pixel_art_upscaling(image_array, scale_factor)
            elif analysis['has_smooth_curves']:
                primary_result = self.super_resolution_upscaling(image_array, scale_factor)
            else:
                primary_result = self.smart_edge_upscaling(image_array, scale_factor)

            # Always apply secondary enhancement
            secondary_result = self.smart_edge_upscaling(image_array, scale_factor)

            # Blend results based on image characteristics
            if analysis['edge_density'] > 0.3:
                # High edge density - favor edge preservation
                final_result = cv2.addWeighted(primary_result, 0.7, secondary_result, 0.3, 0)
            else:
                # Low edge density - favor smoothness
                final_result = cv2.addWeighted(primary_result, 0.8, secondary_result, 0.2, 0)

            return final_result

        except Exception as e:
            print(f"Hybrid upscaling error: {e}")
            return self.smart_edge_upscaling(image_array, scale_factor)

    def analyze_image_characteristics(self, image_array):
        """Analyze image to determine optimal upscaling strategy"""
        try:
            # Convert to grayscale for analysis
            if len(image_array.shape) == 3:
                gray = cv2.cvtColor(image_array[:, :, :3], cv2.COLOR_RGB2GRAY)
            else:
                gray = image_array

            # Detect edges
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size

            # Check for pixel art characteristics
            unique_colors = len(np.unique(gray))
            total_pixels = gray.size
            color_ratio = unique_colors / total_pixels

            is_pixel_art = color_ratio < 0.1 and edge_density > 0.2

            # Check for smooth curves
            # Use Hough circles to detect curved elements
            circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20,
                                     param1=50, param2=30, minRadius=5, maxRadius=50)
            has_smooth_curves = circles is not None

            return {
                'edge_density': edge_density,
                'color_ratio': color_ratio,
                'is_pixel_art': is_pixel_art,
                'has_smooth_curves': has_smooth_curves,
                'unique_colors': unique_colors
            }

        except Exception as e:
            print(f"Image analysis error: {e}")
            return {
                'edge_density': 0.2,
                'color_ratio': 0.5,
                'is_pixel_art': False,
                'has_smooth_curves': False,
                'unique_colors': 100
            }

    def preserve_contrast(self, upscaled_image, original_image):
        """Preserve and enhance contrast from original image"""
        try:
            # Calculate contrast metrics of original
            if len(original_image.shape) == 3:
                original_gray = cv2.cvtColor(original_image, cv2.COLOR_RGB2GRAY)
            else:
                original_gray = original_image

            if len(upscaled_image.shape) == 3:
                upscaled_gray = cv2.cvtColor(upscaled_image, cv2.COLOR_RGB2GRAY)
            else:
                upscaled_gray = upscaled_image

            # Calculate original contrast
            original_std = np.std(original_gray)
            upscaled_std = np.std(upscaled_gray)

            if upscaled_std > 0:
                contrast_ratio = original_std / upscaled_std

                # Apply contrast adjustment
                if len(upscaled_image.shape) == 3:
                    enhanced = upscaled_image.copy().astype(np.float32)

                    for channel in range(upscaled_image.shape[2]):
                        mean_val = np.mean(enhanced[:, :, channel])
                        enhanced[:, :, channel] = (enhanced[:, :, channel] - mean_val) * contrast_ratio * self.contrast_boost + mean_val
                        enhanced[:, :, channel] = np.clip(enhanced[:, :, channel], 0, 255)

                    return enhanced.astype(np.uint8)
                else:
                    enhanced = upscaled_image.astype(np.float32)
                    mean_val = np.mean(enhanced)
                    enhanced = (enhanced - mean_val) * contrast_ratio * self.contrast_boost + mean_val
                    return np.clip(enhanced, 0, 255).astype(np.uint8)

            return upscaled_image

        except Exception as e:
            print(f"Contrast preservation error: {e}")
            return upscaled_image

    def enhance_edges(self, image_array):
        """Final edge enhancement for crisp logo appearance"""
        try:
            # Detect edges
            if len(image_array.shape) == 3:
                gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = image_array

            edges = cv2.Canny(gray, 100, 200)

            # Create edge enhancement mask
            edge_mask = cv2.dilate(edges, np.ones((3,3), np.uint8))

            enhanced = image_array.copy()

            # Enhance contrast near edges
            if len(enhanced.shape) == 3:
                for channel in range(enhanced.shape[2]):
                    channel_data = enhanced[:, :, channel].astype(np.float32)

                    # Apply unsharp mask near edges
                    blurred = cv2.GaussianBlur(channel_data, (3, 3), 1.0)
                    unsharp = channel_data + (channel_data - blurred) * 0.5

                    # Apply enhancement only near edges
                    enhanced[:, :, channel] = np.where(edge_mask > 0,
                                                     np.clip(unsharp, 0, 255),
                                                     channel_data).astype(np.uint8)
            else:
                enhanced_float = enhanced.astype(np.float32)
                blurred = cv2.GaussianBlur(enhanced_float, (3, 3), 1.0)
                unsharp = enhanced_float + (enhanced_float - blurred) * 0.5

                enhanced = np.where(edge_mask > 0,
                                  np.clip(unsharp, 0, 255),
                                  enhanced_float).astype(np.uint8)

            return enhanced

        except Exception as e:
            print(f"Edge enhancement error: {e}")
            return image_array

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

    def flat_color_sharpening(self, original_image, scale_factor):
        """
        PRINT-QUALITY logo upscaling for flat color logos
        Uses multi-stage approach for clean, professional results
        """
        try:
            print(f"PRINT-QUALITY logo upscaling: {scale_factor}x...")

            # Step 1: Edge-directed super-sampling upscaling
            upscaled = self.edge_directed_upscale(original_image, scale_factor)

            # Step 2: Anti-aliasing and smoothing
            smoothed = self.smart_anti_aliasing(upscaled, scale_factor)

            # Step 3: Print-quality finishing
            final_result = self.print_quality_finishing(smoothed, original_image, scale_factor)

            print("Print-quality logo upscaling completed")
            return final_result

        except Exception as e:
            print(f"Print-quality upscaling error: {e}")
            # Fallback to best available method
            return cv2.resize(original_image,
                            (original_image.shape[1] * scale_factor, original_image.shape[0] * scale_factor),
                            interpolation=cv2.INTER_LANCZOS4)

    def edge_directed_upscale(self, image_array, scale_factor):
        """AI-STYLE edge reconstruction with sub-pixel precision"""
        try:
            print("Applying AI-style edge reconstruction...")

            # Step 1: Super-sampling for sub-pixel precision
            supersample_factor = 2  # Render at 2x then downsample
            target_size = (
                image_array.shape[1] * scale_factor * supersample_factor,
                image_array.shape[0] * scale_factor * supersample_factor
            )

            # Initial super-sampled upscale
            supersampled = cv2.resize(image_array, target_size, interpolation=cv2.INTER_CUBIC)

            # Step 2: Edge reconstruction using multiple orientations
            reconstructed = self.ai_edge_reconstruction(supersampled)

            # Step 3: Intelligent downsampling with anti-aliasing
            final_size = (
                image_array.shape[1] * scale_factor,
                image_array.shape[0] * scale_factor
            )

            # Use area interpolation for optimal downsampling quality
            result = cv2.resize(reconstructed, final_size, interpolation=cv2.INTER_AREA)

            return result

        except Exception as e:
            print(f"AI-style upscaling error: {e}")
            return cv2.resize(image_array,
                            (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                            interpolation=cv2.INTER_LANCZOS4)

    def ai_edge_reconstruction(self, image_array):
        """Reconstruct edges using AI-inspired techniques"""
        try:
            print("Reconstructing edges with AI-style processing...")

            if len(image_array.shape) == 3:
                channels = image_array.shape[2]
                result = image_array.copy().astype(np.float32)

                for c in range(min(3, channels)):
                    channel = result[:, :, c]

                    # Multi-orientation edge detection
                    edges = self.detect_multi_orientation_edges(channel)

                    # Curve reconstruction
                    reconstructed = self.reconstruct_smooth_curves(channel, edges)

                    # Straight line enhancement
                    enhanced = self.enhance_straight_lines(reconstructed, edges)

                    result[:, :, c] = enhanced

                return np.clip(result, 0, 255).astype(np.uint8)
            else:
                # Grayscale
                edges = self.detect_multi_orientation_edges(image_array.astype(np.float32))
                reconstructed = self.reconstruct_smooth_curves(image_array.astype(np.float32), edges)
                enhanced = self.enhance_straight_lines(reconstructed, edges)
                return np.clip(enhanced, 0, 255).astype(np.uint8)

        except Exception as e:
            print(f"Edge reconstruction error: {e}")
            return image_array

    def detect_multi_orientation_edges(self, channel):
        """Detect edges at multiple orientations like AI upscalers"""
        try:
            # Create multiple edge detection kernels for different orientations
            kernels = []

            # Horizontal and vertical (standard)
            kernels.append(np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]]))  # Horizontal
            kernels.append(np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]))  # Vertical

            # Diagonal orientations
            kernels.append(np.array([[-2, -1, 0], [-1, 0, 1], [0, 1, 2]]))   # Diagonal 1
            kernels.append(np.array([[0, -1, -2], [1, 0, -1], [2, 1, 0]]))   # Diagonal 2

            # 45-degree rotated edges
            kernels.append(np.array([[-1, -1, 0], [-1, 0, 1], [0, 1, 1]]))   # 45°
            kernels.append(np.array([[0, -1, -1], [1, 0, -1], [1, 1, 0]]))   # 135°

            # Apply all kernels and combine
            edge_responses = []
            for kernel in kernels:
                response = cv2.filter2D(channel, cv2.CV_64F, kernel)
                edge_responses.append(np.abs(response))

            # Combine edge responses - use maximum response
            combined_edges = np.maximum.reduce(edge_responses)

            # Normalize
            if np.max(combined_edges) > 0:
                combined_edges = combined_edges / np.max(combined_edges)

            return combined_edges

        except Exception as e:
            print(f"Multi-orientation edge detection error: {e}")
            return np.zeros_like(channel)

    def reconstruct_smooth_curves(self, channel, edge_map):
        """Reconstruct smooth curves from edge information"""
        try:
            # Use guided filtering for edge-aware smoothing
            # This preserves edges while smoothing curves
            radius = 4
            epsilon = 0.01

            # Approximate guided filter using bilateral filtering
            smoothed = cv2.bilateralFilter(
                channel.astype(np.uint8),
                d=radius * 2,
                sigmaColor=50,
                sigmaSpace=50
            ).astype(np.float32)

            # Blend based on edge strength
            # Strong edges: keep original, weak edges: use smoothed
            edge_strength = np.clip(edge_map * 2, 0, 1)
            result = edge_strength * channel + (1 - edge_strength) * smoothed

            return result

        except Exception as e:
            print(f"Curve reconstruction error: {e}")
            return channel

    def enhance_straight_lines(self, channel, edge_map):
        """Enhance straight lines and geometric shapes"""
        try:
            # Detect straight lines using morphological operations
            # Horizontal lines
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1))
            h_lines = cv2.morphologyEx(edge_map.astype(np.uint8), cv2.MORPH_OPEN, h_kernel)

            # Vertical lines
            v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
            v_lines = cv2.morphologyEx(edge_map.astype(np.uint8), cv2.MORPH_OPEN, v_kernel)

            # Diagonal lines
            d1_kernel = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.uint8)
            d2_kernel = np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]], dtype=np.uint8)

            # Combine line detections
            line_mask = ((h_lines > 0) | (v_lines > 0)).astype(np.float32)

            # Apply extra sharpening to detected lines
            if np.any(line_mask > 0):
                blurred = cv2.GaussianBlur(channel, (3, 3), 0.5)
                sharpened = channel + 1.0 * (channel - blurred)

                # Apply sharpening only to line areas
                result = line_mask * sharpened + (1 - line_mask) * channel
            else:
                result = channel

            return result

        except Exception as e:
            print(f"Line enhancement error: {e}")
            return channel

    def smart_anti_aliasing(self, image_array, scale_factor):
        """Smart anti-aliasing for smooth edges without blur"""
        try:
            print("Applying smart anti-aliasing...")

            if len(image_array.shape) == 3:
                channels = image_array.shape[2]
                result = image_array.copy().astype(np.float32)

                for c in range(min(3, channels)):
                    channel = result[:, :, c]

                    # Apply bilateral filtering for edge-preserving smoothing
                    # This smooths areas while preserving sharp edges
                    smoothed = cv2.bilateralFilter(
                        channel.astype(np.uint8),
                        d=5,           # Neighborhood diameter
                        sigmaColor=20, # Color similarity threshold
                        sigmaSpace=20  # Spatial similarity threshold
                    ).astype(np.float32)

                    result[:, :, c] = smoothed

                return result.astype(np.uint8)
            else:
                # Grayscale
                return cv2.bilateralFilter(
                    image_array,
                    d=5,
                    sigmaColor=20,
                    sigmaSpace=20
                )

        except Exception as e:
            print(f"Anti-aliasing error: {e}")
            return image_array

    def print_quality_finishing(self, image_array, original_image, scale_factor):
        """PROFESSIONAL print-quality finishing with color optimization"""
        try:
            print("Applying professional print-quality finishing...")

            # Step 1: Color space optimization for print/display
            result = self.optimize_color_space(image_array)

            # Step 2: Professional contrast enhancement
            result = self.professional_contrast_enhancement(result)

            # Step 3: Sub-pixel edge refinement
            result = self.subpixel_edge_refinement(result, scale_factor)

            # Step 4: Print-optimized artifact removal
            result = self.print_artifact_removal(result)

            return result

        except Exception as e:
            print(f"Print-quality finishing error: {e}")
            return image_array

    def optimize_color_space(self, image_array):
        """Optimize colors for both print and display"""
        try:
            if len(image_array.shape) == 3:
                channels = image_array.shape[2]

                # Convert to LAB color space for perceptual processing
                if channels >= 3:
                    # Convert RGB to LAB for perceptual color enhancement
                    lab = cv2.cvtColor(image_array, cv2.COLOR_RGB2LAB).astype(np.float32)

                    # Enhance L channel (luminance) for better contrast
                    l_channel = lab[:, :, 0]
                    l_enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(
                        l_channel.astype(np.uint8)
                    ).astype(np.float32)

                    lab[:, :, 0] = l_enhanced

                    # Convert back to RGB
                    result = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

                    # Preserve alpha channel if present
                    if channels == 4:
                        result = np.dstack([result, image_array[:, :, 3]])

                    return result
                else:
                    return image_array
            else:
                # Grayscale - apply CLAHE for local contrast enhancement
                return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(image_array)

        except Exception as e:
            print(f"Color space optimization error: {e}")
            return image_array

    def professional_contrast_enhancement(self, image_array):
        """Professional-grade contrast enhancement for print"""
        try:
            if len(image_array.shape) == 3:
                channels = image_array.shape[2]
                result = image_array.copy().astype(np.float32)

                for c in range(min(3, channels)):
                    channel = result[:, :, c]

                    # Gamma correction for print optimization
                    gamma = 1.1  # Slight gamma boost for print clarity
                    channel_norm = channel / 255.0
                    gamma_corrected = np.power(channel_norm, 1.0/gamma) * 255.0

                    # Selective histogram stretching
                    # Only stretch if the range is too narrow (low contrast)
                    min_val = np.percentile(gamma_corrected, 1)
                    max_val = np.percentile(gamma_corrected, 99)

                    if (max_val - min_val) < 200:  # Low contrast detection
                        # Apply gentle stretching
                        if max_val > min_val:
                            stretched = (gamma_corrected - min_val) * (240.0 / (max_val - min_val)) + 15
                            channel = np.clip(stretched, 0, 255)
                        else:
                            channel = gamma_corrected
                    else:
                        channel = gamma_corrected

                    result[:, :, c] = channel

                return result.astype(np.uint8)
            else:
                # Grayscale gamma correction
                gamma = 1.1
                normalized = image_array.astype(np.float32) / 255.0
                gamma_corrected = np.power(normalized, 1.0/gamma) * 255.0
                return np.clip(gamma_corrected, 0, 255).astype(np.uint8)

        except Exception as e:
            print(f"Professional contrast enhancement error: {e}")
            return image_array

    def subpixel_edge_refinement(self, image_array, scale_factor):
        """Sub-pixel level edge refinement for ultra-smooth results"""
        try:
            print("Applying sub-pixel edge refinement...")

            if len(image_array.shape) == 3:
                channels = image_array.shape[2]
                result = image_array.copy().astype(np.float32)

                for c in range(min(3, channels)):
                    channel = result[:, :, c]

                    # Use very precise edge detection
                    grad_x = cv2.Sobel(channel, cv2.CV_64F, 1, 0, ksize=3)
                    grad_y = cv2.Sobel(channel, cv2.CV_64F, 0, 1, ksize=3)

                    # Calculate gradient magnitude and direction
                    magnitude = np.sqrt(grad_x**2 + grad_y**2)
                    direction = np.arctan2(grad_y, grad_x)

                    # Apply sub-pixel shift based on gradient direction
                    # This simulates sub-pixel rendering
                    kernel_size = max(1, scale_factor // 2)
                    if kernel_size > 0:
                        # Create directional blur kernel
                        kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size**2)
                        refined = cv2.filter2D(channel, -1, kernel)

                        # Blend based on edge strength
                        edge_mask = magnitude > np.percentile(magnitude, 85)
                        alpha = 0.3  # Subtle refinement

                        channel[edge_mask] = (1-alpha) * channel[edge_mask] + alpha * refined[edge_mask]

                    result[:, :, c] = channel

                return result.astype(np.uint8)
            else:
                # Grayscale sub-pixel refinement
                grad_x = cv2.Sobel(image_array.astype(np.float32), cv2.CV_64F, 1, 0, ksize=3)
                grad_y = cv2.Sobel(image_array.astype(np.float32), cv2.CV_64F, 0, 1, ksize=3)
                magnitude = np.sqrt(grad_x**2 + grad_y**2)

                refined = cv2.GaussianBlur(image_array.astype(np.float32), (3, 3), 0.5)
                edge_mask = magnitude > np.percentile(magnitude, 85)

                result = image_array.astype(np.float32)
                result[edge_mask] = 0.7 * result[edge_mask] + 0.3 * refined[edge_mask]

                return result.astype(np.uint8)

        except Exception as e:
            print(f"Sub-pixel refinement error: {e}")
            return image_array

    def print_artifact_removal(self, image_array):
        """Remove artifacts specifically for print quality"""
        try:
            if len(image_array.shape) == 3:
                channels = image_array.shape[2]
                result = image_array.copy()

                # Use elliptical kernels for more natural cleanup
                small_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
                medium_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

                for c in range(min(3, channels)):
                    channel = result[:, :, c]

                    # Remove salt-and-pepper noise
                    denoised = cv2.medianBlur(channel, 3)

                    # Only apply denoising where needed (high frequency noise areas)
                    high_freq = cv2.Laplacian(channel, cv2.CV_64F)
                    noise_mask = np.abs(high_freq) > np.percentile(np.abs(high_freq), 95)

                    channel[noise_mask] = denoised[noise_mask]

                    # Final morphological cleanup
                    channel = cv2.morphologyEx(channel, cv2.MORPH_OPEN, small_kernel)
                    channel = cv2.morphologyEx(channel, cv2.MORPH_CLOSE, medium_kernel)

                    result[:, :, c] = channel

                return result
            else:
                # Grayscale artifact removal
                denoised = cv2.medianBlur(image_array, 3)
                high_freq = cv2.Laplacian(image_array, cv2.CV_64F)
                noise_mask = np.abs(high_freq) > np.percentile(np.abs(high_freq), 95)

                result = image_array.copy()
                result[noise_mask] = denoised[noise_mask]

                # Morphological cleanup
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
                result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel)
                result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel)

                return result

        except Exception as e:
            print(f"Print artifact removal error: {e}")
            return image_array

    def process_background(self, image_array, processing_type, tolerance):
        """
        Intelligent background processing for logos
        - remove: Makes background transparent
        - flatten: Flattens background to average color
        """
        try:
            print(f"Processing background: {processing_type} with tolerance {tolerance}")

            if processing_type == "remove":
                return self.remove_background(image_array, tolerance)
            elif processing_type == "flatten":
                return self.flatten_background(image_array, tolerance)
            else:
                return image_array

        except Exception as e:
            print(f"Background processing error: {e}")
            return image_array

    def remove_background(self, image_array, tolerance):
        """Intelligent background removal that preserves logo upscaling"""
        try:
            # Detect background automatically by analyzing corners and edges
            background_colors = self.detect_background_colors(image_array)

            if len(image_array.shape) == 3:
                channels = image_array.shape[2]

                # Ensure we have alpha channel
                if channels == 3:
                    # Add alpha channel (fully opaque initially)
                    alpha_channel = np.ones((image_array.shape[0], image_array.shape[1], 1), dtype=np.uint8) * 255
                    result = np.concatenate([image_array, alpha_channel], axis=2)
                else:
                    result = image_array.copy()

                # Create mask for background pixels
                background_mask = self.create_background_mask(image_array, background_colors, tolerance)

                # Make background transparent
                result[background_mask, 3] = 0  # Set alpha to 0

                return result
            else:
                # Grayscale - convert to RGBA
                rgb = np.stack([image_array, image_array, image_array], axis=2)
                alpha = np.ones((image_array.shape[0], image_array.shape[1], 1), dtype=np.uint8) * 255
                result = np.concatenate([rgb, alpha], axis=2)

                # Detect background in grayscale
                background_value = self.detect_background_grayscale(image_array)
                mask = np.abs(image_array - background_value) <= (tolerance * 2.55)
                result[mask, 3] = 0

                return result

        except Exception as e:
            print(f"Background removal error: {e}")
            return image_array

    def flatten_background(self, image_array, tolerance):
        """Flatten background to average color"""
        try:
            # Detect background colors
            background_colors = self.detect_background_colors(image_array)

            if len(image_array.shape) == 3:
                result = image_array.copy()

                # Create mask for background pixels
                background_mask = self.create_background_mask(image_array, background_colors, tolerance)

                if np.any(background_mask):
                    # Calculate average background color
                    background_pixels = image_array[background_mask]
                    if len(background_pixels) > 0:
                        avg_color = np.mean(background_pixels, axis=0).astype(np.uint8)

                        # Apply average color to all background pixels
                        for c in range(min(3, image_array.shape[2])):
                            result[background_mask, c] = avg_color[c]

                return result
            else:
                # Grayscale flattening
                result = image_array.copy()
                background_value = self.detect_background_grayscale(image_array)
                mask = np.abs(image_array - background_value) <= (tolerance * 2.55)

                if np.any(mask):
                    avg_value = np.mean(image_array[mask])
                    result[mask] = avg_value

                return result

        except Exception as e:
            print(f"Background flattening error: {e}")
            return image_array

    def detect_background_colors(self, image_array):
        """Intelligently detect background colors by analyzing image edges"""
        try:
            if len(image_array.shape) == 3:
                channels = image_array.shape[2]
                height, width = image_array.shape[:2]

                # Sample pixels from corners and edges (likely background)
                corner_size = min(20, height//4, width//4)
                edge_samples = []

                # Top-left corner
                edge_samples.extend(image_array[:corner_size, :corner_size].reshape(-1, channels))
                # Top-right corner
                edge_samples.extend(image_array[:corner_size, -corner_size:].reshape(-1, channels))
                # Bottom-left corner
                edge_samples.extend(image_array[-corner_size:, :corner_size].reshape(-1, channels))
                # Bottom-right corner
                edge_samples.extend(image_array[-corner_size:, -corner_size:].reshape(-1, channels))

                # Top edge
                edge_samples.extend(image_array[:5, :].reshape(-1, channels))
                # Bottom edge
                edge_samples.extend(image_array[-5:, :].reshape(-1, channels))
                # Left edge
                edge_samples.extend(image_array[:, :5].reshape(-1, channels))
                # Right edge
                edge_samples.extend(image_array[:, -5:].reshape(-1, channels))

                edge_samples = np.array(edge_samples)

                # Find most common colors in edge samples
                background_colors = []
                unique_colors, counts = np.unique(edge_samples.reshape(-1, channels), axis=0, return_counts=True)

                # Sort by frequency and take top candidates
                sorted_indices = np.argsort(counts)[::-1]
                for i in sorted_indices[:3]:  # Top 3 most common colors
                    background_colors.append(unique_colors[i])

                return np.array(background_colors)
            else:
                # Grayscale
                return np.array([[self.detect_background_grayscale(image_array)]])

        except Exception as e:
            print(f"Background color detection error: {e}")
            return np.array([[255, 255, 255]])  # Default to white

    def detect_background_grayscale(self, image_array):
        """Detect background value in grayscale image"""
        try:
            height, width = image_array.shape
            corner_size = min(10, height//4, width//4)

            # Sample corners
            corners = []
            corners.extend(image_array[:corner_size, :corner_size].flatten())
            corners.extend(image_array[:corner_size, -corner_size:].flatten())
            corners.extend(image_array[-corner_size:, :corner_size].flatten())
            corners.extend(image_array[-corner_size:, -corner_size:].flatten())

            # Return most common value
            unique_values, counts = np.unique(corners, return_counts=True)
            return unique_values[np.argmax(counts)]

        except Exception as e:
            print(f"Grayscale background detection error: {e}")
            return 255

    def create_background_mask(self, image_array, background_colors, tolerance):
        """Create mask for background pixels"""
        try:
            if len(image_array.shape) == 3:
                channels = min(3, image_array.shape[2])
                height, width = image_array.shape[:2]
                mask = np.zeros((height, width), dtype=bool)

                for bg_color in background_colors:
                    # Calculate color distance for each pixel
                    pixel_colors = image_array[:, :, :channels]
                    distances = np.sqrt(np.sum((pixel_colors - bg_color[:channels])**2, axis=2))

                    # Add pixels within tolerance to mask
                    color_mask = distances <= (tolerance * 2.55)  # Convert percentage to 255 scale
                    mask = mask | color_mask

                return mask
            else:
                # Grayscale
                bg_value = background_colors[0][0] if len(background_colors) > 0 else 255
                return np.abs(image_array - bg_value) <= (tolerance * 2.55)

        except Exception as e:
            print(f"Background mask creation error: {e}")
            return np.zeros(image_array.shape[:2], dtype=bool)

    def extract_logo_colors(self, image_array):
        """Extract the distinct solid colors from the original logo - SIMPLIFIED"""
        try:
            if len(image_array.shape) == 3:
                channels = image_array.shape[2]

                # Get pixels from the image
                pixels = image_array.reshape(-1, channels)

                # Remove transparent pixels if alpha channel exists
                if channels == 4:
                    alpha_mask = pixels[:, 3] > 127
                    valid_pixels = pixels[alpha_mask][:, :3]  # RGB only
                else:
                    valid_pixels = pixels

                # Use histogram approach for major colors
                unique_colors = []

                # Sample much less aggressively to avoid noise
                sample_pixels = valid_pixels[::500]  # Much larger sampling interval

                for pixel in sample_pixels:
                    pixel_color = pixel[:3] if channels == 4 else pixel
                    is_new_color = True

                    for existing_color in unique_colors:
                        # Use larger tolerance to group similar colors
                        color_distance = np.sqrt(np.sum((pixel_color.astype(float) - existing_color.astype(float))**2))
                        if color_distance < 30:  # Larger tolerance
                            is_new_color = False
                            break

                    if is_new_color:
                        unique_colors.append(pixel_color)

                    # Limit to fewer colors for cleaner results
                    if len(unique_colors) >= 6:
                        break

                if len(unique_colors) == 0:
                    # Fallback - get most common colors
                    unique_colors = [[0, 0, 0], [255, 255, 255], [128, 128, 128]]

                print(f"Color analysis: {len(unique_colors)} distinct colors found")
                return np.array(unique_colors)

            return np.array([[128]])  # Fallback for grayscale

        except Exception as e:
            print(f"Color extraction error: {e}")
            return np.array([[0], [128], [255]])  # Basic fallback

    def pre_sharpen_original(self, image_array, color_palette):
        """CONSERVATIVE pre-sharpening - just basic edge enhancement"""
        try:
            print("Conservative pre-sharpening original image...")

            # Skip color snapping entirely for now - just do basic edge enhancement
            # Apply gentle unsharp masking to enhance edges without creating artifacts

            if len(image_array.shape) == 3:
                # Apply mild unsharp masking
                blurred = cv2.GaussianBlur(image_array, (3, 3), 1.0)
                sharpened = image_array.astype(np.float32) + 0.5 * (image_array.astype(np.float32) - blurred.astype(np.float32))
                sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

                return sharpened
            else:
                # Grayscale
                blurred = cv2.GaussianBlur(image_array, (3, 3), 1.0)
                sharpened = image_array.astype(np.float32) + 0.5 * (image_array.astype(np.float32) - blurred.astype(np.float32))
                return np.clip(sharpened, 0, 255).astype(np.uint8)

        except Exception as e:
            print(f"Pre-sharpening error: {e}")
            return image_array

    def intelligent_flat_upscale(self, image_array, scale_factor, color_palette):
        """Upscale with intelligent edge preservation for flat colors"""
        try:
            print(f"Intelligent upscaling by {scale_factor}x...")

            # Use high-quality interpolation that preserves edges
            upscaled = cv2.resize(
                image_array,
                (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                interpolation=cv2.INTER_CUBIC  # Good balance of quality and speed
            )

            return upscaled

        except Exception as e:
            print(f"Intelligent upscaling error: {e}")
            return cv2.resize(image_array,
                            (image_array.shape[1] * scale_factor, image_array.shape[0] * scale_factor),
                            interpolation=cv2.INTER_LINEAR)

    def post_sharpen_upscaled(self, image_array, color_palette, scale_factor):
        """Smart post-sharpening using the identified color palette"""
        try:
            print("Smart post-sharpening upscaled image...")

            # Step 1: Apply moderate unsharp masking for edge enhancement
            blurred = cv2.GaussianBlur(image_array, (3, 3), 1.0)
            sharpened = image_array.astype(np.float32) + 0.8 * (image_array.astype(np.float32) - blurred.astype(np.float32))
            sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

            # Step 2: NOW apply intelligent color snapping using the palette
            if len(color_palette) > 0 and len(image_array.shape) == 3:
                result = self.intelligent_color_snap(sharpened, color_palette)
                return result
            else:
                return sharpened

        except Exception as e:
            print(f"Post-sharpening error: {e}")
            return image_array

    def intelligent_color_snap(self, image_array, color_palette):
        """Apply intelligent color snapping to the upscaled image"""
        try:
            print("Applying intelligent color snapping...")

            channels = image_array.shape[2] if len(image_array.shape) == 3 else 1
            result = image_array.copy()

            if len(image_array.shape) == 3:
                # Process in blocks to avoid memory issues
                height, width = image_array.shape[:2]
                block_size = 100  # Process 100x100 blocks

                for y in range(0, height, block_size):
                    for x in range(0, width, block_size):
                        # Get block boundaries
                        y_end = min(y + block_size, height)
                        x_end = min(x + block_size, width)

                        # Extract block
                        block = image_array[y:y_end, x:x_end, :min(3, channels)]
                        original_block_shape = block.shape

                        # Reshape for processing
                        block_pixels = block.reshape(-1, min(3, channels))

                        # Skip transparent pixels if alpha channel
                        if channels == 4:
                            alpha_block = image_array[y:y_end, x:x_end, 3].reshape(-1)
                            valid_mask = alpha_block > 127
                        else:
                            valid_mask = np.ones(len(block_pixels), dtype=bool)

                        valid_pixels = block_pixels[valid_mask]

                        if len(valid_pixels) > 0:
                            # Calculate distances to palette colors
                            distances = np.linalg.norm(
                                valid_pixels[:, np.newaxis, :] - color_palette[np.newaxis, :, :],
                                axis=2
                            )

                            # Find closest colors
                            closest_indices = np.argmin(distances, axis=1)
                            min_distances = np.min(distances, axis=1)

                            # Only snap pixels that are close to a palette color
                            snap_threshold = 40  # More conservative threshold
                            close_enough = min_distances < snap_threshold

                            # Apply snapping
                            valid_pixels[close_enough] = color_palette[closest_indices[close_enough]]

                            # Put pixels back
                            block_pixels[valid_mask] = valid_pixels
                            result[y:y_end, x:x_end, :min(3, channels)] = block_pixels.reshape(original_block_shape)

            return result

        except Exception as e:
            print(f"Intelligent color snapping error: {e}")
            return image_array

    def fast_color_quantization(self, image_array, channels):
        """Quantize colors to eliminate gradients - FAST vectorized approach"""
        try:
            # Aggressive color quantization - reduces color palette dramatically
            quantization_levels = 8  # Very few colors for flat logos

            for c in range(min(3, channels)):  # Skip alpha
                channel = image_array[:, :, c]
                # Quantize to specific levels
                quantized = np.round(channel / (255.0 / quantization_levels)) * (255.0 / quantization_levels)
                image_array[:, :, c] = quantized

            return image_array

        except Exception as e:
            print(f"Color quantization error: {e}")
            return image_array

    def ultra_sharp_edges(self, image_array, scale_factor):
        """Create ultra-sharp edges using vectorized operations"""
        try:
            if len(image_array.shape) == 3:
                channels = image_array.shape[2]

                for c in range(min(3, channels)):  # Skip alpha
                    channel = image_array[:, :, c]

                    # Detect edges using Sobel
                    edges = cv2.Sobel(channel.astype(np.uint8), cv2.CV_64F, 1, 1, ksize=3)
                    edge_mask = np.abs(edges) > 10

                    # Apply unsharp masking for extreme sharpening
                    blurred = cv2.GaussianBlur(channel, (3, 3), 0.5)
                    sharpened = channel + 3.0 * (channel - blurred)  # Very aggressive

                    # Clip values
                    sharpened = np.clip(sharpened, 0, 255)

                    # Apply extra sharpening only at edges
                    channel[edge_mask] = sharpened[edge_mask]

                    image_array[:, :, c] = channel

            return image_array

        except Exception as e:
            print(f"Ultra sharp edges error: {e}")
            return image_array

    def snap_to_dominant_colors(self, image_array, channels):
        """FAST dominant color snapping using simple clustering"""
        try:
            # Use simple color snapping instead of k-means for speed
            return self.simple_color_snap(image_array, channels)

        except Exception as e:
            print(f"Dominant color snapping error: {e}")
            return image_array

    def simple_color_snap(self, image_array, channels):
        """AGGRESSIVE color snapping for razor-sharp flat logos"""
        try:
            # VERY aggressive color snapping - only allows specific values
            for c in range(min(3, channels)):
                channel = image_array[:, :, c]

                # Snap to only these specific color values (very limited palette)
                snap_values = [0, 32, 64, 96, 128, 160, 192, 224, 255]

                # For each pixel, find closest snap value
                for snap_val in snap_values:
                    if snap_val == 0:
                        mask = channel <= 16
                    elif snap_val == 255:
                        mask = channel >= 240
                    else:
                        tolerance = 16
                        mask = (channel >= snap_val - tolerance) & (channel <= snap_val + tolerance)

                    channel[mask] = snap_val

                image_array[:, :, c] = channel

            return image_array
        except:
            return image_array

    def sharpen_grayscale_fast(self, image_array, scale_factor):
        """Fast grayscale sharpening"""
        try:
            # Simple but effective grayscale sharpening
            blurred = cv2.GaussianBlur(image_array, (3, 3), 0.5)
            sharpened = image_array + 2.0 * (image_array - blurred)
            return np.clip(sharpened, 0, 255)
        except:
            return image_array

