/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/**
 * Barikoi Service - Core service for Barikoi API interactions
 * 
 * This service provides methods to interact with the Barikoi API
 * for address autocomplete, geocoding, reverse geocoding, and routing.
 */
export const barikoiService = {
    dependencies: ["notification"],
    
    start(env, { notification }) {
        let configCache = null;
        
        /**
         * Get Barikoi configuration from server
         * @param {boolean} refresh - Force refresh cache
         * @returns {Promise<Object>} Configuration object
         */
        async function getConfig(refresh = false) {
            if (refresh || !configCache) {
                try {
                    const response = await fetch('/barikoi/config');
                    configCache = await response.json();
                } catch (error) {
                    console.error('Failed to fetch Barikoi config:', error);
                    configCache = { enabled: false, has_api_key: false };
                }
            }
            return configCache;
        }
        
        /**
         * Check if Barikoi is enabled and configured
         * @returns {Promise<boolean>}
         */
        async function isEnabled() {
            const config = await getConfig();
            return config.enabled && config.has_api_key;
        }
        
        /**
         * Check if Barikoi is the default provider
         * @returns {Promise<boolean>}
         */
        async function isDefaultProvider() {
            const config = await getConfig();
            return config.default_provider;
        }
        
        /**
         * Autocomplete address search
         * @param {string} query - Search query
         * @param {string} [city] - Optional city filter
         * @returns {Promise<Object>} Autocomplete results
         */
        async function autocomplete(query, city = null) {
            if (!await isEnabled()) {
                return { places: [], status: 400 };
            }
            
            try {
                const params = new URLSearchParams({ q: query });
                if (city) {
                    params.append('city', city);
                }
                
                const response = await fetch(`/barikoi/autocomplete?${params.toString()}`);
                return await response.json();
            } catch (error) {
                console.error('Barikoi autocomplete error:', error);
                return { places: [], status: 500, error: error.message };
            }
        }
        
        /**
         * Get place details by ID
         * @param {string} placeId - Barikoi place ID
         * @returns {Promise<Object>} Place details
         */
        async function getPlaceDetails(placeId) {
            if (!await isEnabled()) {
                return { status: 400, error: 'Barikoi not enabled' };
            }
            
            try {
                const response = await fetch(`/barikoi/place/details?id=${encodeURIComponent(placeId)}`);
                return await response.json();
            } catch (error) {
                console.error('Barikoi place details error:', error);
                return { status: 500, error: error.message };
            }
        }
        
        /**
         * Reverse geocode coordinates to address
         * @param {number} latitude - Latitude coordinate
         * @param {number} longitude - Longitude coordinate
         * @param {Object} [options] - Additional options
         * @returns {Promise<Object>} Reverse geocoding result
         */
        async function reverseGeocode(latitude, longitude, options = {}) {
            if (!await isEnabled()) {
                return { status: 400, error: 'Barikoi not enabled' };
            }
            
            try {
                const params = new URLSearchParams({
                    latitude: latitude.toString(),
                    longitude: longitude.toString(),
                });
                
                // Add optional parameters
                const optionalParams = [
                    'district', 'post_code', 'country', 'sub_district',
                    'union', 'pauroshova', 'location_type', 'division',
                    'address', 'area', 'bangla'
                ];
                
                for (const param of optionalParams) {
                    if (options[param] !== undefined) {
                        params.append(param, options[param].toString());
                    }
                }
                
                const response = await fetch(`/barikoi/reverse_geocode?${params.toString()}`);
                return await response.json();
            } catch (error) {
                console.error('Barikoi reverse geocode error:', error);
                return { status: 500, error: error.message };
            }
        }
        
        /**
         * Geocode address to coordinates
         * @param {string} address - Address to geocode
         * @param {string} [city] - Optional city filter
         * @returns {Promise<Object>} Geocoding result
         */
        async function geocode(address, city = null) {
            if (!await isEnabled()) {
                return { status: 400, error: 'Barikoi not enabled' };
            }
            
            try {
                const params = new URLSearchParams({ q: address });
                if (city) {
                    params.append('city', city);
                }
                
                const response = await fetch(`/barikoi/geocode?${params.toString()}`);
                return await response.json();
            } catch (error) {
                console.error('Barikoi geocode error:', error);
                return { status: 500, error: error.message };
            }
        }
        
        /**
         * Get route between coordinates
         * @param {string} coordinates - Semicolon-separated coordinates (lon,lat;lon,lat)
         * @param {string} [geometries='polyline'] - Geometry format
         * @returns {Promise<Object>} Route information
         */
        async function getRoute(coordinates, geometries = 'polyline') {
            if (!await isEnabled()) {
                return { status: 400, error: 'Barikoi not enabled' };
            }
            
            try {
                const params = new URLSearchParams({
                    coordinates: coordinates,
                    geometries: geometries
                });
                
                const response = await fetch(`/barikoi/route?${params.toString()}`);
                return await response.json();
            } catch (error) {
                console.error('Barikoi route error:', error);
                return { status: 500, error: error.message };
            }
        }
        
        /**
         * Find nearby places
         * @param {number} latitude - Center latitude
         * @param {number} longitude - Center longitude
         * @param {Object} [options] - Additional options
         * @returns {Promise<Object>} Nearby places
         */
        async function nearby(latitude, longitude, options = {}) {
            if (!await isEnabled()) {
                return { status: 400, error: 'Barikoi not enabled' };
            }
            
            try {
                const params = new URLSearchParams({
                    latitude: latitude.toString(),
                    longitude: longitude.toString(),
                    radius: (options.radius || 1000).toString(),
                    limit: (options.limit || 10).toString(),
                });
                
                if (options.place_type) {
                    params.append('place_type', options.place_type);
                }
                
                const response = await fetch(`/barikoi/nearby?${params.toString()}`);
                return await response.json();
            } catch (error) {
                console.error('Barikoi nearby error:', error);
                return { status: 500, error: error.message };
            }
        }
        
        /**
         * Parse Barikoi address data into partner fields format
         * @param {Object} data - Barikoi place data
         * @returns {Object} Mapped fields for res.partner
         */
        function parseAddressComponents(data) {
            const result = {};
            
            if (data.address) {
                result.street = data.address;
            }
            if (data.area) {
                result.street2 = data.area;
            }
            if (data.city) {
                result.city = data.city;
            }
            if (data.post_code) {
                result.zip = data.post_code;
            }
            if (data.latitude) {
                result.partner_latitude = parseFloat(data.latitude);
            }
            if (data.longitude) {
                result.partner_longitude = parseFloat(data.longitude);
            }
            
            // Bangladesh-specific fields
            if (data.division) {
                result.barikoi_division = data.division;
            }
            if (data.district) {
                result.barikoi_district = data.district;
            }
            if (data.sub_district) {
                result.barikoi_upazila = data.sub_district;
            }
            if (data.union) {
                result.barikoi_union = data.union;
            }
            
            return result;
        }
        
        return {
            getConfig,
            isEnabled,
            isDefaultProvider,
            autocomplete,
            getPlaceDetails,
            reverseGeocode,
            geocode,
            getRoute,
            nearby,
            parseAddressComponents,
        };
    },
};

registry.category("services").add("barikoi", barikoiService);