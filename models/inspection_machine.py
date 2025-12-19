from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import date


class InspectionMachine(models.Model):
    _name = 'inspection.machine'
    _description = 'Machine or Equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Machine Name/Description", required=True)
    serial_number = fields.Char(string="Serial Number")
    model_no = fields.Char(string="Model Number")
    swl = fields.Char(string="S.W.L. (Safe Working Load)")
    build_year = fields.Char(string="Date of Manufacture")
    manufacturer = fields.Char(string="Manufacturer")
    owner_id_no = fields.Char(string="Owner ID / Fleet No.")

    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    category_id = fields.Many2one('inspection.category', string="Category", required=True)

    custom_question_ids = fields.One2many('inspection.question', 'machine_id', string="Machine Specific Questions")
    inspection_ids = fields.One2many('inspection.inspection', 'machine_id', string="Inspections")
    inspection_count = fields.Integer(compute='_compute_inspection_count')

    # --- SUBSCRIPTION & RECURRING FIELDS ---
    recurring_inspection = fields.Boolean(string="Active Subscription",
                                          help="If checked, system will auto-generate inspections.")
    inspection_interval = fields.Selection([
        ('1', 'Monthly'),
        ('3', 'Quarterly (Every 3 Months)'),
        ('6', 'Semi-Annually (Every 6 Months)'),
        ('12', 'Annually (Every Year)')
    ], string="Frequency", default='12')

    next_inspection_date = fields.Date(string="Next Inspection Date", default=fields.Date.today)

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
            'context': {'default_machine_id': self.id}
        }

    def action_create_inspection(self):
        self.ensure_one()
        return {
            'name': 'New Inspection',
            'type': 'ir.actions.act_window',
            'res_model': 'inspection.inspection',
            'view_mode': 'form',
            'context': {'default_machine_id': self.id, 'default_customer_id': self.partner_id.id}
        }

    # --- CRON JOB: GENERATE RECURRING INSPECTIONS ---
    @api.model
    def _cron_generate_recurring_inspections(self):
        """ This method is called by the System Scheduler every day """
        today = fields.Date.today()

        # 1. Find machines that are Active AND due for inspection
        machines_due = self.search([
            ('recurring_inspection', '=', True),
            ('next_inspection_date', '<=', today)
        ])

        for machine in machines_due:
            # 2. Create the Draft Inspection
            self.env['inspection.inspection'].create({
                'machine_id': machine.id,
                'customer_id': machine.partner_id.id,
                'status': 'draft',
                'name': f"Auto-Renewal: {machine.name} ({today})",
                'start_date': today,
                'inspection_type': 'thorough',
                'company_id': self.env.company.id,  # Ensure company set if using multi-company
            })

            # 3. Calculate next date based on interval
            months_to_add = int(machine.inspection_interval)
            new_date = machine.next_inspection_date + relativedelta(months=months_to_add)
            machine.write({'next_inspection_date': new_date})

            # Log in chatter
            machine.message_post(body=f"System auto-generated inspection for {today}. Next run: {new_date}")

    # --- DASHBOARD DATA FETCHER ---
    @api.model
    def get_machine_dashboard_stats(self):
        today = fields.Date.today()

        # 1. KPIs
        total_machines = self.search_count([])

        compliant_ids = self.env['inspection.inspection'].search([
            ('status', '=', 'passed'),
            ('expire_date', '>=', today)
        ]).mapped('machine_id.id')

        compliant_count = len(set(compliant_ids))
        non_compliant_count = total_machines - compliant_count

        manufacturers = self.read_group([], ['manufacturer'], ['manufacturer'])
        manufacturer_count = len(manufacturers)

        # 2. Charts
        by_manufacturer = self.read_group(
            domain=[('manufacturer', '!=', False)],
            fields=['manufacturer'],
            groupby=['manufacturer'],
            orderby='manufacturer_count desc',
            limit=10
        )
        man_labels = [x['manufacturer'] for x in by_manufacturer]
        man_data = [x['manufacturer_count'] for x in by_manufacturer]

        by_category = self.read_group(
            domain=[],
            fields=['category_id'],
            groupby=['category_id']
        )
        cat_labels = [x['category_id'][1] for x in by_category if x['category_id']]
        cat_data = [x['category_id_count'] for x in by_category if x['category_id']]

        # 3. Non-Compliant List
        non_compliant_recs = self.search_read(
            domain=[('id', 'not in', compliant_ids)],
            fields=['name', 'serial_number', 'partner_id', 'manufacturer'],
            limit=20
        )
        nc_list = []
        for rec in non_compliant_recs:
            nc_list.append({
                'id': rec['id'],
                'name': rec['name'],
                'serial': rec['serial_number'] or 'N/A',
                'partner': rec['partner_id'][1] if rec['partner_id'] else 'Unknown',
                'manufacturer': rec['manufacturer'] or '-'
            })

        return {
            'kpi': {
                'total': total_machines,
                'compliant': compliant_count,
                'non_compliant': non_compliant_count,
                'manufacturers': manufacturer_count
            },
            'charts': {
                'manufacturer': {'labels': man_labels, 'data': man_data},
                'category': {'labels': cat_labels, 'data': cat_data}
            },
            'lists': {'non_compliant': nc_list}
        }
