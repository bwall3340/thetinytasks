/**
 * API Configuration for WSR Background Remover
 *
 * IMPORTANT: Update this file with your actual API Gateway URL after deployment
 */

const WSR_CONFIG = {
    getApiUrl: function() {
        // When opened as a local file, point to local dev server
        if (window.location.protocol === 'file:') {
            return 'http://localhost:5000';
        }
        // When served over HTTP/HTTPS (Railway, etc.) use the same origin
        return window.location.origin;
    },

    // Convenience getter so existing code using API_GATEWAY_URL still works
    get API_GATEWAY_URL() {
        return this.getApiUrl();
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WSR_CONFIG;
}
