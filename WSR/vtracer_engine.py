#!/usr/bin/env python3
"""
VTracer-based multi-color vectorization engine.
Produces filled, multi-layer SVG with cubic bezier curves.
"""

import vtracer


class VtracerEngine:
    def vectorize_color(self, image_bytes, filter_speckle=4, color_precision=6,
                        layer_difference=16, corner_threshold=60):
        try:
            svg_content = vtracer.convert_raw_image_to_svg(
                image_bytes,
                colormode='color',
                hierarchical='stacked',
                mode='spline',
                filter_speckle=int(filter_speckle),
                color_precision=int(color_precision),
                layer_difference=int(layer_difference),
                corner_threshold=int(corner_threshold),
                length_threshold=4.0,
                splice_threshold=45,
                path_precision=8,
            )
            path_count = svg_content.count('<path')
            return {
                'success': True,
                'svg_content': svg_content,
                'path_count': path_count,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
