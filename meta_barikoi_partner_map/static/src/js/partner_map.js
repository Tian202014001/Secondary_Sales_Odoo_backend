/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";

// bkoi-gl will be loaded dynamically
/* global bkoi */

/**
 * Barikoi Partner Map Widget
 * Displays an interactive map showing partner location
 * Uses Barikoi GL (Mapbox GL based) library
 */
export class BarikoiPartnerMap extends Component {
    static template = "meta_barikoi_partner_map.BarikoiPartnerMap";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            mapLoaded: false,
            error: null,
        });
        
        this.mapRef = useRef("map");
        this.map = null;
        this.marker = null;
        this.orm = useService("orm");
        
        onMounted(() => {
            this.initMap();
        });
        
        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
            }
        });
    }

    get latitude() {
        return this.props.record.data.partner_latitude || 0;
    }

    get longitude() {
        return this.props.record.data.partner_longitude || 0;
    }

    get partnerName() {
        return this.props.record.data.display_name || "Partner";
    }

    get hasCoordinates() {
        return this.latitude && this.longitude && 
               this.latitude !== 0 && this.longitude !== 0;
    }

    async initMap() {
        try {
            // Check if map container exists
            if (!this.mapRef.el) {
                this.state.error = "Map container not found";
                return;
            }

            // Ensure container has dimensions
            const container = this.mapRef.el;
            if (container.offsetHeight === 0) {
                container.style.height = '300px';
                container.style.minHeight = '300px';
            }

            // Get API key from settings
            const apiKey = await this.getApiKey();
            if (!apiKey) {
                this.state.error = "Barikoi API key not configured";
                return;
            }

            // Load Barikoi GL library dynamically
            await this.loadBarikoiGL();

            // Check if bkoi is available
            if (typeof bkoi === 'undefined' || !bkoi.Map) {
                this.state.error = "Barikoi GL library failed to load";
                return;
            }

            // Set API key
            bkoi.accessToken = apiKey;

            // Initialize map
            const defaultLng = this.hasCoordinates ? this.longitude : 90.4125;
            const defaultLat = this.hasCoordinates ? this.latitude : 23.8103;
            
            this.map = new bkoi.Map({
                container: container,
                center: [defaultLng, defaultLat], // Mapbox GL uses [lng, lat]
                zoom: this.hasCoordinates ? 15 : 7,
                style: `https://map.barikoi.com/styles/osm-liberty/style.json?key=${apiKey}`,
            });

            // Add navigation controls
            this.map.addControl(new bkoi.NavigationControl(), 'top-right');

            // Wait for map to load
            this.map.on('load', () => {
                this.state.mapLoaded = true;
                
                // Add marker if coordinates exist
                if (this.hasCoordinates) {
                    this.addMarker(this.longitude, this.latitude);
                }
            });

            // Add click handler to set location
            this.map.on('click', async (e) => {
                const { lng, lat } = e.lngLat;
                await this.updateCoordinates(lat, lng);
            });

            // Handle errors
            this.map.on('error', (e) => {
                console.error("Map error:", e);
                this.state.error = "Map loading error";
            });
            
        } catch (error) {
            console.error("Barikoi Map initialization error:", error);
            this.state.error = "Failed to load map: " + error.message;
        }
    }

    async loadBarikoiGL() {
        // Load Barikoi GL JS from npm CDN (jsdelivr UMD build for global bkoi variable)
        // Load CSS files separately to avoid ORB issues with @import in bkoi-gl.css
        const jsUrl = "https://cdn.jsdelivr.net/npm/bkoi-gl@3.3.0/dist/umd/bkoi-gl.js";
        const cssUrls = [
            "https://cdn.jsdelivr.net/npm/maplibre-gl@5.13.0/dist/maplibre-gl.css",
            // Note: maplibre-gl-draw is optional, only needed for drawing features
            // "https://cdn.jsdelivr.net/npm/@maplibre/maplibre-gl-draw@1.6.9/dist/maplibre-gl-draw.css",
        ];
        
        try {
            await Promise.all([
                loadJS(jsUrl),
                ...cssUrls.map(url => loadCSS(url)),
            ]);
        } catch (e) {
            console.error("Failed to load Barikoi GL:", e);
            throw new Error("Failed to load Barikoi GL library");
        }
    }

    addMarker(lng, lat) {
        if (!this.map) return;

        // Remove existing marker if any
        if (this.marker) {
            this.marker.remove();
        }

        // Create a draggable marker
        this.marker = new bkoi.Marker({ draggable: true })
            .setLngLat([lng, lat])
            .setPopup(new bkoi.Popup().setHTML(`<b>${this.partnerName}</b>`))
            .addTo(this.map);

        // Handle marker drag
        this.marker.on('dragend', async () => {
            const position = this.marker.getLngLat();
            await this.updateCoordinates(position.lat, position.lng);
        });

        // Center map on marker
        this.map.flyTo({
            center: [lng, lat],
            zoom: 15,
        });
    }

    async updateCoordinates(lat, lng) {
        // Update the record
        await this.props.record.update({
            partner_latitude: lat,
            partner_longitude: lng,
        });
        
        // Update or add marker
        this.addMarker(lng, lat);
    }

    async getApiKey() {
        // Get API key from Odoo config
        try {
            const result = await this.orm.searchRead(
                "ir.config_parameter",
                [["key", "=", "barikoi.api_key"]],
                ["value"],
                { limit: 1 }
            );
            return result && result.length > 0 ? result[0].value : null;
        } catch (e) {
            console.error("Error getting API key:", e);
            return null;
        }
    }
}

// Register the widget
registry.category("fields").add("barikoi_partner_map", {
    component: BarikoiPartnerMap,
    displayName: _t("Barikoi Partner Map"),
    supportedTypes: ["float"],
    extractProps: () => ({}),
});