/**
 * API Configuration for WSR Background Remover
 *
 * IMPORTANT: Update this file with your actual API Gateway URL after deployment
 */

const WSR_CONFIG = {
    // Replace this with your API Gateway URL after deployment
    // Format: https://YOUR-API-ID.execute-api.REGION.amazonaws.com/STAGE
    API_GATEWAY_URL: 'https://gjaywdda7i.execute-api.us-east-1.amazonaws.com/default/tiny-tasks-api',

    // Alternatively, you can set different URLs for different environments
    // Uncomment and customize as needed:
    /*
    getApiUrl: function() {
        const hostname = window.location.hostname;

        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            // Local development
            return 'http://localhost:5000';
        } else if (hostname.includes('cloudfront')) {
            // CloudFront distribution
            return 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod';
        } else if (hostname.includes('s3')) {
            // S3 website hosting
            return 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod';
        } else {
            // Default production URL
            return 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod';
        }
    }
    */
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WSR_CONFIG;
}
