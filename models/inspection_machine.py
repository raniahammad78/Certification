from odoo import models, fields, api


class InspectionMachine(models.Model):
    _name = 'inspection.machine'
    _description = 'Machine or Equipment'

    name = fields.Char(string="Machine Name/Description", required=True)

    serial_number = fields.Char(string="Serial Number")
    model_no = fields.Char(string="Model Number")
    swl = fields.Char(string="S.W.L. (Safe Working Load)", placeholder="e.g. 1 Ton")
    build_year = fields.Char(string="Date of Manufacture", placeholder="e.g. 2015")

    manufacturer = fields.Char(string="Manufacturer", placeholder="e.g. Caterpillar, Toyota")
    owner_id_no = fields.Char(string="Owner ID / Fleet No.", placeholder="e.g. FL-001")

    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    category_id = fields.Many2one('inspection.category', string="Category", required=True)

    custom_question_ids = fields.One2many('inspection.question', 'machine_id', string="Machine Specific Questions")
    inspection_ids = fields.One2many('inspection.inspection', 'machine_id', string="Inspections")
    inspection_count = fields.Integer(compute='_compute_inspection_count')

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for record in self:
            record.inspection_count = len(record.inspection_ids)

    def action_view_inspections(self):
        self.ensure_one()
        return {
            'name': 'Machine Inspections',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.inspection',
            'view_mode': 'list,form',
            'domain': [('machine_id', '=', self.id)],
            'context': {
                'default_machine_id': self.id,
                'default_category_id': self.category_id.id,
            },
        }

    def action_create_inspection(self):
        self.ensure_one()
        return {
            'name': 'New Inspection',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.inspection',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_machine_id': self.id,
                'default_customer_id': self.partner_id.id,
                'default_category_id': self.category_id.id,
            }
        }
