# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import base64
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class InspectionController(http.Controller):

    # 1. PUBLIC CERTIFICATE VIEW
    @http.route('/inspection/view/<int:inspection_id>', type='http', auth='public', website=True)
    def view_inspection_certificate(self, inspection_id, **kwargs):
        inspection = request.env['inspection.inspection'].sudo().browse(inspection_id)
        if not inspection.exists():
            return request.render('http_routing.404')
        return request.render('certification.public_inspection_view', {'inspection': inspection})

    # NEW: PUBLIC MACHINE INFO (No Login Required)
    @http.route('/machine/info/<int:machine_id>', type='http', auth='public', website=True)
    def view_public_machine(self, machine_id, **kwargs):
        _logger.info(f"Public user scanning QR for Machine ID: {machine_id}")

        # Use sudo() to allow public access to the record
        machine = request.env['inspection.machine'].sudo().browse(machine_id)

        if not machine.exists():
            return request.render('http_routing.404')

        # Render the new public template
        return request.render('certification.public_machine_info', {'machine': machine})

    # 2. DOWNLOAD QR CODE
    @http.route('/inspection/qr_download/<int:inspection_id>', type='http', auth='public', website=True)
    def download_qr_code(self, inspection_id, **kwargs):
        """Download QR code image for an inspection"""
        inspection = request.env['inspection.inspection'].sudo().browse(inspection_id)

        # Check if inspection exists
        if not inspection.exists():
            _logger.warning(f"Inspection {inspection_id} not found")
            return request.not_found()

        # Check if QR image exists
        if not inspection.qr_image:
            _logger.warning(f"QR image not found for inspection {inspection_id}")
            return request.not_found()

        try:
            # Decode base64 image
            image_content = base64.b64decode(inspection.qr_image)

            # Create safe filename
            safe_name = (inspection.name or str(inspection.id)).replace('/', '_').replace(' ', '_')
            filename = f'QR_{safe_name}.png'

            _logger.info(f"Downloading QR code for inspection {inspection_id}: {filename}")

            return request.make_response(
                image_content,
                headers=[
                    ('Content-Type', 'image/png'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                    ('Content-Length', len(image_content))
                ]
            )
        except Exception as e:
            _logger.error(f"Error downloading QR code for inspection {inspection_id}: {str(e)}")
            return request.not_found()

    # 3. DIGITAL SIGNATURE
    @http.route('/inspection/sign/<int:inspection_id>', type='http', auth='user', methods=['POST'], website=True)
    def sign_inspection(self, inspection_id, **kwargs):
        inspection = request.env['inspection.inspection'].sudo().browse(inspection_id)

        if inspection.customer_id != request.env.user.partner_id:
            return request.redirect('/my/machines')

        signature_data = kwargs.get('signature_data')
        signer_name = kwargs.get('signer_name')

        if signature_data:
            inspection.sudo().write({
                'customer_signature': signature_data,
                'signed_by': signer_name or request.env.user.name,
                'signed_date': datetime.now()
            })

        return request.redirect(f'/my/machines/{inspection.machine_id.id}?msg=signed')


class MachineCustomerPortal(CustomerPortal):

    # 1. HOME PAGE COUNTERS
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        # Add machine and inspection counts
        values['machine_count'] = request.env['inspection.machine'].sudo().search_count([
            ('partner_id', '=', partner.id)
        ])

        values['inspection_count'] = request.env['inspection.inspection'].sudo().search_count([
            ('customer_id', '=', partner.id)
        ])
        return values

    # 2. MY MACHINES LIST
    @http.route(['/my/machines', '/my/machines/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_machines(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Machine = request.env['inspection.machine'].sudo()
        domain = [('partner_id', '=', partner.id)]

        machine_count = Machine.search_count(domain)
        pager = portal_pager(url="/my/machines", total=machine_count, page=page, step=10)
        machines = Machine.search(domain, offset=pager['offset'], limit=10)

        values.update({
            'machines': machines,
            'page_name': 'machine',
            'pager': pager,
            'default_url': '/my/machines'
        })
        return request.render("certification.portal_my_machines", values)

    # 3. MACHINE DETAIL
    @http.route(['/my/machines/<int:machine_id>'], type='http', auth="user", website=True)
    def portal_my_machine_detail(self, machine_id, **kw):
        machine = request.env['inspection.machine'].sudo().browse(machine_id)

        # Security check
        if machine.partner_id != request.env.user.partner_id:
            return request.redirect('/my/machines')

        logs = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'inspection.machine'),
            ('res_id', '=', machine.id)
        ])

        return request.render("certification.portal_my_machine_detail", {
            'machine': machine,
            'page_name': 'machine',
            'logs': logs,
        })

    # 4. REQUEST INSPECTION (With Note & Email)
    @http.route('/my/machines/<int:machine_id>/request_inspection', type='http', auth="user", methods=['POST'],
                website=True)
    def request_inspection(self, machine_id, **kwargs):
        machine = request.env['inspection.machine'].sudo().browse(machine_id)

        # Security check
        if machine.partner_id != request.env.user.partner_id:
            return request.redirect('/my/machines')

        # Get Note
        customer_note = kwargs.get('request_note')

        # A. Create Record
        new_inspection = request.env['inspection.inspection'].sudo().create({
            'machine_id': machine.id,
            'customer_id': machine.partner_id.id,
            'status': 'draft',
            'inspection_type': 'thorough',
            'name': 'REQ: ' + machine.name,
            'company_id': request.env.company.id,
        })

        # B. Post Note to Chatter
        if customer_note:
            new_inspection.message_post(
                body=f"<strong>Customer Note:</strong> {customer_note}",
                subtype_xmlid="mail.mt_note",
                author_id=machine.partner_id.id
            )

        # C. Send Email
        template = request.env.ref('certification.email_template_inspection_request', raise_if_not_found=False)
        if template:
            template.sudo().send_mail(new_inspection.id, force_send=True)

        return request.redirect(f'/my/machines/{machine_id}?msg=inspection_requested')

    # 5. UPLOAD LOG
    @http.route('/my/machines/<int:machine_id>/upload_log', type='http', auth="user", methods=['POST'], website=True)
    def upload_maintenance_log(self, machine_id, **kwargs):
        machine = request.env['inspection.machine'].sudo().browse(machine_id)

        # Security check
        if machine.partner_id != request.env.user.partner_id:
            return request.redirect('/my/machines')

        file = kwargs.get('attachment')
        if file:
            request.env['ir.attachment'].sudo().create({
                'name': file.filename,
                'type': 'binary',
                'datas': base64.b64encode(file.read()),
                'res_model': 'inspection.machine',
                'res_id': machine.id,
                'mimetype': file.content_type
            })

        return request.redirect(f'/my/machines/{machine_id}?msg=log_uploaded')

    # 6. MY INSPECTIONS LIST
    @http.route(['/my/inspections', '/my/inspections/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_inspections(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Inspection = request.env['inspection.inspection'].sudo()
        domain = [('customer_id', '=', partner.id)]

        searchbar_sortings = {
            'date': {'label': 'Newest', 'order': 'start_date desc'},
            'status': {'label': 'Status', 'order': 'status'},
        }
        if not sortby: sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        count = Inspection.search_count(domain)
        pager = portal_pager(url="/my/inspections", url_args={'sortby': sortby}, total=count, page=page, step=15)
        inspections = Inspection.search(domain, order=order, limit=15, offset=pager['offset'])

        values.update({
            'inspections': inspections,
            'page_name': 'inspection',
            'pager': pager,
            'default_url': '/my/inspections',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("certification.portal_my_inspections", values)
