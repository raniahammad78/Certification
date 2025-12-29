/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, onMounted, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";

export class InspectionDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.chartStatusRef = useRef("chart_status");

        this.state = useState({
            kpi: { total_insp: 0, passed: 0, failed: 0, total_machines: 0 },
            lists: { recent: [], expiring: [] },
            inspectors: []
        });

        this.chartData = { status: [0, 0, 0] };

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboardData();
        });

        onMounted(async () => { await this.renderCharts(); });
    }

    async loadDashboardData() {
        try {
            const result = await this.orm.call("inspection.inspection", "get_dashboard_stats", []);
            if (result) {
                this.state.kpi = result.kpi || this.state.kpi;
                this.state.lists = result.lists || this.state.lists;

                if (result.inspectors) {
                    this.state.inspectors = result.inspectors;
                }

                if (result.charts && result.charts.status) {
                    this.chartData.status = result.charts.status;
                }
            }
        } catch (e) { console.error("Error loading dashboard data", e); }
    }

    async renderCharts() {
        if (!window.Chart || !this.chartStatusRef.el) return;

        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        this.chartInstance = new Chart(this.chartStatusRef.el, {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Pending'],
                datasets: [{
                    data: this.chartData.status,
                    backgroundColor: ['#38a169', '#e53e3e', '#d69e2e'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'right', labels: { boxWidth: 12 } } },
                cutout: '70%',
            }
        });
    }

    openView(model, viewType = 'list') {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            views: [[false, viewType], [false, 'form']],
            target: 'current'
        });
    }

    openInspection(id) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'inspection.inspection',
            res_id: id,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    // === NEW FUNCTION: OPEN INSPECTOR'S WORK ===
    openInspectorInspections(inspectorId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Inspector Activity',
            res_model: 'inspection.inspection',
            domain: [['inspector_id', '=', inspectorId]], // Filters by the clicked inspector
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    openInspectionsByStatus(status) {
        let domain = [];
        let name = "Inspections";

        if (status === 'passed') {
            domain = [['status', '=', 'passed']];
            name = "Passed Inspections";
        } else if (status === 'failed') {
            domain = [['status', '=', 'failed']];
            name = "Failed Inspections";
        } else if (status === 'pending') {
            domain = [['status', '=', 'draft']];
            name = "Pending Inspections";
        }

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: 'inspection.inspection',
            domain: domain,
            views: [[false, 'list'], [false, 'form']],
            target: 'current'
        });
    }
}
InspectionDashboard.template = "certification.InspectionDashboard";
registry.category("actions").add("certification.dashboard_client_action", InspectionDashboard);