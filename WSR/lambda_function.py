#!/usr/bin/env python3
"""
AWS Lambda handler for Logo Vectorizer Tool
Alternative handler that doesn't require awsgi
"""

import json
import base64
from io import BytesIO

# Import Flask app
from app import app

def lambda_handler(event, context):
    """
    AWS Lambda handler function for API Gateway

    Args:
        event: API Gateway event object
        context: Lambda context object

    Returns:
        API Gateway formatted response
    """

    try:
        # Get HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        headers = event.get('headers', {})
        query_params = event.get('queryStringParameters', {})
        body = event.get('body', '')
        is_base64 = event.get('isBase64Encoded', False)

        # Decode base64 body if needed
        if is_base64 and body:
            body = base64.b64decode(body)

        # Create Flask test client
        with app.test_client() as client:
            # Handle different HTTP methods
            if http_method == 'GET':
                response = client.get(path, query_string=query_params, headers=headers)
            elif http_method == 'POST':
                # Check if it's multipart/form-data or JSON
                content_type = headers.get('content-type', headers.get('Content-Type', ''))

                if 'multipart/form-data' in content_type:
                    # For multipart, we need to pass the raw body
                    response = client.post(
                        path,
                        data=body,
                        headers=headers,
                        content_type=content_type
                    )
                else:
                    # For JSON or other content types
                    response = client.post(
                        path,
                        data=body,
                        headers=headers,
                        content_type=content_type
                    )
            elif http_method == 'OPTIONS':
                # Handle CORS preflight
                return {
                    'statusCode': 200,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    },
                    'body': ''
                }
            else:
                response = client.open(
                    path,
                    method=http_method,
                    data=body,
                    headers=headers
                )

            # Get response data
            response_data = response.get_data()

            # Determine if response should be base64 encoded
            response_headers = dict(response.headers)
            content_type = response_headers.get('Content-Type', '')

            # Check if it's binary content
            is_binary = False
            binary_types = ['image/', 'application/octet-stream', 'application/pdf']
            for binary_type in binary_types:
                if binary_type in content_type:
                    is_binary = True
                    break

            # Add CORS headers
            response_headers.update({
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            })

            # Format response
            if is_binary:
                return {
                    'statusCode': response.status_code,
                    'headers': response_headers,
                    'body': base64.b64encode(response_data).decode('utf-8'),
                    'isBase64Encoded': True
                }
            else:
                return {
                    'statusCode': response.status_code,
                    'headers': response_headers,
                    'body': response_data.decode('utf-8') if isinstance(response_data, bytes) else response_data,
                    'isBase64Encoded': False
                }

    except Exception as e:
        # Error handling
        import traceback
        error_trace = traceback.format_exc()

        print(f"Lambda Error: {str(e)}")
        print(f"Trace: {error_trace}")

        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            },
            'body': json.dumps({
                'success': False,
                'error': f'Server error: {str(e)}'
            }),
            'isBase64Encoded': False
        }
