#!/usr/bin/env python3
"""
Flask web application for Logo Vectorizer Tool
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import cv2
import numpy as np
from PIL import Image
from skimage import morphology
import io
import base64
import time
import traceback
from vectorizer_engine import ImprovedVectorizer
from detailed_vectorizer import DetailedVectorizer
from extreme_vectorizer import ExtremeDetailVectorizer
from test_vectorizer import AdvancedTestVectorizer
from logo_upscaler import LogoUpscaler


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Directory containing the static home-page files (copied in by Docker)
SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site')

# ── Market commentary module ──────────────────────────────────────────────────
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///market.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')

from market.models import db
from market.admin import admin_bp, init_oauth
from market.routes import market_bp

db.init_app(app)
init_oauth(app)
app.register_blueprint(admin_bp)
app.register_blueprint(market_bp)

with app.app_context():
    db.create_all()

# Start background scrape scheduler (only when running under gunicorn or directly)
if not app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    try:
        from market.scheduler import start_scheduler
        start_scheduler(app)
    except Exception as _sched_err:
        app.logger.warning('Scheduler not started: %s', _sched_err)
# ─────────────────────────────────────────────────────────────────────────────

# Manual CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/', methods=['OPTIONS'])
def handle_options(path=None):
    response = jsonify({'status': 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


class LogoVectorizerAPI:
    def __init__(self):
        pass

    def remove_white_background(self, image_data, white_threshold=245):
        """Remove only white background pixels, preserving light yellow and other colors"""
        try:
            # Load image from bytes
            image = Image.open(io.BytesIO(image_data))
            image_array = np.array(image)

            # Convert to RGBA if not already
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                # Add alpha channel
                alpha = np.ones((image_array.shape[0], image_array.shape[1], 1), dtype=np.uint8) * 255
                image_array = np.concatenate([image_array, alpha], axis=2)
            elif len(image_array.shape) == 2:
                # Grayscale to RGBA
                rgb = np.stack([image_array, image_array, image_array], axis=2)
                alpha = np.ones((image_array.shape[0], image_array.shape[1], 1), dtype=np.uint8) * 255
                image_array = np.concatenate([rgb, alpha], axis=2)

            # Create mask for white pixels only
            # Check if all RGB channels are above white_threshold
            white_mask = (
                (image_array[:, :, 0] >= white_threshold) &
                (image_array[:, :, 1] >= white_threshold) &
                (image_array[:, :, 2] >= white_threshold)
            )

            # Set alpha to 0 for white pixels only
            image_array[white_mask, 3] = 0

            return image_array

        except Exception as e:
            raise Exception(f"Error removing white background: {e}")

    def preprocess_for_vectorization(self, image_array, binary_threshold=128):
        """Preprocess image for vectorization with hard borders"""
        # Convert to grayscale if it's RGBA
        if len(image_array.shape) == 3 and image_array.shape[2] == 4:
            # Use alpha channel to create mask
            alpha = image_array[:, :, 3]
            # Convert RGB to grayscale
            gray = cv2.cvtColor(image_array[:, :, :3], cv2.COLOR_RGB2GRAY)
            # Apply alpha mask - set transparent areas to white
            gray = np.where(alpha > 0, gray, 255)
        else:
            gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)

        # NO Gaussian blur - preserve hard edges!
        # Direct binary threshold for crisp edges
        binary = gray < binary_threshold

        # Minimal cleanup - only remove very small artifacts
        cleaned = morphology.remove_small_objects(binary, min_size=10)
        cleaned = morphology.remove_small_holes(cleaned, area_threshold=10)

        return cleaned.astype(np.uint8) * 255

    def extract_contours(self, binary_image):
        """Extract contours from binary image"""
        contours, _ = cv2.findContours(
            binary_image,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        return contours

    def simplify_contours(self, contours, epsilon_factor=0.02):
        """Simplify contours to reduce complexity"""
        simplified = []
        for contour in contours:
            epsilon = epsilon_factor * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            if len(approx) >= 3:  # At least a triangle
                simplified.append(approx)
        return simplified

    def contours_to_svg(self, contours, image_shape):
        """Convert contours to SVG format"""
        height, width = image_shape[:2]

        svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg">
'''

        for i, contour in enumerate(contours):
            if len(contour) < 3:
                continue

            path_data = f"M {contour[0][0][0]} {contour[0][0][1]}"

            for point in contour[1:]:
                x, y = point[0][0], point[0][1]
                path_data += f" L {x} {y}"

            path_data += " Z"

            svg_content += f'  <path d="{path_data}" fill="black" stroke="none"/>\n'

        svg_content += '</svg>'

        return svg_content

    def image_to_base64(self, image_array):
        """Convert numpy array to base64 string"""
        if len(image_array.shape) == 3:
            image = Image.fromarray(image_array)
        else:
            image = Image.fromarray(image_array, mode='L')

        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode()



# Initialize the APIs
vectorizer_api = LogoVectorizerAPI()
improved_vectorizer = ImprovedVectorizer()
detailed_vectorizer = DetailedVectorizer()
extreme_vectorizer = ExtremeDetailVectorizer()
test_vectorizer = AdvancedTestVectorizer()
logo_upscaler = LogoUpscaler()


@app.route('/')
def index():
    """Serve the home page (title screen + tool dashboard)"""
    return send_from_directory(SITE_DIR, 'index.html')


@app.route('/styles.css')
def home_styles():
    return send_from_directory(SITE_DIR, 'styles.css')


@app.route('/script.js')
def home_script():
    return send_from_directory(SITE_DIR, 'script.js')


@app.route('/background-remover.html')
def background_remover():
    return send_from_directory(SITE_DIR, 'background-remover.html')


@app.route('/Sankey/<path:filename>')
def sankey_files(filename):
    return send_from_directory(os.path.join(SITE_DIR, 'Sankey'), filename)


@app.route('/WhiteBackgroundRemover/<path:filename>')
def white_bg_remover_files(filename):
    return send_from_directory(os.path.join(SITE_DIR, 'WhiteBackgroundRemover'), filename)


@app.route('/interactive')
def interactive():
    """Serve the vectorizer tool"""
    return render_template('interactive.html')




@app.route('/test')
def test_page():
    """Serve the test interface"""
    return render_template('test.html')




@app.route('/process_interactive', methods=['POST'])
def process_interactive():
    """Process image that was edited interactively and return vectorized results"""
    try:
        # Check if image file is present
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'})

        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        # Get epsilon factor
        epsilon = float(request.form.get('epsilon', 0.02))

        # Validate epsilon range (allow ultra-fine detail)
        if epsilon < 0.0001 or epsilon > 0.1:
            return jsonify({'success': False, 'error': 'Epsilon must be between 0.0001 and 0.1'})

        # Read image data
        image_data = file.read()

        # Validate file size
        if len(image_data) > 10 * 1024 * 1024:  # 10MB
            return jsonify({'success': False, 'error': 'File size must be less than 10MB'})

        # For interactive processing, skip background removal since it's already done
        # Just process for vectorization
        start_time = time.time()

        try:
            # Load the already-edited image
            image = Image.open(io.BytesIO(image_data))
            image_array = np.array(image)

            # Choose vectorization engine based on epsilon (detail level)
            if epsilon <= 0.0001:
                # Use extreme detail vectorizer for pixel-perfect results
                vectorization_result = extreme_vectorizer.vectorize_extreme_detail_logo(image_array, epsilon)
            else:
                # Use detailed vectorization engine for high quality
                vectorization_result = detailed_vectorizer.vectorize_detailed_logo(image_array, epsilon, use_curves=True)

            if not vectorization_result['success']:
                return jsonify(vectorization_result)

            # Convert images to base64 for web display using appropriate vectorizer
            if epsilon <= 0.0001:
                no_bg_b64 = extreme_vectorizer.image_to_base64(image_array)
                binary_b64 = extreme_vectorizer.image_to_base64(vectorization_result['binary_mask'])
            else:
                no_bg_b64 = detailed_vectorizer.image_to_base64(image_array)
                binary_b64 = detailed_vectorizer.image_to_base64(vectorization_result['binary_mask'])

            # Get original image info
            original_size = f"{image.size[0]}x{image.size[1]}"
            processing_time = round(time.time() - start_time, 2)

            result = {
                'success': True,
                'no_bg_image': no_bg_b64,
                'binary_image': binary_b64,
                'svg_content': vectorization_result['svg_content'],
                'contour_count': vectorization_result['contour_count'],
                'original_size': original_size,
                'epsilon_factor': epsilon,
                'processing_time': processing_time
            }

        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"Error processing interactive image: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })


@app.route('/process_test', methods=['POST'])
def process_test():
    """Process image in test mode - duplicate of process_interactive for testing improvements"""
    try:
        # Check if image file is present
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'})

        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        # Get epsilon factor and smoothing level
        epsilon = float(request.form.get('epsilon', 0.02))
        smoothing_level = request.form.get('smoothing_level', 'high')

        # Validate epsilon range (allow ultra-fine detail)
        if epsilon < 0.0001 or epsilon > 0.1:
            return jsonify({'success': False, 'error': 'Epsilon must be between 0.0001 and 0.1'})

        # Read image data
        image_data = file.read()

        # Validate file size
        if len(image_data) > 10 * 1024 * 1024:  # 10MB
            return jsonify({'success': False, 'error': 'File size must be less than 10MB'})

        # For test processing, skip background removal since it's already done
        # Just process for vectorization
        start_time = time.time()

        try:
            # Load the already-edited image
            image = Image.open(io.BytesIO(image_data))
            image_array = np.array(image)

            # Use the advanced test vectorizer with edge smoothing
            vectorization_result = test_vectorizer.vectorize_test_logo(image_array, epsilon, smoothing_level)

            if not vectorization_result['success']:
                return jsonify(vectorization_result)

            # Convert images to base64 for web display
            no_bg_b64 = test_vectorizer.image_to_base64(image_array)
            binary_b64 = test_vectorizer.image_to_base64(vectorization_result['binary_mask'])

            # Get original image info
            original_size = f"{image.size[0]}x{image.size[1]}"
            processing_time = round(time.time() - start_time, 2)

            result = {
                'success': True,
                'no_bg_image': no_bg_b64,
                'binary_image': binary_b64,
                'svg_content': vectorization_result['svg_content'],
                'contour_count': vectorization_result['contour_count'],
                'original_size': original_size,
                'epsilon_factor': epsilon,
                'processing_time': processing_time,
                'test_mode': True,  # Identifier for test mode
                'smoothing_level': smoothing_level,
                'detail_level': vectorization_result.get('detail_level', 'test_advanced')
            }

        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"Error processing test image: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })



@app.route('/process_upscale', methods=['POST'])
def process_upscale():
    """Process image upscaling with edge preservation"""
    try:
        # Check if image file is present
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image file provided'})

        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})

        # Get upscaling parameters
        scale_factor = int(request.form.get('scale_factor', 2))
        method = request.form.get('method', 'smart_edge')
        preserve_contrast = request.form.get('preserve_contrast', 'true').lower() == 'true'
        logo_type = request.form.get('logo_type', 'styled')

        # Validate parameters
        if scale_factor < 1 or scale_factor > 8:
            return jsonify({'success': False, 'error': 'Scale factor must be between 1 and 8'})

        valid_methods = ['smart_edge', 'super_resolution', 'pixel_art', 'hybrid']
        if method not in valid_methods:
            return jsonify({'success': False, 'error': f'Method must be one of: {valid_methods}'})

        valid_logo_types = ['flat_color', 'styled']
        if logo_type not in valid_logo_types:
            return jsonify({'success': False, 'error': f'Logo type must be one of: {valid_logo_types}'})

        # Read image data
        image_data = file.read()

        # Validate file size
        if len(image_data) > 10 * 1024 * 1024:  # 10MB
            return jsonify({'success': False, 'error': 'File size must be less than 10MB'})

        start_time = time.time()

        try:
            # Load the image
            image = Image.open(io.BytesIO(image_data))
            image_array = np.array(image)

            # Upscale the image using the LogoUpscaler
            upscale_result = logo_upscaler.upscale_logo(
                image_array,
                scale_factor=scale_factor,
                method=method,
                preserve_contrast=preserve_contrast,
                logo_type=logo_type
            )

            if not upscale_result['success']:
                return jsonify(upscale_result)

            # Convert images to base64 for web display
            original_b64 = logo_upscaler.image_to_base64(image_array)
            upscaled_b64 = logo_upscaler.image_to_base64(upscale_result['upscaled_image'])

            # Get image info
            original_size = f"{image.size[0]}x{image.size[1]}"
            upscaled_size = f"{upscale_result['upscaled_image'].shape[1]}x{upscale_result['upscaled_image'].shape[0]}"
            processing_time = round(time.time() - start_time, 2)

            result = {
                'success': True,
                'original_image': original_b64,
                'upscaled_image': upscaled_b64,
                'original_size': original_size,
                'upscaled_size': upscaled_size,
                'scale_factor': scale_factor,
                'method': method,
                'preserve_contrast': preserve_contrast,
                'logo_type': logo_type,
                'processing_time': processing_time
            }

        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }

        return jsonify(result)

    except Exception as e:
        app.logger.error(f"Error processing upscale request: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })


@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'error': 'File too large. Maximum size is 16MB.'}), 413


@app.errorhandler(404)
def not_found(e):
    return send_from_directory(SITE_DIR, 'index.html'), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("Starting Logo Vectorizer Web Interface...")
    print(f"Open your browser and go to: http://localhost:{port}")
    app.run(debug=False, host='0.0.0.0', port=port)