from odoo import models, fields, api


class InspectionCategory(models.Model):
    _name = 'inspection.category'
    _description = 'Inspection Category'

    name = fields.Char(string="Category Name", required=True)
    description = fields.Text(string="Description")

    # CHANGED: 'Text' -> 'Char' allows Grouping and fixes "False" in Kanban
    standard = fields.Char(string="Standard")

    # Required for Kanban Color Picker
    color = fields.Integer(string='Color Index')

    question_ids = fields.One2many('inspection.question', 'category_id', string="Standard Checklist")
    inspection_ids = fields.One2many('inspection.inspection', 'category_id', string="Inspections")

    #  Link to machines for Smart Button
    machine_ids = fields.One2many('inspection.machine', 'category_id', string="Machines")

    inspection_count = fields.Integer(string="Inspection Count", compute='_compute_counts')
    machine_count = fields.Integer(string="Machine Count", compute='_compute_counts')

    @api.depends('inspection_ids', 'machine_ids')
    def _compute_counts(self):
        for record in self:
            record.inspection_count = len(record.inspection_ids)
            record.machine_count = len(record.machine_ids)

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

    def action_view_machines(self):
        self.ensure_one()
        return {
            'name': 'Machines',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.machine',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }

    @api.model
    def create(self, vals):
        res = super(InspectionCategory, self).create(vals)
        # Only populate if questions are not already provided
        if not res.question_ids:
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
    sequence = fields.Integer(string="Sequence")

    # Default Value Checkboxes
    is_accepted = fields.Boolean(string="A")
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
