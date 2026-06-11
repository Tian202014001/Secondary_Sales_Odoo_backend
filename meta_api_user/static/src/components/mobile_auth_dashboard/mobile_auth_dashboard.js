/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class MobileAuthDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            isLoading: true,
            stats: {},
            settings: {},
            recentSessions: [],
            actions: {},
        });

        onWillStart(async () => {
            await this.refresh();
        });
    }

    async refresh() {
        this.state.isLoading = true;
        try {
            const data = await this.orm.call("mobile.auth.session", "get_dashboard_data", []);
            this.state.stats = data.stats || {};
            this.state.settings = data.settings || {};
            this.state.recentSessions = data.recent_sessions || [];
            this.state.actions = data.actions || {};
        } catch (error) {
            this.notification.add("Unable to load the Mobile API dashboard.", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    openNamedAction(key) {
        const config = this.state.actions[key];
        if (!config) {
            return;
        }
        this.openRecords(config.model, config.domain, config.name, config.context);
    }

    openRecords(model, domain = [], name = "Records", context = {}) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            domain,
            context,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openSession(sessionId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Mobile Session",
            res_model: "mobile.auth.session",
            res_id: sessionId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    sessionUserName(session) {
        return session.mobile_user_id ? session.mobile_user_id[1] : "Unknown user";
    }

    formatState(state) {
        const labels = {
            active: "Active",
            refresh_expired: "Expired",
            logged_out: "Logged Out",
            revoked: "Revoked",
        };
        return labels[state] || state || "";
    }

    openSettings() {
        this.action.doAction("base_setup.action_general_configuration");
    }
}

MobileAuthDashboard.template = "meta_api_user.MobileAuthDashboard";

registry.category("actions").add("meta_api_user.mobile_auth_dashboard", MobileAuthDashboard);
