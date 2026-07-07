/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, useState, useRef } from "@odoo/owl";

export class RouteMapDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.mapRef = useRef("mapContainer");
        this.map = null;
        this.routeLayer = null;
        this.markersGroup = null;

        const today = new Date().toISOString().split("T")[0];

        this.state = useState({
            isLoading: false,
            selectedDate: today,
            employees: [],
            selectedEmployeeId: null,
            attendances: [],
            selectedAttendanceId: null,
            locationPoints: [],
            mapTileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        });

        onWillStart(async () => {
            // Load Map Tile config from settings
            try {
                const configTile = await this.orm.call("ir.config_parameter", "get_param", [
                    "meta_ss_location_tracking.map_tile_url",
                    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                ]);
                this.state.mapTileUrl = configTile || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
            } catch (err) {
                console.error("Failed to load map tile url configuration", err);
            }
            await this.loadEmployees();
        });

        onMounted(() => {
            this.initMap();
        });
    }

    initMap() {
        if (!this.mapRef.el) return;

        // Initialize Leaflet Map (Centered on Bangladesh / Dhaka as default center)
        this.map = L.map(this.mapRef.el).setView([23.8103, 90.4125], 8);

        // Add Tile Layer
        L.tileLayer(this.state.mapTileUrl, {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(this.map);

        this.routeLayer = L.featureGroup().addTo(this.map);
        this.markersGroup = L.featureGroup().addTo(this.map);
    }

    async loadEmployees() {
        this.state.isLoading = true;
        try {
            // Fetch all active employees
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

            // Search for attendance records of this employee on the selected date
            const attendances = await this.orm.searchRead(
                "hr.attendance",
                [
                    ["employee_id", "=", employeeId],
                    ["check_in", ">=", dateStart],
                    ["check_in", "<=", dateEnd],
                ],
                ["id", "check_in", "check_out", "check_in_address", "check_out_address"]
            );
            this.state.attendances = attendances || [];
            
            // If attendances exist, automatically load the first one
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

    async loadLocationPoints(attendanceId) {
        this.state.isLoading = true;
        try {
            const points = await this.orm.searchRead(
                "sales.employee.location",
                [["attendance_id", "=", attendanceId]],
                ["id", "latitude", "longitude", "accuracy", "speed", "battery_level", "recorded_at", "is_mock"],
                { order: "recorded_at asc" }
            );
            this.state.locationPoints = points || [];
            this.plotPoints();
        } catch (error) {
            this.notification.add("Failed to load location logs.", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    clearMap() {
        if (this.routeLayer) this.routeLayer.clearLayers();
        if (this.markersGroup) this.markersGroup.clearLayers();
    }

    plotPoints() {
        this.clearMap();
        if (!this.state.locationPoints || this.state.locationPoints.length === 0) {
            return;
        }

        const latlngs = [];

        this.state.locationPoints.forEach((pt, index) => {
            const latlng = [pt.latitude, pt.longitude];
            latlngs.push(latlng);

            // Choose color: Red for mock locations, green for start, checkered/black for end, blue for normal
            let markerColor = "#3388ff";
            let popupTitle = "Log Point";
            
            if (pt.is_mock) {
                markerColor = "#ff3333";
                popupTitle = "⚠️ Mock/Spoofed Location";
            } else if (index === 0) {
                markerColor = "#22bb22";
                popupTitle = "🏁 Start Point";
            } else if (index === this.state.locationPoints.length - 1) {
                markerColor = "#111111";
                popupTitle = "🏁 End Point";
            }

            // Create circular marker for sleek design
            const marker = L.circleMarker(latlng, {
                radius: 8,
                fillColor: markerColor,
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8,
            });

            // Set Popup Content
            const timeStr = pt.recorded_at ? pt.recorded_at.split(" ")[1] : "N/A";
            const popupHtml = `
                <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4;">
                    <strong style="color: ${markerColor}">${popupTitle}</strong><br/>
                    <b>Time:</b> ${timeStr}<br/>
                    <b>Lat/Lng:</b> ${pt.latitude.toFixed(5)}, ${pt.longitude.toFixed(5)}<br/>
                    <b>Accuracy:</b> ${pt.accuracy ? pt.accuracy.toFixed(1) + ' m' : 'N/A'}<br/>
                    <b>Speed:</b> ${pt.speed ? (pt.speed * 3.6).toFixed(1) + ' km/h' : 'N/A'}<br/>
                    <b>Battery:</b> ${pt.battery_level ? pt.battery_level + '%' : 'N/A'}<br/>
                    ${pt.is_mock ? '<strong style="color: red; display: block; margin-top: 4px;">⚠️ Fake GPS Detected!</strong>' : ''}
                </div>
            `;
            marker.bindPopup(popupHtml);
            this.markersGroup.addLayer(marker);
        });

        // Draw polyline connecting points
        if (latlngs.length > 1) {
            const polyline = L.polyline(latlngs, {
                color: "#2563eb",
                weight: 5,
                opacity: 0.8,
                dashArray: pt => pt.is_mock ? "5, 5" : null,
            });
            this.routeLayer.addLayer(polyline);
        }

        // Fit map boundaries to coordinates
        const bounds = L.latLngBounds(latlngs);
        this.map.fitBounds(bounds, { padding: [50, 50] });
    }

    formatTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        return dateTimeStr.split(" ")[1] || dateTimeStr;
    }
}

RouteMapDashboard.template = "meta_ss_location_tracking.RouteMapDashboard";

registry.category("actions").add("meta_ss_location_tracking.route_map_dashboard", RouteMapDashboard);
