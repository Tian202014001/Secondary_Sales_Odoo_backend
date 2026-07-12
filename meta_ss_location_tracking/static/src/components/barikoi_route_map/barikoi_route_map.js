/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, onWillUnmount, useState, useRef } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

/* global bkoi */

export class BarikoiRouteMapDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.mapRef = useRef("mapContainer");
        this.map = null;
        this.markers = [];
        this.apiKey = "";

        const today = new Date().toISOString().split("T")[0];

        this.state = useState({
            isLoading: false,
            selectedDate: today,
            employees: [],
            selectedEmployeeId: null,
            attendances: [],
            selectedAttendanceId: null,
            locationPoints: [],
            error: null,
        });

        onWillStart(async () => {
            // Load Barikoi API key
            try {
                const configKey = await this.orm.call("ir.config_parameter", "get_param", [
                    "barikoi.api_key",
                    "",
                ]);
                this.apiKey = configKey;
                if (!this.apiKey) {
                    this.state.error = "Barikoi API Key is not configured. Please configure it in settings.";
                }
            } catch (err) {
                console.error("Failed to load Barikoi API key configuration", err);
                this.state.error = "Failed to load Barikoi API key.";
            }
            await this.loadEmployees();
        });

        onMounted(async () => {
            if (this.apiKey) {
                try {
                    await this.loadBarikoiGL();
                    this.initMap();
                } catch (e) {
                    this.state.error = e.message || "Failed to load Barikoi GL library.";
                }
            }
        });

        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
            }
        });
    }

    async loadBarikoiGL() {
        const jsUrl = "https://unpkg.com/bkoi-gl@2.0.4/dist/iife/bkoi-gl.js";
        const cssUrl = "https://unpkg.com/bkoi-gl@2.0.4/dist/style/bkoi-gl.css";
        try {
            await Promise.all([
                loadJS(jsUrl),
                loadCSS(cssUrl),
            ]);
            // Resolve the global variable exported by the Barikoi GL JS package (handles both bkoigl and bkoi)
            const bkoiLib = (typeof bkoigl !== 'undefined') ? bkoigl : ((typeof bkoi !== 'undefined') ? bkoi : null);
            if (!bkoiLib) {
                throw new Error("Neither bkoigl nor bkoi global namespace is defined");
            }
            window.bkoi = bkoiLib;
        } catch (e) {
            console.error("Failed to load Barikoi GL:", e);
            throw new Error("Failed to load Barikoi GL library from CDN: " + e.message);
        }
    }

    initMap() {
        if (!this.mapRef.el || !this.apiKey) return;

        try {
            bkoi.accessToken = this.apiKey;
            this.map = new bkoi.Map({
                container: this.mapRef.el,
                center: [90.4125, 23.8103], // [lng, lat]
                zoom: 8,
                style: "https://map.barikoi.com/styles/osm-liberty/style.json",
                accessToken: this.apiKey,
            });

            this.map.addControl(new bkoi.NavigationControl(), 'top-right');

            this.map.on('load', () => {
                if (this.state.locationPoints.length > 0) {
                    this.plotPoints();
                }
            });
        } catch (err) {
            console.error("Barikoi Map initialization error:", err);
            this.state.error = "Failed to load Barikoi Map: " + err.message;
        }
    }

    async loadEmployees() {
        this.state.isLoading = true;
        try {
            const employees = await this.orm.searchRead(
                "hr.employee",
                [],
                ["id", "name", "work_email", "image_128"]
            );
            this.state.employees = employees || [];
        } catch (error) {
            this.notification.add("Unable to fetch employees.", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    async onDateChange(ev) {
        this.state.selectedDate = ev.target.value;
        if (this.state.selectedEmployeeId) {
            await this.loadAttendances(this.state.selectedEmployeeId);
        }
    }

    async selectEmployee(employeeId) {
        this.state.selectedEmployeeId = employeeId;
        this.state.selectedAttendanceId = null;
        this.state.locationPoints = [];
        this.clearMap();
        await this.loadAttendances(employeeId);
    }

    async loadAttendances(employeeId) {
        this.state.isLoading = true;
        try {
            const dateStart = this.state.selectedDate + " 00:00:00";
            const dateEnd = this.state.selectedDate + " 23:59:59";

            const attendances = await this.orm.searchRead(
                "hr.attendance",
                [
                    ["employee_id", "=", employeeId],
                    ["check_in", ">=", dateStart],
                    ["check_in", "<=", dateEnd],
                ],
                [
                    "id", "check_in", "check_out", 
                    "check_in_address", "check_out_address",
                    "check_in_latitude", "check_in_longitude",
                    "check_out_latitude", "check_out_longitude"
                ]
            );
            this.state.attendances = attendances || [];
            
            if (this.state.attendances.length > 0) {
                await this.selectAttendance(this.state.attendances[0].id);
            } else {
                this.state.selectedAttendanceId = null;
                this.state.locationPoints = [];
                this.clearMap();
            }
        } catch (error) {
            this.notification.add("Failed to load attendances.", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    async selectAttendance(attendanceId) {
        this.state.selectedAttendanceId = attendanceId;
        await this.loadLocationPoints(attendanceId);
    }

    getDistance(lat1, lon1, lat2, lon2) {
        const R = 6371e3; // metres
        const phi1 = lat1 * Math.PI/180;
        const phi2 = lat2 * Math.PI/180;
        const deltaPhi = (lat2-lat1) * Math.PI/180;
        const deltaLambda = (lon2-lon1) * Math.PI/180;

        const a = Math.sin(deltaPhi/2) * Math.sin(deltaPhi/2) +
                  Math.cos(phi1) * Math.cos(phi2) *
                  Math.sin(deltaLambda/2) * Math.sin(deltaLambda/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

        return R * c; // in metres
    }

    parseDateTime(str) {
        if (!str) return null;
        const parts = str.split(' ');
        const dateParts = parts[0].split('-');
        const timeParts = parts[1].split(':');
        return new Date(Date.UTC(
            parseInt(dateParts[0]),
            parseInt(dateParts[1]) - 1,
            parseInt(dateParts[2]),
            parseInt(timeParts[0]),
            parseInt(timeParts[1]),
            parseInt(timeParts[2])
        ));
    }

    processLocationPoints(points) {
        if (!points || points.length === 0) return [];
        const processed = [];
        for (let i = 0; i < points.length; i++) {
            const pt = points[i];
            let duration = 0;
            let isStop = false;

            if (i < points.length - 1) {
                const nextPt = points[i + 1];
                const t1 = this.parseDateTime(pt.recorded_at);
                const t2 = this.parseDateTime(nextPt.recorded_at);
                if (t1 && t2) {
                    duration = Math.round((t2 - t1) / 60000); // duration in minutes
                }
                const dist = this.getDistance(pt.latitude, pt.longitude, nextPt.latitude, nextPt.longitude);
                // If they spent more than 5 minutes and moved less than 50 meters, it's a stop
                if (duration >= 5 && dist < 50) {
                    isStop = true;
                }
            }

            processed.push({
                ...pt,
                duration,
                isStop
            });
        }
        return processed;
    }

    async loadLocationPoints(attendanceId) {
        this.state.isLoading = true;
        try {
            const points = await this.orm.searchRead(
                "sales.employee.location",
                [["attendance_id", "=", attendanceId]],
                ["id", "latitude", "longitude", "recorded_at", "is_mock"],
                { order: "recorded_at asc" }
            );
            this.state.locationPoints = this.processLocationPoints(points || []);
            this.plotPoints();
        } catch (error) {
            this.notification.add("Failed to load location logs.", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    clearMap() {
        if (this.markers) {
            this.markers.forEach(m => m.remove());
        }
        this.markers = [];

        if (this.map && this.map.getLayer('route')) {
            this.map.removeLayer('route');
        }
        if (this.map && this.map.getSource('route')) {
            this.map.removeSource('route');
        }
    }

    plotPoints() {
        this.clearMap();
        if (!this.map) return;

        const latlngs = [];
        const selectedAtt = this.state.attendances.find(a => a.id === this.state.selectedAttendanceId);

        // Plot Actual Check-In
        if (selectedAtt && selectedAtt.check_in_latitude && selectedAtt.check_in_longitude) {
            const latlng = [selectedAtt.check_in_longitude, selectedAtt.check_in_latitude];
            latlngs.push(latlng);

            const el = document.createElement('div');
            el.className = 'bkoi-route-marker';
            el.style.width = '30px';
            el.style.height = '30px';
            el.style.cursor = 'pointer';
            el.innerHTML = `
                <svg viewBox="0 0 24 24" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 2px 3px rgba(0,0,0,0.3));">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" 
                          fill="#059669" 
                          stroke="white" 
                          stroke-width="2"/>
                </svg>
            `;

            const checkInHtml = `
                <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4; padding: 4px;">
                    <strong style="color: #059669">📍 Actual Check-In</strong><br/>
                    <b>Time:</b> ${this.formatTime(selectedAtt.check_in)}<br/>
                    <b>Address:</b> ${selectedAtt.check_in_address || 'N/A'}<br/>
                </div>
            `;

            const marker = new bkoi.Marker({ element: el, anchor: 'bottom' })
                .setLngLat(latlng)
                .setPopup(new bkoi.Popup({ offset: [0, -15] }).setHTML(checkInHtml))
                .addTo(this.map);
            this.markers.push(marker);
        }

        // Plot Actual Check-Out
        if (selectedAtt && selectedAtt.check_out_latitude && selectedAtt.check_out_longitude) {
            const latlng = [selectedAtt.check_out_longitude, selectedAtt.check_out_latitude];
            latlngs.push(latlng);

            const el = document.createElement('div');
            el.className = 'bkoi-route-marker';
            el.style.width = '30px';
            el.style.height = '30px';
            el.style.cursor = 'pointer';
            el.innerHTML = `
                <svg viewBox="0 0 24 24" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 2px 3px rgba(0,0,0,0.3));">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" 
                          fill="#dc2626" 
                          stroke="white" 
                          stroke-width="2"/>
                </svg>
            `;

            const checkOutHtml = `
                <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4; padding: 4px;">
                    <strong style="color: #dc2626">📍 Actual Check-Out</strong><br/>
                    <b>Time:</b> ${this.formatTime(selectedAtt.check_out)}<br/>
                    <b>Address:</b> ${selectedAtt.check_out_address || 'N/A'}<br/>
                </div>
            `;

            const marker = new bkoi.Marker({ element: el, anchor: 'bottom' })
                .setLngLat(latlng)
                .setPopup(new bkoi.Popup({ offset: [0, -15] }).setHTML(checkOutHtml))
                .addTo(this.map);
            this.markers.push(marker);
        }

        if (!this.state.locationPoints || this.state.locationPoints.length === 0) {
            if (latlngs.length > 0) {
                const bounds = new bkoi.LngLatBounds();
                latlngs.forEach(coord => bounds.extend(coord));
                this.map.fitBounds(bounds, { padding: 50, maxZoom: 16 });
            }
            return;
        }


        this.state.locationPoints.forEach((pt, index) => {
            const latlng = [pt.longitude, pt.latitude]; // MapLibre/Barikoi GL uses [lng, lat]
            latlngs.push(latlng);

            let markerColor = "#3b82f6"; // Default active movement (Blue)
            let markerSize = 18; // Size in px
            let popupTitle = "Active Movement";
            let stopInfoHtml = "";
            let pulseClass = "";

            if (pt.is_mock) {
                markerColor = "#ef4444"; // Red for mock
                markerSize = 26;
                popupTitle = "⚠️ Mock/Spoofed Location";
                pulseClass = "bkoi-route-marker-mock";
            } else if (index === 0) {
                markerColor = "#10b981"; // Green for start
                markerSize = 28;
                popupTitle = "🏁 Start Point";
            } else if (index === this.state.locationPoints.length - 1) {
                markerColor = "#1f2937"; // Dark Gray for end
                markerSize = 28;
                popupTitle = "🏁 End Point";
            } else if (pt.isStop) {
                if (pt.duration >= 15) {
                    markerColor = "#d97706"; // Major Stop (Deep Amber)
                    markerSize = 32;
                    popupTitle = "🛑 Major Stop";
                    pulseClass = "bkoi-route-marker-major-stop";
                } else {
                    markerColor = "#f59e0b"; // Minor Stop (Yellow)
                    markerSize = 24;
                    popupTitle = "⏱️ Short Stop";
                }
                stopInfoHtml = `<b>Time Spent:</b> ${pt.duration} minutes<br/>`;
            }

            // Create custom map pin element
            const el = document.createElement('div');
            el.className = `bkoi-route-marker ${pulseClass}`;
            el.style.width = `${markerSize}px`;
            el.style.height = `${markerSize}px`;
            el.style.borderRadius = '50%'; // Ensures pulsing box-shadow is circular
            el.style.cursor = 'pointer';
            
            // Render high-quality SVG location pin
            el.innerHTML = `
                <svg viewBox="0 0 24 24" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 2px 3px rgba(0,0,0,0.3));">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" 
                          fill="${markerColor}" 
                          stroke="white" 
                          stroke-width="1.5"/>
                </svg>
            `;

            const timeStr = pt.recorded_at ? pt.recorded_at.split(" ")[1] : "N/A";
            const popupHtml = `
                <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4; padding: 4px;">
                    <strong style="color: ${markerColor}">${popupTitle}</strong><br/>
                    <b>Time:</b> ${timeStr}<br/>
                    ${stopInfoHtml}
                    <b>Lat/Lng:</b> ${pt.latitude.toFixed(5)}, ${pt.longitude.toFixed(5)}<br/>
                    ${pt.is_mock ? '<strong style="color: red; display: block; margin-top: 4px;">⚠️ Fake GPS Detected!</strong>' : ''}
                </div>
            `;

            const marker = new bkoi.Marker({ 
                element: el,
                anchor: 'bottom'
            })
                .setLngLat(latlng)
                .setPopup(new bkoi.Popup({ offset: [0, -markerSize / 2] }).setHTML(popupHtml))
                .addTo(this.map);

            this.markers.push(marker);
        });

        // Draw polyline connecting points with segment-based color coding
        if (this.state.locationPoints.length > 1) {
            const features = [];
            for (let i = 0; i < this.state.locationPoints.length - 1; i++) {
                const p1 = this.state.locationPoints[i];
                const p2 = this.state.locationPoints[i + 1];

                let segmentColor = "#3b82f6"; // Default Blue (Active Movement)
                let segmentWidth = 4;

                if (p1.is_mock || p2.is_mock) {
                    segmentColor = "#ef4444"; // Red for mock segment
                    segmentWidth = 4;
                } else if (p1.isStop) {
                    if (p1.duration >= 15) {
                        segmentColor = "#d97706"; // Orange for major stop segment
                        segmentWidth = 5;
                    } else {
                        segmentColor = "#f59e0b"; // Yellow for short stop segment
                        segmentWidth = 5;
                    }
                }

                features.push({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [
                            [p1.longitude, p1.latitude],
                            [p2.longitude, p2.latitude]
                        ]
                    },
                    'properties': {
                        'color': segmentColor,
                        'width': segmentWidth
                    }
                });
            }

            this.map.addSource('route', {
                'type': 'geojson',
                'data': {
                    'type': 'FeatureCollection',
                    'features': features
                }
            });

            this.map.addLayer({
                'id': 'route',
                'type': 'line',
                'source': 'route',
                'layout': {
                    'line-join': 'round',
                    'line-cap': 'round'
                },
                'paint': {
                    'line-color': ['get', 'color'],
                    'line-width': ['get', 'width'],
                    'line-opacity': 0.8
                }
            });
        }

        // Fit map boundaries to coordinates
        if (latlngs.length > 0) {
            const bounds = new bkoi.LngLatBounds();
            latlngs.forEach(coord => bounds.extend(coord));
            this.map.fitBounds(bounds, { padding: 50, maxZoom: 16 });
        }
    }

    formatTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        return dateTimeStr.split(" ")[1] || dateTimeStr;
    }
}

BarikoiRouteMapDashboard.template = "meta_ss_location_tracking.BarikoiRouteMapDashboard";

registry.category("actions").add("meta_ss_location_tracking.barikoi_route_map_dashboard", BarikoiRouteMapDashboard);
