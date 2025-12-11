from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
import base64
from io import BytesIO

try:
    import qrcode
except ImportError:
    qrcode = None


class InspectionInspection(models.Model):
    _name = 'inspection.inspection'
    _description = 'Inspection Sheet'
    _order = 'start_date desc, id desc'

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default='New')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    customer_id = fields.Many2one('res.partner', string="Customer", required=True)
    machine_id = fields.Many2one('inspection.machine', string="Machine", required=True)
    category_id = fields.Many2one(related='machine_id.category_id', string="Category", store=True)

    start_date = fields.Date(string="Date of Inspection", default=fields.Date.today, required=True)
    expire_date = fields.Date(string="Next Due Date")

    last_inspection_date = fields.Date(string="Date of Last Inspection")
    inspection_type = fields.Selection([
        ('thorough', 'Thorough Examination'),
        ('visual', 'Visual Inspection'),
        ('6_month', '6 Monthly Inspection'),
        ('12_month', '12 Monthly Inspection'),
        ('initial', 'Initial Inspection')
    ], string="Type of Examination", default='thorough')

    inspector_name = fields.Char(string="Inspector Name")
    inspector_signature = fields.Binary(string="Inspector Signature")

    location_site = fields.Char(string="Location of Inspection")

    # Documents Reviewed
    doc_report = fields.Boolean(string="Previous Inspection Report", default=True)
    doc_maintenance = fields.Boolean(string="Maintenance Record", default=True)
    doc_load_chart = fields.Boolean(string="Load Chart", default=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('passed', 'Passed'),
        ('failed', 'Failed')
    ], string="Status", default='draft', copy=False)

    line_ids = fields.One2many('inspection.inspection.line', 'inspection_id', string="Checklist")

    qr_code_url = fields.Char(compute='_compute_qr_code_url', string="QR URL")
    qr_image = fields.Binary(string="QR Code Image", compute='_compute_qr_image')

    @api.depends('qr_code_url')
    def _compute_qr_image(self):
        for rec in self:
            if qrcode and rec.qr_code_url:
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
                qr.add_data(rec.qr_code_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                rec.qr_image = base64.b64encode(buffer.getvalue())
            else:
                rec.qr_image = False

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        if self.machine_id and self.machine_id.partner_id != self.customer_id:
            self.machine_id = False
            self.line_ids = [(5, 0, 0)]
        if self.customer_id and not self.location_site:
            self.location_site = self.customer_id.city

    @api.onchange('machine_id')
    def _onchange_machine_id(self):
        if self.machine_id:
            if self.machine_id.partner_id:
                self.customer_id = self.machine_id.partner_id

            # Auto-fill last inspection date if exists
            last_insp = self.search(
                [('machine_id', '=', self.machine_id.id), ('status', '=', 'passed'), ('id', '!=', self._origin.id)],
                limit=1, order='start_date desc')
            if last_insp:
                self.last_inspection_date = last_insp.start_date

            category_questions = self.machine_id.category_id.question_ids
            machine_questions = self.machine_id.custom_question_ids
            all_questions = category_questions + machine_questions

            new_lines = []
            for q in all_questions:
                new_lines.append((0, 0, {
                    'section': q.section,
                    'serial_no': q.serial_no,
                    'name': q.name,
                    'is_accepted': q.is_accepted,
                    'is_rejected': q.is_rejected,
                    'is_na': q.is_na,
                }))
            self.line_ids = [(5, 0, 0)] + new_lines

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date:
            self.expire_date = self.start_date + relativedelta(months=6)

    @api.depends('name')
    def _compute_qr_code_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.qr_code_url = f"{base_url}/inspection/view/{rec.id}" if rec.id else base_url

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('inspection.inspection') or 'New'
        return super(InspectionInspection, self).create(vals)

    def action_pass(self):
        self.write({'status': 'passed'})

    def action_fail(self):
        self.write({'status': 'failed'})

    def action_reset_draft(self):
        self.write({'status': 'draft'})

    def action_download_qr(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/inspection/qr_download/{self.id}',
            'target': 'self',
        }


class InspectionInspectionLine(models.Model):
    _name = 'inspection.inspection.line'
    _description = 'Inspection Question'
    _order = 'id'

    inspection_id = fields.Many2one('inspection.inspection', string="Inspection", ondelete='cascade')

    section = fields.Char(string="Section")
    serial_no = fields.Char(string="No")
    name = fields.Char(string="Examination Item", required=True)

    is_accepted = fields.Boolean(string="A")
    is_rejected = fields.Boolean(string="R")
    is_na = fields.Boolean(string="N/A")

    comment = fields.Text(string="Remarks")
    recommendation = fields.Text(string="Recommendations")
    image_ids = fields.One2many('inspection.inspection.image', 'line_id', string="Evidence Photos")

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


class InspectionInspectionImage(models.Model):
    _name = 'inspection.inspection.image'
    _description = 'Inspection Evidence Photo'
    line_id = fields.Many2one('inspection.inspection.line', string="Question Line", ondelete='cascade')
    name = fields.Char(string="Name")
    image = fields.Image(string="Photo", max_width=1024, max_height=1024)
    description = fields.Char(string="Description")
