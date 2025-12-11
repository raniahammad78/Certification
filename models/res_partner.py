from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'


    # Link to Machines
    machine_ids = fields.One2many('inspection.machine', 'partner_id', string="Machines")
    machine_count = fields.Integer(compute='_compute_machine_count', string="Machine Count")

    # Link to Inspections
    inspection_ids = fields.One2many('inspection.inspection', 'customer_id', string="Inspections")
    inspection_count = fields.Integer(compute='_compute_inspection_count', string="Inspection Count")

    # Link to Categories (Computed from Machines)
    category_ids = fields.Many2many('inspection.category', compute='_compute_categories', string="Linked Categories")
    category_count = fields.Integer(compute='_compute_category_count', string="Category Count")

    @api.depends('machine_ids')
    def _compute_machine_count(self):
        for partner in self:
            partner.machine_count = len(partner.machine_ids)

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for partner in self:
            partner.inspection_count = len(partner.inspection_ids)

    @api.depends('machine_ids.category_id')
    def _compute_categories(self):
        for partner in self:
            # Get all unique categories from this partner's machines
            partner.category_ids = partner.machine_ids.mapped('category_id')

    @api.depends('category_ids')
    def _compute_category_count(self):
        for partner in self:
            partner.category_count = len(partner.category_ids)

    # ACTIONS
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
            'name': 'Inspections',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.inspection',
            'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
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
