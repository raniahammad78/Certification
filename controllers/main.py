from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import base64


class InspectionController(http.Controller):

    # 1. Public View (Scan QR)
    @http.route('/inspection/view/<int:inspection_id>', type='http', auth='public', website=True)
    def view_inspection_certificate(self, inspection_id, **kwargs):
        inspection = request.env['inspection.inspection'].sudo().browse(inspection_id)
        if not inspection.exists():
            return request.render('http_routing.404')
        return request.render('certification.public_inspection_view', {'inspection': inspection})

    # 2. NEW: Download QR Code (Portal User)
    @http.route('/inspection/qr_download/<int:inspection_id>', type='http', auth='user')
    def download_qr_code(self, inspection_id, **kwargs):
        inspection = request.env['inspection.inspection'].browse(inspection_id)

        # Check if record and image exist
        if not inspection.exists() or not inspection.qr_image:
            return request.not_found()

        # Decode the binary image
        image_content = base64.b64decode(inspection.qr_image)

        # Create a safe filename (replace / with _ to avoid errors)
        safe_name = inspection.name.replace('/', '_') if inspection.name else str(inspection.id)

        # Return as a downloadable file
        return request.make_response(
            image_content,
            headers=[
                ('Content-Type', 'image/png'),
                ('Content-Disposition', f'attachment; filename=QR_{safe_name}.png'),
            ]
        )


class MachineCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'machine_count' in counters:
            partner = request.env.user.partner_id
            values['machine_count'] = request.env['inspection.machine'].search_count([
                ('partner_id', '=', partner.id)
            ])
        return values

    @http.route(['/my/machines', '/my/machines/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_machines(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Machine = request.env['inspection.machine']

        domain = [('partner_id', '=', partner.id)]

        machine_count = Machine.search_count(domain)
        pager = portal_pager(
            url="/my/machines",
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
        })
        return request.render("certification.portal_my_machines", values)

    @http.route(['/my/machines/<int:machine_id>'], type='http', auth="user", website=True)
    def portal_my_machine_detail(self, machine_id, **kw):
        machine = request.env['inspection.machine'].browse(machine_id)
        if machine.partner_id != request.env.user.partner_id:
            return request.redirect('/my/machines')

        return request.render("certification.portal_my_machine_detail", {
            'machine': machine,
            'page_name': 'machine',
        })
