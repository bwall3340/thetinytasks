"""
Tests for WSR Flask app routes.

Run with:
    cd WSR
    pytest tests/ -v
"""

import io
import json
import pytest
from conftest import make_png_bytes, make_png_with_white_bg


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

class TestPageRoutes:
    def test_root_returns_200(self, client):
        response = client.get('/')
        assert response.status_code == 200

    def test_interactive_returns_200(self, client):
        response = client.get('/interactive')
        assert response.status_code == 200

    def test_test_page_returns_200(self, client):
        response = client.get('/test')
        assert response.status_code == 200

    def test_unknown_route_returns_404_page(self, client):
        # The app renders interactive.html on 404 (not a JSON error)
        response = client.get('/nonexistent-path')
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /process_interactive
# ---------------------------------------------------------------------------

class TestProcessInteractive:
    ENDPOINT = '/process_interactive'

    def _post(self, client, image_bytes=None, epsilon='0.02', filename='test.png'):
        data = {'epsilon': epsilon}
        if image_bytes is not None:
            data['image'] = (io.BytesIO(image_bytes), filename)
        return client.post(
            self.ENDPOINT,
            data=data,
            content_type='multipart/form-data'
        )

    def test_no_image_returns_error(self, client):
        response = self._post(client, image_bytes=None)
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'No image file provided' in body['error']

    def test_empty_filename_returns_error(self, client):
        data = {'epsilon': '0.02', 'image': (io.BytesIO(b''), '')}
        response = client.post(
            self.ENDPOINT,
            data=data,
            content_type='multipart/form-data'
        )
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'No file selected' in body['error']

    def test_epsilon_too_low_returns_error(self, client, small_png):
        response = self._post(client, small_png, epsilon='0.00001')
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'Epsilon' in body['error']

    def test_epsilon_too_high_returns_error(self, client, small_png):
        response = self._post(client, small_png, epsilon='0.5')
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'Epsilon' in body['error']

    def test_valid_image_returns_success(self, client, logo_png):
        response = self._post(client, logo_png, epsilon='0.02')
        body = json.loads(response.data)
        assert body['success'] is True
        assert 'svg_content' in body
        assert 'no_bg_image' in body
        assert 'binary_image' in body
        assert 'contour_count' in body
        assert 'processing_time' in body

    def test_svg_content_is_valid_xml(self, client, logo_png):
        response = self._post(client, logo_png, epsilon='0.02')
        body = json.loads(response.data)
        assert body['success'] is True
        svg = body['svg_content']
        assert svg.strip().startswith('<?xml') or '<svg' in svg

    def test_original_size_format(self, client, logo_png):
        response = self._post(client, logo_png, epsilon='0.02')
        body = json.loads(response.data)
        assert body['success'] is True
        # Should be "WxH" format
        size = body['original_size']
        parts = size.split('x')
        assert len(parts) == 2
        assert parts[0].isdigit() and parts[1].isdigit()

    def test_epsilon_boundary_min_valid(self, client, logo_png):
        # 0.0001 is the minimum allowed
        response = self._post(client, logo_png, epsilon='0.0001')
        body = json.loads(response.data)
        assert body['success'] is True

    def test_epsilon_boundary_max_valid(self, client, logo_png):
        # 0.1 is the maximum allowed
        response = self._post(client, logo_png, epsilon='0.1')
        body = json.loads(response.data)
        assert body['success'] is True


# ---------------------------------------------------------------------------
# /process_test
# ---------------------------------------------------------------------------

class TestProcessTest:
    ENDPOINT = '/process_test'

    def _post(self, client, image_bytes=None, epsilon='0.02',
              smoothing_level='high', filename='test.png'):
        data = {'epsilon': epsilon, 'smoothing_level': smoothing_level}
        if image_bytes is not None:
            data['image'] = (io.BytesIO(image_bytes), filename)
        return client.post(
            self.ENDPOINT,
            data=data,
            content_type='multipart/form-data'
        )

    def test_no_image_returns_error(self, client):
        response = self._post(client)
        body = json.loads(response.data)
        assert body['success'] is False

    def test_valid_image_returns_success(self, client, logo_png):
        response = self._post(client, logo_png)
        body = json.loads(response.data)
        assert body['success'] is True
        assert body.get('test_mode') is True

    def test_smoothing_level_reflected_in_response(self, client, logo_png):
        response = self._post(client, logo_png, smoothing_level='medium')
        body = json.loads(response.data)
        assert body['success'] is True
        assert body['smoothing_level'] == 'medium'

    def test_epsilon_out_of_range_returns_error(self, client, logo_png):
        response = self._post(client, logo_png, epsilon='1.0')
        body = json.loads(response.data)
        assert body['success'] is False


# ---------------------------------------------------------------------------
# /process_upscale
# ---------------------------------------------------------------------------

class TestProcessUpscale:
    ENDPOINT = '/process_upscale'

    def _post(self, client, image_bytes=None, scale_factor='2',
              method='smart_edge', preserve_contrast='true',
              logo_type='styled', filename='test.png'):
        data = {
            'scale_factor': scale_factor,
            'method': method,
            'preserve_contrast': preserve_contrast,
            'logo_type': logo_type,
        }
        if image_bytes is not None:
            data['image'] = (io.BytesIO(image_bytes), filename)
        return client.post(
            self.ENDPOINT,
            data=data,
            content_type='multipart/form-data'
        )

    def test_no_image_returns_error(self, client):
        response = self._post(client)
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'No image file provided' in body['error']

    def test_scale_factor_too_large_returns_error(self, client, small_png):
        response = self._post(client, small_png, scale_factor='9')
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'Scale factor' in body['error']

    def test_scale_factor_zero_returns_error(self, client, small_png):
        response = self._post(client, small_png, scale_factor='0')
        body = json.loads(response.data)
        assert body['success'] is False

    def test_invalid_method_returns_error(self, client, small_png):
        response = self._post(client, small_png, method='invalid_method')
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'Method' in body['error']

    def test_invalid_logo_type_returns_error(self, client, small_png):
        response = self._post(client, small_png, logo_type='cartoon')
        body = json.loads(response.data)
        assert body['success'] is False
        assert 'Logo type' in body['error']

    def test_valid_upscale_2x(self, client, small_png):
        response = self._post(client, small_png, scale_factor='2')
        body = json.loads(response.data)
        assert body['success'] is True
        assert 'upscaled_image' in body
        assert 'original_image' in body
        assert body['scale_factor'] == 2

    def test_upscaled_size_doubles(self, client):
        # 50x50 image upscaled 2x should report 100x100
        png = make_png_bytes(width=50, height=50)
        response = self._post(client, png, scale_factor='2')
        body = json.loads(response.data)
        assert body['success'] is True
        upscaled = body['upscaled_size']
        w, h = map(int, upscaled.split('x'))
        assert w == 100 and h == 100

    def test_all_valid_methods(self, client, small_png):
        for method in ['smart_edge', 'super_resolution', 'pixel_art', 'hybrid']:
            response = self._post(client, small_png, method=method)
            body = json.loads(response.data)
            assert body['success'] is True, f"Method '{method}' failed: {body.get('error')}"

    def test_all_valid_logo_types(self, client, small_png):
        for logo_type in ['flat_color', 'styled']:
            response = self._post(client, small_png, logo_type=logo_type)
            body = json.loads(response.data)
            assert body['success'] is True, f"Logo type '{logo_type}' failed"


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------

class TestCORSHeaders:
    def test_cors_header_on_get(self, client):
        response = client.get('/')
        assert response.headers.get('Access-Control-Allow-Origin') == '*'

    def test_cors_header_on_post(self, client, logo_png):
        data = {
            'epsilon': '0.02',
            'image': (io.BytesIO(logo_png), 'test.png'),
        }
        response = client.post(
            '/process_interactive',
            data=data,
            content_type='multipart/form-data'
        )
        assert response.headers.get('Access-Control-Allow-Origin') == '*'
