/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, onMounted, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";

export class CustomerDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartMarketRef = useRef("chart_market");

        this.state = useState({
            kpi: { active_clients: 0, largest_fleet: {id: false, name: '-', count: 0} },
            lists: { risk_watchlist: [], all_customers: [] },
            searchQuery: ""
        });

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

    get filteredCustomers() {
        const query = this.state.searchQuery.toLowerCase();
        if (!query) return this.state.lists.all_customers;

        return this.state.lists.all_customers.filter(c =>
            (c.name && c.name.toLowerCase().includes(query)) ||
            (c.email && c.email.toLowerCase().includes(query)) ||
            (c.city && c.city.toLowerCase().includes(query))
        );
    }

    async renderCharts() {
        if (!window.Chart || !this.chartMarketRef.el) return;

        new Chart(this.chartMarketRef.el, {
            type: 'bar',
            data: {
                labels: this.chartData.market_share.labels,
                datasets: [{
                    label: 'Fleet Size',
                    data: this.chartData.market_share.data,
                    backgroundColor: '#4F46E5',
                    borderRadius: 6,
                    barThickness: 40
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, grid: { display: false } },
                    x: { grid: { display: false } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    openCustomer(id) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            res_id: id,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    openNewCustomer() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            views: [[false, 'form']],
            target: 'current',
            context: {
                'default_customer_rank': 1,
                'default_is_company': true,
                'default_type': 'contact'
            }
        });
    }
}
CustomerDashboard.template = "certification.CustomerDashboard";
registry.category("actions").add("certification.customer_dashboard_client_action", CustomerDashboard);