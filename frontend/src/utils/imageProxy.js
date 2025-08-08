/**
 * Utility to proxy Bluesky CDN images through our server to avoid CORS issues
 */

/**
 * Convert a Bluesky CDN URL to use our image proxy
 * @param {string} originalUrl - The original Bluesky CDN URL
 * @returns {string} - Proxied URL through our server
 */
export function proxyImageUrl(originalUrl) {
  if (!originalUrl) return originalUrl;
  
  // Only proxy Bluesky CDN URLs
  if (!originalUrl.includes('bsky.app') && !originalUrl.includes('cdn.bsky.app')) {
    return originalUrl;
  }
  
  // Return proxied URL
  return `/api/v1/image-proxy?url=${encodeURIComponent(originalUrl)}`;
}

/**
 * Get a safe image URL that handles errors gracefully
 * @param {string} originalUrl - The original image URL
 * @param {string} fallbackUrl - Fallback URL if proxy fails
 * @returns {string} - Safe image URL
 */
export function getSafeImageUrl(originalUrl, fallbackUrl = '/assets/default-avatar.png') {
  if (!originalUrl) return fallbackUrl;
  return proxyImageUrl(originalUrl);
}