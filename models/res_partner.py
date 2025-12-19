from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Link to Machines
    machine_ids = fields.One2many('inspection.machine', 'partner_id', string="Machines")
    machine_count = fields.Integer(compute='_compute_machine_count', string="Machine Count")

    # Link to Inspections (ALL)
    inspection_ids = fields.One2many('inspection.inspection', 'customer_id', string="Inspections")
    inspection_count = fields.Integer(compute='_compute_inspection_count', string="Inspection Count")

    # Link to Certificates (PASSED ONLY) - NEW FEATURE
    certificate_count = fields.Integer(compute='_compute_certificate_count', string="Certificates")

    # Link to Categories
    category_ids = fields.Many2many('inspection.category', compute='_compute_categories', string="Linked Categories")
    category_count = fields.Integer(compute='_compute_category_count', string="Category Count")

    # ---------------------------------------------------------
    # COMPUTE METHODS
    # ---------------------------------------------------------
    @api.depends('machine_ids')
    def _compute_machine_count(self):
        for partner in self:
            partner.machine_count = len(partner.machine_ids)

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for partner in self:
            partner.inspection_count = len(partner.inspection_ids)

    @api.depends('inspection_ids.status')
    def _compute_certificate_count(self):
        """Count only passed inspections which serve as certificates"""
        for partner in self:
            partner.certificate_count = self.env['inspection.inspection'].search_count([
                ('customer_id', '=', partner.id),
                ('status', '=', 'passed')
            ])

    @api.depends('machine_ids.category_id')
    def _compute_categories(self):
        for partner in self:
            partner.category_ids = partner.machine_ids.mapped('category_id')

    @api.depends('category_ids')
    def _compute_category_count(self):
        for partner in self:
            partner.category_count = len(partner.category_ids)

    # ---------------------------------------------------------
    # SMART BUTTON ACTIONS
    # ---------------------------------------------------------
    def action_view_machines(self):
        self.ensure_one()
        return {
            'name': 'Machines',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.machine',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_inspections(self):
        self.ensure_one()
        return {
            'name': 'All Inspections',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.inspection',
            'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
        }

    def action_view_certificates(self):
        """Open only passed inspections (Digital Folder)"""
        self.ensure_one()
        return {
            'name': 'Certificates',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.inspection',
            'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id), ('status', '=', 'passed')],
            'context': {'default_customer_id': self.id},
        }

    def action_view_categories(self):
        self.ensure_one()
        return {
            'name': 'Categories',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.category',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.category_ids.ids)],
        }

    # ---------------------------------------------------------
    # CUSTOMER DASHBOARD DATA
    # ---------------------------------------------------------
    @api.model
    def get_customer_dashboard_stats(self):
        """Data for the refined Customer Dashboard"""

        Machine = self.env['inspection.machine']
        Inspection = self.env['inspection.inspection']

        # 1. KPIs
        # Total Active Customers
        customers_with_machines = Machine.read_group([], ['partner_id'], ['partner_id'])
        total_active = len(customers_with_machines)

        # 2. Charts: Top 5 Customers
        fleet_counts = Machine.read_group(
            domain=[],
            fields=['partner_id'],
            groupby=['partner_id'],
            orderby='partner_id_count desc',
            limit=5
        )

        top_clients_labels = []
        top_clients_data = []
        top_client_id = False

        for group in fleet_counts:
            if group['partner_id']:
                top_clients_labels.append(group['partner_id'][1])
                top_clients_data.append(group['partner_id_count'])
                # Capture the ID of the #1 client
                if not top_client_id:
                    top_client_id = group['partner_id'][0]

        top_client_name = top_clients_labels[0] if top_clients_labels else "N/A"
        top_client_count = top_clients_data[0] if top_clients_data else 0

        # 3. List: Risk Watchlist
        failed_inspections = Inspection.read_group(
            [('status', '=', 'failed')],
            ['customer_id'],
            ['customer_id'],
            orderby='customer_id_count desc',
            limit=5
        )

        risk_watchlist = []
        for group in failed_inspections:
            if group['customer_id']:
                partner = self.browse(group['customer_id'][0])
                risk_watchlist.append({
                    'id': group['customer_id'][0],
                    'name': group['customer_id'][1],
                    'phone': partner.phone or '',
                    'fail_count': group['customer_id_count']
                })

        return {
            'kpi': {
                'total_active': total_active,
                'top_client_name': top_client_name,
                'top_client_count': top_client_count,
                'top_client_id': top_client_id,
            },
            'charts': {
                'top_clients': {
                    'labels': top_clients_labels,
                    'data': top_clients_data
                }
            },
            'lists': {
                'risk_watchlist': risk_watchlist
            }
        }
