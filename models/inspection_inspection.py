from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
import base64
from io import BytesIO
import logging

_logger = logging.getLogger(__name__)

try:
    import qrcode
except ImportError:
    qrcode = None


class InspectionInspection(models.Model):
    _name = 'inspection.inspection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Inspection Sheet'
    _order = 'start_date desc, id desc'

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default='New')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    customer_id = fields.Many2one('res.partner', string="Customer", required=True)
    machine_id = fields.Many2one('inspection.machine', string="Machine", required=True)
    category_id = fields.Many2one(related='machine_id.category_id', string="Category", store=True)

    gantt_name = fields.Char(string="Gantt Label", compute='_compute_gantt_name', store=True)

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

    # Inspector Signature (Internal)
    inspector_name = fields.Char(string="Inspector Name")
    inspector_signature = fields.Binary(string="Inspector Signature")

    # Customer Signature (External)
    customer_signature = fields.Binary(string="Customer Signature", attachment=True)
    signed_date = fields.Datetime(string="Signed On")
    signed_by = fields.Char(string="Signed By")

    location_site = fields.Char(string="Location of Inspection")

    # -------------------------------------------------------------------------
    #  GPS Field
    # -------------------------------------------------------------------------
    gps_coordinates = fields.Char(
        string="GPS Location URL",
        help="Paste a Google Maps link (must contain 'google')"
    )

    doc_report = fields.Boolean(string="Previous Inspection Report", default=True)
    doc_maintenance = fields.Boolean(string="Maintenance Record", default=True)
    doc_load_chart = fields.Boolean(string="Load Chart", default=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('passed', 'Passed'),
        ('failed', 'Failed')
    ], string="Status", default='draft', copy=False, tracking=True)

    line_ids = fields.One2many('inspection.inspection.line', 'inspection_id', string="Checklist")

    qr_code_url = fields.Char(compute='_compute_qr_code_url', string="QR URL")
    qr_image = fields.Binary(string="QR Code Image", compute='_compute_qr_image')

    # Assigned Inspector
    inspector_id = fields.Many2one('res.users', string="Assigned Inspector", default=lambda self: self.env.user)

    # -------------------------------------------------------------------------
    # CONSTRAINT: SMART GOOGLE VALIDATION (Accepts App Short Links)
    # -------------------------------------------------------------------------
    @api.constrains('gps_coordinates')
    def _check_gps_coordinates(self):
        for rec in self:
            if rec.gps_coordinates:
                # 1. Clean the input
                url = rec.gps_coordinates.strip().lower()

                # 2. Check for "google" OR the short link format "goo.gl"
                # This accepts:
                # - https://maps.app.goo.gl/pD9cR... (Mobile App Share)
                # - http://googleusercontent.com/... (Desktop)
                # - https://www.google.com/maps/... (Standard)

                if "google" not in url and "goo.gl" not in url:
                    raise ValidationError("Invalid Link! Please enter a valid Google Maps URL.")

    # 3. Action to Open Map
    def action_open_map(self):
        self.ensure_one()
        url = self.gps_coordinates.strip() if self.gps_coordinates else "http://googleusercontent.com/maps.google.com/"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    @api.constrains('start_date', 'expire_date')
    def _check_dates(self):
        for record in self:
            if record.expire_date and record.start_date and record.expire_date < record.start_date:
                raise ValidationError("Error: The Expiration Date cannot be earlier than the Inspection Start Date!")

    @api.depends('machine_id', 'customer_id')
    def _compute_gantt_name(self):
        for record in self:
            machine = record.machine_id.name if record.machine_id else "N/A"
            customer = record.customer_id.name if record.customer_id else "No Customer"
            record.gantt_name = f"{machine} ({customer})"

    # -------------------------------------------------------------------------
    # DASHBOARD STATS
    # -------------------------------------------------------------------------
    @api.model
    def get_dashboard_stats(self):
        # 1. Calculate Basic KPIs
        total_insp = self.search_count([])
        passed = self.search_count([('status', '=', 'passed')])
        failed = self.search_count([('status', '=', 'failed')])

        Machine = self.env['inspection.machine']
        total_machines = Machine.search_count([])

        Category = self.env['inspection.category']
        total_categories = Category.search_count([])

        # 2. Status Chart Data
        if total_insp == 0:
            status_data = [0, 0, 0]
        else:
            draft = total_insp - passed - failed
            status_data = [passed, failed, draft]

        # 3. Machines by Category Chart
        machines_by_cat = Machine.read_group(domain=[], fields=['category_id'], groupby=['category_id'])
        cat_labels = []
        cat_data = []
        for group in machines_by_cat:
            category = group.get('category_id')
            count = group.get('category_id_count', 0)
            if category:
                cat_labels.append(category[1])
                cat_data.append(count)
            else:
                cat_labels.append('Uncategorized')
                cat_data.append(count)

        # 4. Recent Inspections List
        recent_inspections = self.search_read(
            domain=[],
            fields=['name', 'machine_id', 'status', 'start_date', 'signed_by', 'signed_date', 'customer_id',
                    'inspector_id'],
            limit=5,
            order='create_date desc'
        )
        for insp in recent_inspections:
            if insp['machine_id']:
                insp['machine_name'] = insp['machine_id'][1]
            if insp['customer_id']:
                insp['customer_name'] = insp['customer_id'][1]
            else:
                insp['customer_name'] = 'N/A'

            # Handling Inspector Name
            if insp['inspector_id']:
                insp['inspector_name'] = insp['inspector_id'][1]
            else:
                insp['inspector_name'] = 'Unassigned'

        # 5. Expiring Inspections List
        today = fields.Date.today()
        # Ensure 'relativedelta' is imported at the top of your file: from dateutil.relativedelta import relativedelta
        next_30_days = today + relativedelta(days=30)

        expiring_inspections = self.search_read(
            domain=[('status', '=', 'passed'), ('expire_date', '>=', today), ('expire_date', '<=', next_30_days)],
            fields=['name', 'machine_id', 'expire_date', 'customer_id'],
            limit=5,
            order='expire_date asc'
        )
        for exp in expiring_inspections:
            if exp['machine_id']:
                exp['machine_name'] = exp['machine_id'][1]
            if exp['customer_id']:
                exp['customer_name'] = exp['customer_id'][1]

        # 6. INSPECTOR TRACKING (Added Section)
        # ---------------------------------------------------------
        users = self.env['res.users'].sudo().search([('share', '=', False)])
        inspector_data = []

        for user in users:
            # Count Completed (Using 'inspector_id' to match your field name)
            done_count = self.search_count([
                ('inspector_id', '=', user.id),
                ('status', 'in', ['passed', 'failed'])
            ])

            # Find Next Task (Using 'start_date' to match your field name)
            next_task = self.search([
                ('inspector_id', '=', user.id),
                ('status', 'in', ['draft', 'pending'])
            ], order='start_date asc', limit=1)

            # Check if user has any activity
            has_activity = self.search_count([('inspector_id', '=', user.id)]) > 0

            if has_activity:
                inspector_data.append({
                    'id': user.id,
                    'name': user.name,
                    'done_count': done_count,
                    'next_date': next_task.start_date if next_task and next_task.start_date else False,
                    'next_machine': next_task.machine_id.name if next_task and next_task.machine_id else False,
                })
        # ---------------------------------------------------------

        return {
            'kpi': {
                'total_insp': total_insp,
                'passed': passed,
                'failed': failed,
                'total_machines': total_machines,
                'total_categories': total_categories
            },
            'charts': {
                'status': status_data,
                'machines_by_category': {'labels': cat_labels, 'data': cat_data}
            },
            'lists': {
                'recent': recent_inspections,
                'expiring': expiring_inspections
            },
            'inspectors': inspector_data  # <--- Included in return
        }

    @api.model
    def get_customer_dashboard_stats(self):
        Machine = self.env['inspection.machine']
        Inspection = self.env['inspection.inspection']
        Partner = self.env['res.partner']

        # 1. Existing Logic for Charts & KPIs
        machines_by_partner = Machine.read_group(
            domain=[('partner_id', '!=', False)], fields=['partner_id'], groupby=['partner_id'],
            orderby='partner_id_count desc'
        )
        market_share_labels = []
        market_share_data = []
        active_clients_count = len(machines_by_partner)
        largest_fleet_holder = {'id': False, 'name': 'None', 'count': 0}

        for index, group in enumerate(machines_by_partner):
            partner_name = group['partner_id'][1]
            partner_id = group['partner_id'][0]
            count = group['partner_id_count']
            if index < 5:
                market_share_labels.append(partner_name)
                market_share_data.append(count)
            if index == 0:
                largest_fleet_holder = {'id': partner_id, 'name': partner_name, 'count': count}

        # 2. Risk Watchlist
        failed_by_partner = Inspection.read_group(
            domain=[('status', '=', 'failed'), ('customer_id', '!=', False)], fields=['customer_id'],
            groupby=['customer_id'], orderby='customer_id_count desc', limit=5
        )
        risk_list = []
        for group in failed_by_partner:
            risk_list.append(
                {'id': group['customer_id'][0], 'name': group['customer_id'][1], 'count': group['customer_id_count']})

        # 3. UPDATED: Fetch MORE fields for the "Pro" Cards
        all_customers = Partner.search_read(
            domain=['|', ('machine_ids', '!=', False), ('customer_rank', '>', 0)],
            fields=['id', 'name', 'street', 'city', 'email', 'phone', 'mobile', 'machine_count', 'inspection_count'],
            order='name asc'
        )

        # Add risk flag
        risk_ids = [r['id'] for r in risk_list]
        for cust in all_customers:
            cust['is_risk'] = cust['id'] in risk_ids

        return {
            'kpi': {'active_clients': active_clients_count, 'largest_fleet': largest_fleet_holder},
            'charts': {'market_share': {'labels': market_share_labels, 'data': market_share_data}},
            'lists': {'risk_watchlist': risk_list, 'all_customers': all_customers}
        }

    # -------------------------------------------------------------------------
    # STANDARD METHODS
    # -------------------------------------------------------------------------

    @api.depends('name', 'machine_id')
    def _compute_qr_code_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            if rec.machine_id:
                rec.qr_code_url = f"{base_url}/machine/info/{rec.machine_id.id}"
            else:
                rec.qr_code_url = base_url

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

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('inspection.inspection') or 'New'
        return super(InspectionInspection, self).create(vals)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------

    # NEW: Map Button Action
    def action_open_map(self):
        self.ensure_one()
        # Clean the URL before opening
        url = self.gps_coordinates.strip() if self.gps_coordinates else "http://googleusercontent.com/maps.google.com/"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_pass(self):
        self.write({'status': 'passed'})
        try:
            report = self.env.ref('certification.action_report_certificate')
            pdf_content, _ = report._render_qweb_pdf(self.id)

            self.env['ir.attachment'].create({
                'name': f"Certificate - {self.name}.pdf",
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'inspection.inspection',
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            _logger.info(f"Certificate PDF generated successfully for inspection {self.name}")
        except Exception as e:
            _logger.error(f"Failed to generate certificate PDF for inspection {self.name}: {e}")
        return True

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

    @api.model
    def action_send_expiration_reminders(self):
        today = fields.Date.today()
        target_date = today + relativedelta(days=30)
        expiring_inspections = self.search([
            ('status', '=', 'passed'),
            ('expire_date', '=', target_date)
        ])
        template = self.env.ref('certification.mail_template_inspection_expiration', raise_if_not_found=False)
        if not template:
            return
        for inspection in expiring_inspections:
            if inspection.customer_id.email:
                template.send_mail(inspection.id, force_send=True)


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


# -------------------------------------------------------------------------
# CUSTOMER PORTAL EXTENSIONS (Docs, Invoices, Payment Status)
# -------------------------------------------------------------------------

class ResPartner(models.Model):
    _inherit = 'res.partner'

    inspection_document_ids = fields.One2many(
        'inspection.document', 'partner_id', string="Portal Documents"
    )

    unpaid_document_count = fields.Integer(
        string="Unpaid Docs",
        compute='_compute_unpaid_document_count'
    )

    @api.depends('inspection_document_ids.payment_status')
    def _compute_unpaid_document_count(self):
        for partner in self:
            count = self.env['inspection.document'].search_count([
                ('partner_id', '=', partner.id),
                ('payment_status', '!=', 'paid')
            ])
            partner.unpaid_document_count = count


class InspectionDocument(models.Model):
    _name = 'inspection.document'
    _description = 'Customer Portal Document'
    _order = 'upload_date desc'

    name = fields.Char(string="Description", required=True)
    file = fields.Binary(string="File", required=True, attachment=True)
    file_name = fields.Char(string="Filename")
    partner_id = fields.Many2one('res.partner', string="Customer")
    upload_date = fields.Date(string="Date", default=fields.Date.today)

    # Link to Invoice
    invoice_id = fields.Many2one('account.move', string="Linked Invoice",
                                 domain="[('partner_id', '=', partner_id), ('move_type', '=', 'out_invoice')]")

    # Payment Status (Computed & Editable)
    payment_status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid')
    ], string="Payment Status", compute='_compute_payment_status', store=True, readonly=False)

    @api.depends('invoice_id', 'invoice_id.payment_state')
    def _compute_payment_status(self):
        for doc in self:
            if doc.invoice_id:
                state = doc.invoice_id.payment_state
                if state in ('paid', 'in_payment'):
                    doc.payment_status = 'paid'
                elif state == 'partial':
                    doc.payment_status = 'partial'
                else:
                    doc.payment_status = 'unpaid'

    @api.model
    def create(self, vals):
        doc = super(InspectionDocument, self).create(vals)
        if doc.partner_id and doc.partner_id.email:
            try:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                doc_url = f"{base_url}/my/documents"

                subject = f"New Document Shared: {doc.name}"
                body_html = f"""
                    <div style="font-family: Arial, sans-serif; color: #333;">
                        <p>Hello <strong>{doc.partner_id.name}</strong>,</p>
                        <p>A new document has been shared with you in your portal.</p>
                        <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #00A09D; margin: 15px 0;">
                            <p style="margin: 0;"><strong>Document:</strong> {doc.name}</p>
                            <p style="margin: 5px 0 0 0;"><strong>Date:</strong> {doc.upload_date}</p>
                        </div>
                        <p>You can access and download this file by logging into your portal:</p>
                        <a href="{doc_url}" style="background-color: #00A09D; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Documents</a>
                        <p style="margin-top: 20px; font-size: 12px; color: #777;">Thank you,<br/>Inspection Team</p>
                    </div>
                """

                self.env['mail.mail'].create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': doc.partner_id.email,
                    'email_from': self.env.user.email_formatted or self.env.company.email,
                    'auto_delete': True,
                }).send()
            except Exception as e:
                _logger.error(f"Failed to send document upload email: {e}")
        return doc
