/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// Bangladesh District to Division Mapping
// This mapping is used when Barikoi autocomplete doesn't return division
const DISTRICT_TO_DIVISION = {
    // Barishal Division
    'Barguna': 'Barishal',
    'Barisal': 'Barishal',
    'Bhola': 'Barishal',
    'Jhalokati': 'Barishal',
    'Patuakhali': 'Barishal',
    'Pirojpur': 'Barishal',
    // Chattogram Division
    'Bandarban': 'Chattogram',
    'Brahmanbaria': 'Chattogram',
    'Chandpur': 'Chattogram',
    'Chittagong': 'Chattogram',
    'Comilla': 'Chattogram',
    "Cox's Bazar": 'Chattogram',
    'Feni': 'Chattogram',
    'Khagrachhari': 'Chattogram',
    'Lakshmipur': 'Chattogram',
    'Noakhali': 'Chattogram',
    'Rangamati': 'Chattogram',
    // Dhaka Division
    'Dhaka': 'Dhaka',
    'Faridpur': 'Dhaka',
    'Gazipur': 'Dhaka',
    'Gopalganj': 'Dhaka',
    'Kishoreganj': 'Dhaka',
    'Madaripur': 'Dhaka',
    'Manikganj': 'Dhaka',
    'Munshiganj': 'Dhaka',
    'Narayanganj': 'Dhaka',
    'Narsingdi': 'Dhaka',
    'Rajbari': 'Dhaka',
    'Shariatpur': 'Dhaka',
    'Tangail': 'Dhaka',
    // Khulna Division
    'Bagerhat': 'Khulna',
    'Chuadanga': 'Khulna',
    'Jessore': 'Khulna',
    'Jhenaidah': 'Khulna',
    'Khulna': 'Khulna',
    'Kushtia': 'Khulna',
    'Magura': 'Khulna',
    'Meherpur': 'Khulna',
    'Narail': 'Khulna',
    'Satkhira': 'Khulna',
    // Mymensingh Division
    'Jamalpur': 'Mymensingh',
    'Mymensingh': 'Mymensingh',
    'Netrokona': 'Mymensingh',
    'Sherpur': 'Mymensingh',
    // Rajshahi Division
    'Bogra': 'Rajshahi',
    'Joypurhat': 'Rajshahi',
    'Naogaon': 'Rajshahi',
    'Natore': 'Rajshahi',
    'Nawabganj': 'Rajshahi',
    'Pabna': 'Rajshahi',
    'Rajshahi': 'Rajshahi',
    'Sirajganj': 'Rajshahi',
    // Rangpur Division
    'Dinajpur': 'Rangpur',
    'Gaibandha': 'Rangpur',
    'Kurigram': 'Rangpur',
    'Lalmonirhat': 'Rangpur',
    'Nilphamari': 'Rangpur',
    'Panchagarh': 'Rangpur',
    'Rangpur': 'Rangpur',
    'Thakurgaon': 'Rangpur',
    // Sylhet Division
    'Habiganj': 'Sylhet',
    'Moulvibazar': 'Sylhet',
    'Sunamganj': 'Sylhet',
    'Sylhet': 'Sylhet',
};

/**
 * Barikoi Autocomplete Widget
 * Works like Odoo's many2one autocomplete with dropdown suggestions
 */
export class BarikoiAutocomplete extends Component {
    static template = "meta_barikoi_address_autocomplete.BarikoiAutocomplete";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            suggestions: [],
            showDropdown: false,
            loading: false,
            selectedIndex: 0,
            inputValue: this.props.record.data[this.props.name] || "",
        });
        
        this.debounceTimer = null;
        this.inputRef = useRef("input");
        this.orm = useService("orm");
        this.notification = useService("notification");
        
        onMounted(() => {
            document.addEventListener("click", this.onDocumentClick.bind(this));
        });
        
        onWillUnmount(() => {
            document.removeEventListener("click", this.onDocumentClick.bind(this));
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
        });
    }

    onDocumentClick(ev) {
        const inputEl = this.inputRef.el;
        if (inputEl && !inputEl.contains(ev.target)) {
            this.state.showDropdown = false;
        }
    }

    get currentValue() {
        return this.props.record.data[this.props.name] || "";
    }

    onInput(ev) {
        const value = ev.target.value;
        this.state.inputValue = value;
        
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        
        if (value.length >= 2) {
            this.state.loading = true;
            this.debounceTimer = setTimeout(() => {
                this.fetchSuggestions(value);
            }, 300);
        } else {
            this.state.suggestions = [];
            this.state.showDropdown = false;
            this.state.loading = false;
        }
    }

    onFocus(ev) {
        if (this.state.suggestions.length > 0) {
            this.state.showDropdown = true;
        }
    }

    onKeyDown(ev) {
        if (!this.state.showDropdown || this.state.suggestions.length === 0) {
            return;
        }
        
        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                this.state.selectedIndex = Math.min(
                    this.state.selectedIndex + 1,
                    this.state.suggestions.length - 1
                );
                break;
            case "ArrowUp":
                ev.preventDefault();
                this.state.selectedIndex = Math.max(this.state.selectedIndex - 1, 0);
                break;
            case "Enter":
                ev.preventDefault();
                if (this.state.selectedIndex >= 0) {
                    this.selectSuggestion(this.state.selectedIndex);
                }
                break;
            case "Escape":
                this.state.showDropdown = false;
                break;
            case "Tab":
                this.state.showDropdown = false;
                break;
        }
    }

    async fetchSuggestions(query) {
        this.state.loading = true;
        
        try {
            const result = await this.orm.call(
                "barikoi.api",
                "autocomplete",
                [query],
                { context: this.props.record.context }
            );
            
            if (result && result.places && result.places.length > 0) {
                this.state.suggestions = result.places.map(place => ({
                    id: place.id,
                    name: place.name || place.address || "",
                    address: place.address || "",
                    city: place.city || "",
                    area: place.area || "",
                    district: place.district || "",
                    division: place.division || "",
                    post_code: place.postCode || place.post_code || "",
                    sub_district: place.sub_district || "",
                    // Handle various field name formats from Barikoi API
                    latitude: place.latitude || place.lat || place.Latitude,
                    longitude: place.longitude || place.lon || place.Longitude,
                    uCode: place.uCode || place.ucode,
                    label: place.address || place.name || "",
                }));
                this.state.showDropdown = true;
                this.state.selectedIndex = 0;
            } else {
                this.state.suggestions = [];
                this.state.showDropdown = false;
            }
        } catch (error) {
            console.error("Barikoi autocomplete error:", error);
            this.state.suggestions = [];
            this.state.showDropdown = false;
        } finally {
            this.state.loading = false;
        }
    }

    async selectSuggestion(index) {
        const suggestion = this.state.suggestions[index];
        if (!suggestion) return;
        
        const selectedValue = suggestion.label || suggestion.name;
        this.state.showDropdown = false;
        this.state.suggestions = [];
        this.state.inputValue = selectedValue;
        
        // Build all changes
        const changes = { [this.props.name]: selectedValue };
        
        // City - use district as city (Bangladesh mapping)
        if (suggestion.district) {
            changes.city = suggestion.district;
        } else if (suggestion.city) {
            changes.city = suggestion.city;
        }
        
        // ZIP/Postcode
        if (suggestion.post_code) {
            changes.zip = String(suggestion.post_code);
        }
        
        // Street2 - additional address info (area)
        if (suggestion.area) {
            changes.street2 = suggestion.area;
        }
        
        // Coordinates
        if (suggestion.latitude !== undefined && suggestion.latitude !== null) {
            const lat = parseFloat(suggestion.latitude);
            if (!isNaN(lat)) {
                changes.partner_latitude = lat;
            }
        }
        if (suggestion.longitude !== undefined && suggestion.longitude !== null) {
            const lng = parseFloat(suggestion.longitude);
            if (!isNaN(lng)) {
                changes.partner_longitude = lng;
            }
        }
        
        // Barikoi-specific fields
        if (suggestion.division) {
            changes.barikoi_division = suggestion.division;
        }
        if (suggestion.district) {
            changes.barikoi_district = suggestion.district;
        }
        if (suggestion.sub_district) {
            changes.barikoi_upazila = suggestion.sub_district;
        }
        if (suggestion.id) {
            changes.barikoi_place_id = String(suggestion.id);
        }
        if (suggestion.uCode) {
            changes.barikoi_ucode = suggestion.uCode;
        }
        
        
        // For existing records, call server method to update all fields atomically
        if (this.props.record.resId) {
            try {
                // Call server method that handles everything atomically and returns updated values
                const result = await this.orm.call(
                    "res.partner",
                    "update_from_barikoi_suggestion",
                    [[this.props.record.resId], suggestion],
                    { context: this.props.record.context }
                );
                
                // Update the form with the returned values (including many2one display names)
                if (result) {
                    this.props.record.update(result);
                }
                
            } catch (e) {
                console.error("Barikoi: Error updating from suggestion:", e);
                this.notification.add(_("Error saving address data"), { type: "danger" });
            }
        } else {
            // For new records, use form update
            this.props.record.update(changes);
            const countryStateData = await this._getCountryAndStateData(suggestion);
            this.props.record.update(countryStateData);
        }
    }

    /**
     * Get country and state data for the address (for new records)
     * Returns many2one values in the format { id: number, display_name: string }
     * Note: For Bangladesh, Odoo states are DIVISIONS (not districts)
     */
    async _getCountryAndStateData(place) {
        const result = {};
        try {
            // Get Bangladesh country
            const countries = await this.orm.searchRead(
                "res.country",
                [["code", "=", "BD"]],
                ["id", "name"],
                { limit: 1 }
            );
            
            if (countries && countries.length > 0) {
                const country = countries[0];
                // Many2one format: { id: number, display_name: string }
                result.country_id = {
                    id: country.id,
                    display_name: country.name,
                };
                
                // In Bangladesh, Odoo states are DIVISIONS
                // Barikoi autocomplete API doesn't return division, so we use district-to-division mapping
                const districtName = place.district || '';
                const divisionName = place.division || DISTRICT_TO_DIVISION[districtName] || '';
                
                if (divisionName) {
                    // First try exact match
                    let states = await this.orm.searchRead(
                        "res.country.state",
                        [
                            ["name", "=", divisionName],
                            ["country_id", "=", country.id]
                        ],
                        ["id", "name"],
                        { limit: 1 }
                    );
                    
                    // If no exact match, try ilike (case-insensitive)
                    if (!states || states.length === 0) {
                        states = await this.orm.searchRead(
                            "res.country.state",
                            [
                                ["name", "ilike", divisionName],
                                ["country_id", "=", country.id]
                            ],
                            ["id", "name"],
                            { limit: 1 }
                        );
                    }
                    
                    if (states && states.length > 0) {
                        const state = states[0];
                        result.state_id = {
                            id: state.id,
                            display_name: state.name,
                        };
                        result.barikoi_division = divisionName;
                    }
                }
            }
        } catch (e) {
            console.error("Barikoi: Error getting country/state:", e);
        }
        return result;
    }

    onSuggestionClick(index) {
        this.selectSuggestion(index);
    }

    onSuggestionMouseEnter(index) {
        this.state.selectedIndex = index;
    }
}

// Register the widget
registry.category("fields").add("barikoi_autocomplete", {
    component: BarikoiAutocomplete,
    displayName: _t("Barikoi Autocomplete"),
    supportedTypes: ["char"],
    extractProps: ({ attrs }) => ({
        placeholder: attrs.placeholder || _t("Start typing address..."),
    }),
});