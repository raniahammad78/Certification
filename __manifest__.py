{
    'name': 'Certification',
    'version': '2.0',
    'category': 'Services',
    'sequence': 4,
    'summary': 'Manage machine inspections, checklists, and certificates',
    'depends': ['base', 'web', 'contacts', 'website','mail','portal'],
    'data': [
        "data/inspection_cron_data.xml",
        "data/mail_template_data.xml",
        "views/res_partner_views.xml",
        "views/inspection_portal_templates.xml",
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'reports/report_certificate_template.xml',
        'reports/inspection_report.xml',
        'views/inspection_category_views.xml',
        'views/inspection_machine_views.xml',
        'views/inspection_inspection_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Main Dashboard
            'certification/static/src/dashboard/dashboard.xml',
            'certification/static/src/dashboard/dashboard.js',
            'certification/static/src/dashboard/dashboard.css',

            # Machine Dashboard
            'certification/static/src/dashboard/machine_dashboard.xml',
            'certification/static/src/dashboard/machine_dashboard.js',

            # NEW: Customer Dashboard
            'certification/static/src/dashboard/customer_dashboard.xml',
            'certification/static/src/dashboard/customer_dashboard.js',
        ],
    },
    'application': True,
    'installable': True,
}
