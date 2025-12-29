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

    # 2. PUBLIC MACHINE INFO
    @http.route('/machine/info/<int:machine_id>', type='http', auth='public', website=True)
    def view_public_machine(self, machine_id, **kwargs):
        machine = request.env['inspection.machine'].sudo().browse(machine_id)
        if not machine.exists():
            return request.render('http_routing.404')
        return request.render('certification.public_machine_info', {'machine': machine})

    # 3. DOWNLOAD QR CODE
    @http.route('/inspection/qr_download/<int:inspection_id>', type='http', auth='user', website=True)
    def download_qr_code(self, inspection_id, **kwargs):
        inspection = request.env['inspection.inspection'].sudo().browse(inspection_id)

        if not inspection.exists() or not inspection.qr_image:
            return request.not_found()

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        is_customer = inspection.customer_id == user.partner_id

        if not (is_internal or is_customer):
            return request.not_found()

        image_content = base64.b64decode(inspection.qr_image)
        safe_name = (inspection.name or str(inspection.id)).replace('/', '_')
        return request.make_response(
            image_content,
            headers=[
                ('Content-Type', 'image/png'),
                ('Content-Disposition', f'attachment; filename=QR_{safe_name}.png')
            ]
        )

    # 4. DIGITAL SIGNATURE
    @http.route('/inspection/sign/<int:inspection_id>', type='json', auth='user', website=True)
    def sign_inspection(self, inspection_id, name=None, signature=None, access_token=None, **kwargs):
        inspection = request.env['inspection.inspection'].sudo().browse(inspection_id)

        user = request.env.user
        if inspection.customer_id != user.partner_id and not user.has_group('base.group_user'):
            return {'error': _('You are not authorized to sign this document.')}

        if signature:
            if ',' in signature:
                signature = signature.split(',')[1]

            inspection.sudo().write({
                'customer_signature': signature,
                'signed_by': name or user.name,
                'signed_date': datetime.now()
            })

        return {
            'force_refresh': True,
            'redirect_url': f'/inspection/view/{inspection.id}',
        }


class MachineCustomerPortal(CustomerPortal):

    # 1. HOME PAGE COUNTERS
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'machine_count' in counters:
            values['machine_count'] = request.env['inspection.machine'].search_count([
                ('partner_id', '=', partner.id)
            ])
        if 'inspection_count' in counters:
            values['inspection_count'] = request.env['inspection.inspection'].search_count([
                ('customer_id', '=', partner.id)
            ])
        if 'document_count' in counters:
            values['document_count'] = len(partner.inspection_document_ids)

        return values

    # 2. MY MACHINES LIST
    @http.route(['/my/machines', '/my/machines/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_machines(self, page=1, sortby=None, search=None, search_in='all', **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Machine = request.env['inspection.machine']

        domain = [('partner_id', '=', partner.id)]

        searchbar_inputs = {
            'all': {'input': 'all', 'label': _('Search in All')},
            'name': {'input': 'name', 'label': _('Name')},
            'serial': {'input': 'serial', 'label': _('Serial Number')},
            'model': {'input': 'model', 'label': _('Model Number')},
        }

        if search and search_in:
            search = search.strip()
            if search_in == 'all':
                domain += ['|', '|', ('name', 'ilike', search), ('serial_number', 'ilike', search),
                           ('model_no', 'ilike', search)]
            elif search_in == 'name':
                domain += [('name', 'ilike', search)]
            elif search_in == 'serial':
                domain += [('serial_number', 'ilike', search)]
            elif search_in == 'model':
                domain += [('model_no', 'ilike', search)]

        machine_count = Machine.search_count(domain)
        pager = portal_pager(
            url="/my/machines",
            url_args={'sortby': sortby, 'search': search, 'search_in': search_in},
            total=machine_count,
            page=page,
            step=10
        )
        machines = Machine.search(domain, offset=pager['offset'], limit=10)

        values.update({
            'machines': machines,
            'page_name': 'machine',
            'pager': pager,
            'default_url': '/my/machines',
            'searchbar_inputs': searchbar_inputs,
            'search': search,
            'search_in': search_in
        })
        return request.render("certification.portal_my_machines", values)

    # 3. MACHINE DETAIL
    @http.route(['/my/machines/<int:machine_id>'], type='http', auth="user", website=True)
    def portal_my_machine_detail(self, machine_id, **kw):
        machine = request.env['inspection.machine'].browse(machine_id)
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

    # 4. REQUEST INSPECTION
    @http.route('/my/machines/<int:machine_id>/request_inspection', type='http', auth="user", methods=['POST'],
                website=True)
    def request_inspection(self, machine_id, **kwargs):
        machine = request.env['inspection.machine'].browse(machine_id)
        if machine.partner_id != request.env.user.partner_id:
            return request.redirect('/my/machines')

        customer_note = kwargs.get('request_note')

        new_inspection = request.env['inspection.inspection'].sudo().create({
            'machine_id': machine.id,
            'customer_id': machine.partner_id.id,
            'status': 'draft',
            'inspection_type': 'thorough',
            'name': 'REQ: ' + machine.name,
            'company_id': request.env.company.id,
        })

        if customer_note:
            new_inspection.message_post(
                body=f"<strong>Customer Note:</strong> {customer_note}",
                subtype_xmlid="mail.mt_note",
                author_id=machine.partner_id.id
            )

        template = request.env.ref('certification.email_template_inspection_request', raise_if_not_found=False)
        if template:
            template.sudo().send_mail(new_inspection.id, force_send=True)

        return request.redirect(f'/my/machines/{machine_id}?msg=inspection_requested')

    # 5. UPLOAD LOG
    @http.route('/my/machines/<int:machine_id>/upload_log', type='http', auth="user", methods=['POST'], website=True)
    def upload_maintenance_log(self, machine_id, **kwargs):
        machine = request.env['inspection.machine'].browse(machine_id)
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

    # 6. MY INSPECTIONS LIST (UPDATED WITH SEARCH)
    @http.route(['/my/inspections', '/my/inspections/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_inspections(self, page=1, sortby=None, search=None, search_in='all', **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Inspection = request.env['inspection.inspection']
        domain = [('customer_id', '=', partner.id)]

        searchbar_sortings = {
            'date': {'label': 'Newest', 'order': 'start_date desc'},
            'status': {'label': 'Status', 'order': 'status'},
        }

        # --- A. SEARCH INPUTS DEFINITION ---
        searchbar_inputs = {
            'all': {'input': 'all', 'label': _('Search in All')},
            'ref': {'input': 'ref', 'label': _('Reference')},
            'machine': {'input': 'machine', 'label': _('Machine Name')},
            'serial': {'input': 'serial', 'label': _('Serial Number')},
            'status': {'input': 'status', 'label': _('Status')},
        }

        # --- B. APPLY SEARCH LOGIC ---
        if search and search_in:
            search = search.strip()
            if search_in == 'all':
                domain += ['|', '|', '|',
                           ('name', 'ilike', search),
                           ('machine_id.name', 'ilike', search),
                           ('machine_id.serial_number', 'ilike', search),
                           ('status', 'ilike', search)]
            elif search_in == 'ref':
                domain += [('name', 'ilike', search)]
            elif search_in == 'machine':
                domain += [('machine_id.name', 'ilike', search)]
            elif search_in == 'serial':
                domain += [('machine_id.serial_number', 'ilike', search)]
            elif search_in == 'status':
                domain += [('status', 'ilike', search)]

        if not sortby: sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        count = Inspection.search_count(domain)
        pager = portal_pager(
            url="/my/inspections",
            url_args={'sortby': sortby, 'search': search, 'search_in': search_in},
            total=count,
            page=page,
            step=15
        )
        inspections = Inspection.search(domain, order=order, limit=15, offset=pager['offset'])

        values.update({
            'inspections': inspections,
            'page_name': 'inspection',
            'pager': pager,
            'default_url': '/my/inspections',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_inputs': searchbar_inputs,
            'sortby': sortby,
            'search': search,
            'search_in': search_in
        })
        return request.render("certification.portal_my_inspections", values)

    # 7. PORTAL DOCUMENTS LIST
    @http.route(['/my/documents', '/my/documents/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_documents(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        documents = partner.inspection_document_ids
        pager = portal_pager(url="/my/documents", total=len(documents), page=page, step=15)
        docs_paged = documents[pager['offset']:pager['offset'] + 15]

        values.update({
            'documents': docs_paged,
            'page_name': 'document',
            'pager': pager,
            'default_url': '/my/documents',
        })
        return request.render("certification.portal_my_documents", values)

    # 8. DOWNLOAD DOCUMENT
    @http.route('/my/documents/download/<int:doc_id>', type='http', auth="user", website=True)
    def download_portal_document(self, doc_id, **kw):
        document = request.env['inspection.document'].sudo().browse(doc_id)
        if document.partner_id != request.env.user.partner_id:
            return request.not_found()
        return request.make_response(
            base64.b64decode(document.file),
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename={document.file_name}')
            ]
        )
