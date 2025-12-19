/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, onMounted } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";

export class MachineDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartManRef = useRef("chart_manufacturer");
        this.chartCatRef = useRef("chart_category");

        this.state = {
            kpi: { total: 0, compliant: 0, non_compliant: 0, manufacturers: 0 },
            lists: { non_compliant: [] }
        };

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadData();
        });

        onMounted(async () => {
            await this.renderCharts();
        });
    }

    async loadData() {
        const result = await this.orm.call("inspection.machine", "get_machine_dashboard_stats", []);
        this.state.kpi = result.kpi;
        this.state.lists = result.lists;
        this.chartData = result.charts;
    }

    async renderCharts() {
        if (this.chartManRef.el) {
            new Chart(this.chartManRef.el, {
                type: 'doughnut',
                data: {
                    labels: this.chartData.manufacturer.labels,
                    datasets: [{
                        data: this.chartData.manufacturer.data,
                        backgroundColor: ['#6f42c1', '#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8'],
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' }, title: { display: true, text: 'Top Manufacturers' } }
                }
            });
        }

        if (this.chartCatRef.el) {
            new Chart(this.chartCatRef.el, {
                type: 'bar',
                data: {
                    labels: this.chartData.category.labels,
                    datasets: [{
                        label: 'Machines',
                        data: this.chartData.category.data,
                        backgroundColor: '#6f42c1',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false }, title: { display: true, text: 'Fleet by Category' } },
                    scales: { y: { beginAtZero: true } }
                }
            });
        }
    }

    openMachine(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "inspection.machine",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    viewAllMachines() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "All Machines",
            res_model: "inspection.machine",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

MachineDashboard.template = "certification.MachineDashboard";
// IMPORTANT: This registers the tag used in step 7
registry.category("actions").add("certification.machine_dashboard_client_action", MachineDashboard);