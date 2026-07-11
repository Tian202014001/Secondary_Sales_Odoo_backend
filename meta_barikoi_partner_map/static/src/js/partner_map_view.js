/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";

// bkoi-gl will be loaded dynamically
/* global bkoi */

/**
 * Barikoi Partner Map View
 * Full map view showing all partners with coordinates
 * Uses Barikoi GL (Mapbox GL based) library
 */
export class BarikoiPartnerMapView extends Component {
    static template = "meta_barikoi_partner_map.PartnerMapView";

    setup() {
        this.state = useState({
            mapLoaded: false,
            error: null,
            partners: [],
            selectedPartner: null,
        });
        
        this.mapRef = useRef("map");
        this.map = null;
        this.markers = [];
        this.orm = useService("orm");
        this.action = useService("action");
        
        // Check if we're zooming to a specific partner
        this.zoomToPartner = this.props && this.props.params && this.props.params.zoom_to_partner;
        this.specificPartner = this.zoomToPartner ? {
            id: this.props.params.partner_id,
            latitude: this.props.params.latitude,
            longitude: this.props.params.longitude,
            name: this.props.params.name,
        } : null;
        
        onMounted(() => {
            this.initMap();
        });
        
        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
            }
        });
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
                container.style.height = '500px';
                container.style.minHeight = '500px';
            }

            // Get API key from settings
            const apiKey = await this.getApiKey();
            if (!apiKey) {
                this.state.error = "Barikoi API key not configured. Please configure it in Settings.";
                return;
            }

            // Load Barikoi GL library dynamically
            await this.loadBarikoiGL();

            // Check if bkoi is available
            if (typeof bkoi === 'undefined' || !bkoi.Map) {
                this.state.error = "Barikoi GL library failed to load. Please refresh the page.";
                return;
            }

            // Set API key
            bkoi.accessToken = apiKey;

            // Determine initial center and zoom
            let initialLng = 90.4125; // Dhaka (lng, lat for Mapbox GL)
            let initialLat = 23.8103;
            let initialZoom = 7;
            
            // If we have a specific partner, center on them
            if (this.zoomToPartner && this.specificPartner) {
                initialLat = this.specificPartner.latitude;
                initialLng = this.specificPartner.longitude;
                initialZoom = 15;
            }

            // Initialize map using Barikoi GL (Mapbox GL style)
            this.map = new bkoi.Map({
                container: container,
                center: [initialLng, initialLat], // Mapbox GL uses [lng, lat]
                zoom: initialZoom,
                style: `https://map.barikoi.com/styles/osm-liberty/style.json?key=${apiKey}`,
            });

            // Add navigation controls
            this.map.addControl(new bkoi.NavigationControl(), 'top-right');

            // Wait for map to load
            this.map.on('load', async () => {
                this.state.mapLoaded = true;
                await this.loadPartners();
            });

            // Handle errors
            this.map.on('error', (e) => {
                console.error("Map error:", e);
                this.state.error = "Map loading error. Please check your API key.";
            });
            
        } catch (error) {
            console.error("Barikoi Map View initialization error:", error);
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

    async loadPartners() {
        try {
            const fields = ['id', 'name', 'display_name', 'partner_latitude', 'partner_longitude', 
                           'street', 'city', 'phone', 'email', 'geocoding_status'];
            
            let partners = [];
            
            // If we have a specific partner, load only that partner
            if (this.zoomToPartner && this.specificPartner && this.specificPartner.id) {
                partners = await this.orm.searchRead(
                    "res.partner",
                    [['id', '=', this.specificPartner.id]],
                    fields,
                    { limit: 1 }
                );
            } else {
                // Otherwise load all partners with coordinates
                const domain = [
                    ['partner_latitude', '!=', false],
                    ['partner_longitude', '!=', false],
                    ['partner_latitude', '!=', 0],
                    ['partner_longitude', '!=', 0],
                ];
                
                partners = await this.orm.searchRead(
                    "res.partner",
                    domain,
                    fields,
                    { limit: 500 }
                );
            }
            
            this.state.partners = partners;
            
            // Add markers for each partner
            this.addPartnerMarkers(partners);
            
            // If zooming to specific partner, center and zoom on that partner
            if (this.zoomToPartner && this.specificPartner) {
                this.map.flyTo({
                    center: [this.specificPartner.longitude, this.specificPartner.latitude],
                    zoom: 16,
                });
            } else if (partners.length > 0) {
                // Fit bounds if there are partners
                const bounds = new bkoi.LngLatBounds();
                partners.forEach(p => {
                    bounds.extend([p.partner_longitude, p.partner_latitude]);
                });
                this.map.fitBounds(bounds, { padding: 50 });
            }
            
        } catch (error) {
            console.error("Error loading partners:", error);
            this.state.error = "Failed to load partners: " + error.message;
        }
    }

    addPartnerMarkers(partners) {
        if (!this.map || !partners.length) return;

        // Add markers as a GeoJSON source
        const geojson = {
            type: 'FeatureCollection',
            features: partners.map(partner => ({
                type: 'Feature',
                geometry: {
                    type: 'Point',
                    coordinates: [partner.partner_longitude, partner.partner_latitude],
                },
                properties: {
                    id: partner.id,
                    name: partner.display_name,
                    street: partner.street || '',
                    city: partner.city || '',
                    phone: partner.phone || '',
                    email: partner.email || '',
                },
            })),
        };

        // Add source
        if (this.map.getSource('partners')) {
            this.map.getSource('partners').setData(geojson);
        } else {
            this.map.addSource('partners', {
                type: 'geojson',
                data: geojson,
            });

            // Add marker layer
            this.map.addLayer({
                id: 'partners-markers',
                type: 'circle',
                source: 'partners',
                paint: {
                    'circle-radius': 8,
                    'circle-color': '#714B67',
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#ffffff',
                },
            });

            // Add label layer
            this.map.addLayer({
                id: 'partners-labels',
                type: 'symbol',
                source: 'partners',
                layout: {
                    'text-field': ['get', 'name'],
                    'text-font': ['Open Sans Regular'],
                    'text-offset': [0, 1.5],
                    'text-anchor': 'top',
                    'text-size': 12,
                },
                paint: {
                    'text-color': '#333333',
                    'text-halo-color': '#ffffff',
                    'text-halo-width': 1,
                },
            });

            // Add click handler for popups
            this.map.on('click', 'partners-markers', (e) => {
                const props = e.features[0].properties;
                const coordinates = e.features[0].geometry.coordinates.slice();
                
                const popup = new bkoi.Popup()
                    .setLngLat(coordinates)
                    .setHTML(this.getPopupContent(props))
                    .addTo(this.map);
                
                // Add click handler for the "Open Partner" button in popup
                setTimeout(() => {
                    const openBtn = document.querySelector('.o_open_partner');
                    if (openBtn) {
                        openBtn.addEventListener('click', (ev) => {
                            ev.preventDefault();
                            const partnerId = parseInt(openBtn.dataset.partnerId);
                            if (partnerId) {
                                this.openPartner(partnerId);
                            }
                        });
                    }
                }, 100);
            });

            // Change cursor on hover
            this.map.on('mouseenter', 'partners-markers', () => {
                this.map.getCanvas().style.cursor = 'pointer';
            });
            this.map.on('mouseleave', 'partners-markers', () => {
                this.map.getCanvas().style.cursor = '';
            });
        }
    }

    getPopupContent(props) {
        return `
            <div class="o_barikoi_partner_popup" style="min-width: 200px;">
                <h6 style="margin-bottom: 8px; color: #714B67;"><b>${props.name}</b></h6>
                ${props.street ? `<p style="margin-bottom: 4px; font-size: 12px;"><i class="fa fa-map-marker" style="width: 16px; color: #6c757d;"></i> ${props.street}</p>` : ''}
                ${props.city ? `<p style="margin-bottom: 4px; font-size: 12px;"><i class="fa fa-building" style="width: 16px; color: #6c757d;"></i> ${props.city}</p>` : ''}
                ${props.phone ? `<p style="margin-bottom: 4px; font-size: 12px;"><i class="fa fa-phone" style="width: 16px; color: #6c757d;"></i> ${props.phone}</p>` : ''}
                ${props.email ? `<p style="margin-bottom: 4px; font-size: 12px;"><i class="fa fa-envelope" style="width: 16px; color: #6c757d;"></i> ${props.email}</p>` : ''}
                <hr style="margin: 8px 0;"/>
                <button class="btn btn-sm btn-primary o_open_partner" data-partner-id="${props.id}">
                    Open Partner
                </button>
            </div>
        `;
    }

    async getApiKey() {
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

    openPartner(partnerId) {
        // Open partner form view
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: partnerId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

// Register the client action - Odoo 19 style
registry.category("actions").add("barikoi_partner_map_view", BarikoiPartnerMapView);