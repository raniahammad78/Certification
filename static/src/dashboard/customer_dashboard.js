/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, onMounted } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";

export class CustomerDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartMarketRef = useRef("chart_market");

        this.state = {
            kpi: { active_clients: 0, largest_fleet: {id: false, name: '-', count: 0} },
            lists: { risk_watchlist: [] }
        };
        this.chartData = { market_share: { labels: [], data: [] } };

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadData();
        });
        onMounted(async () => { await this.renderCharts(); });
    }

    async loadData() {
        try {
            const result = await this.orm.call("inspection.inspection", "get_customer_dashboard_stats", []);
            if (result) {
                this.state.kpi = result.kpi;
                this.state.lists = result.lists;
                this.chartData = result.charts;
            }
        } catch (e) { console.error("Error loading customer stats", e); }
    }

    async renderCharts() {
        if (!window.Chart || !this.chartMarketRef.el) return;

        new Chart(this.chartMarketRef.el, {
            type: 'bar',
            data: {
                labels: this.chartData.market_share.labels,
                datasets: [{
                    label: 'Machines',
                    data: this.chartData.market_share.data,
                    backgroundColor: '#5856d6',
                    borderRadius: 8,
                    barThickness: 30,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { beginAtZero: true, grid: { borderDash: [4, 4], drawBorder: false } },
                    y: { grid: { display: false } }
                },
                plugins: { legend: { display: false } },
                onClick: (e) => this.openAllCustomers() // Click chart to see all customers
            }
        });
    }

    // 1. Open specific customer form
    openCustomer(id) {
        if (!id) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: id,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    // 2. Open full list of customers
    openAllCustomers() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Customers',
            res_model: 'res.partner',
            views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
            target: 'current'
        });
    }
}
CustomerDashboard.template = "certification.CustomerDashboard";
registry.category("actions").add("certification.customer_dashboard_client_action", CustomerDashboard);