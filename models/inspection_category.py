from odoo import models, fields, api


class InspectionCategory(models.Model):
    _name = 'inspection.category'
    _description = 'Inspection Category'

    name = fields.Char(string="Category Name", required=True)
    description = fields.Text(string="Description")

    standard = fields.Text(string="Standard")

    question_ids = fields.One2many('inspection.question', 'category_id', string="Standard Checklist")
    inspection_ids = fields.One2many('inspection.inspection', 'category_id', string="Inspections")
    inspection_count = fields.Integer(string="Inspection Count", compute='_compute_inspection_count')

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for record in self:
            record.inspection_count = len(record.inspection_ids)

    def action_view_inspections(self):
        self.ensure_one()
        return {
            'name': 'Inspections',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.inspection',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }

    @api.model
    def create(self, vals):
        res = super(InspectionCategory, self).create(vals)
        res._populate_standard_questions()
        return res

    def _populate_standard_questions(self):
        # Format: (Section, Number, Question Text)
        raw_data = [
            ("STRUCTURE", "01", "Welds"),
            ("STRUCTURE", "02", "Sidewalls/cracks"),
            ("STRUCTURE", "03", "Handrails"),
            ("STRUCTURE", "04", "Basket door lock /latch"),
            ("BRAKES", "05", "Man lift control valves"),
            ("BRAKES", "06", "Hoses (condition and leaks)"),
            ("BRAKES", "07", "System oil leaks"),
            ("BRAKES", "08", "Line fittings/valves"),
            ("ELECTRICAL", "09", "Instrument Panel"),
            ("ELECTRICAL", "10", "Wiring"),
            ("ELECTRICAL", "11", "Lights/Indicators/Hazard"),
            ("ELECTRICAL", "12", "Battery"),
            ("SAFETY DEVICES", "13", "Load Limiter"),
            ("SAFETY DEVICES", "14", "Warning Audible"),
            ("SAFETY DEVICES", "15", "Emergency Button"),
            ("SAFETY DEVICES", "16", "Limit Switchs"),
            ("SCISSOR", "17", "Operation"),
            ("SCISSOR", "18", "Operation (raise/lower)"),
            ("SCISSOR", "19", "Lift cylinder pins and bushings"),
            ("SCISSOR", "20", "Scissor Structure"),
            ("GENERAL", "21", "All functions (operation)"),
            ("GENERAL", "22", "All panels (superstructure)"),
            ("GENERAL", "23", "Platform handrails"),
            ("GENERAL", "24", "Platform door Lock / Latch"),
        ]

        lines = []
        for section, no, text in raw_data:
            lines.append({
                'category_id': self.id,
                'section': section,
                'serial_no': no,
                'name': text,
                'is_accepted': True,
                'sequence': int(no) * 10
            })
        if lines:
            self.env['inspection.question'].create(lines)


class InspectionQuestion(models.Model):
    _name = 'inspection.question'
    _description = 'Inspection Question Template'
    _order = 'sequence, id'

    category_id = fields.Many2one('inspection.category', string="Category")
    machine_id = fields.Many2one('inspection.machine', string="Machine")

    section = fields.Char(string="Section")
    serial_no = fields.Char(string="No")
    name = fields.Char(string="Examination Item", required=True)
    sequence = fields.Integer(string="Sequence", default=10)

    # Default Value Checkboxes
    is_accepted = fields.Boolean(string="A", default=True)
    is_rejected = fields.Boolean(string="R")
    is_na = fields.Boolean(string="N/A")

    @api.onchange('is_accepted')
    def _onchange_accepted(self):
        if self.is_accepted:
            self.is_rejected = False
            self.is_na = False

    @api.onchange('is_rejected')
    def _onchange_rejected(self):
        if self.is_rejected:
            self.is_accepted = False
            self.is_na = False

    @api.onchange('is_na')
    def _onchange_na(self):
        if self.is_na:
            self.is_accepted = False
            self.is_rejected = False
