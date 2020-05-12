import pandas as pd
from odoo import fields, models,api


class Salesforecast(models.Model):
    """Salesforecast Master model """
    _name = 'forecast.salesforecast'
    _description = 'Salesforecast model'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def list_consumption(self):
        list_bom_items = []
        list_items=[]
        list_grouped=[]
        list_bom_items.append((5, 0, 0))
        for re in self.salesforecast_product:
            bomlist = self.env['mrp.bom.line'].search([
                ('bom_id', '=', re.bom_id.id)])
            for bo in bomlist:
                obje = {
                    'item_id': bo.product_id.id,
                    'product_id': re.product_id.id,
                    'item_qty': bo.product_qty * re.product_qty,
                    'item_available': bo.product_id.qty_available,
                    'item_required': 1}
                list_bom_items.append((0, 0, obje))
                list_items.append(obje)

        data=pd.DataFrame(list_items)
        grpd=data.groupby('item_id', as_index=False)['item_qty'].sum()
        list_grouped=grpd.to_dict('r')
        self.salesforecast_items = list_bom_items
        lst=[]
        lst.append((5, 0, 0))

        for re in list_grouped:
            lst.append((0,0,re))
        self.salesforecast_items_grouped=lst



    @api.model
    def _get_default_picking_type(self):
        company_id = self.env.context.get('default_company_id', self.env.company.id)
        return self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('warehouse_id.company_id', '=', company_id),
        ], limit=1).id

    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        domain="[('code', '=', 'mrp_operation'), ('company_id', '=', company_id)]",
        default=_get_default_picking_type, required=True, check_company=True)
    picking_ids = fields.Many2many('stock.picking', compute='_compute_picking_ids',
                                   string='Picking associated to this manufacturing order')
    company_id = fields.Many2one(
        'res.company', 'Company', default=lambda self: self.env.company,
        index=True, required=True)

    name = fields.Char(
        'Salesforecast no', copy=False, readonly=True)
    salesforecast_name = fields.Char(
        'Salesforecast ref')
    date_planned_start = fields.Datetime(
        'Forecast starting Date', copy=False, default=fields.Datetime.now,
        help="Date at which you plan to start the production.", required=True, store=True)
    date_planned_finished = fields.Datetime(
        'Forecast Ending Date',
        default=fields.Datetime.now,
        help="Date at which you plan to finish the production.",
        copy=False, store=True)
    post_visible = fields.Boolean(
        'Allowed to Post Inventory', compute='_compute_post_visible',
        help='Technical field to check when we can post')
    user_id = fields.Many2one(
        'res.users', 'Responsible', default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', 'Company', default=lambda self: self.env.company,
        index=True, required=True)
    salesforecast_product = fields.One2many('forecast.salesforecastproducts', 'salesforecast_id', 'Salesforecast Products')
    salesforecast_items = fields.One2many('forecast.salesforecastproductsitems', 'salesforecast_id', 'Salesforecast Items')
    salesforecast_items_grouped = fields.One2many('forecast.salesforecastitemsgrouped', 'salesforecast_id', 'Ingredients summary')



class SalesforecastProducts(models.Model):
    """ List of salesforecast products """
    _name = 'forecast.salesforecastproducts'
    _description = 'Salesforecast Products'


    @api.onchange('product_id')
    def onchange_product_id(self):
        """ Finds UoM of changed product. """
        if not self.product_id:
            self.bom_id = False
        else:
            bom = self.env['mrp.bom']._bom_find(product=self.product_id,
                                                picking_type=self.salesforecast_id.picking_type_id,
                                                company_id=self.salesforecast_id.picking_type_id.company_id.id,
                                                bom_type='normal')
            if bom:
                self.bom_id = bom.id
                self.product_qty = self.bom_id.product_qty
                self.product_uom_id = self.bom_id.product_uom_id.id
            else:
                self.bom_id = False
                self.product_uom_id = self.product_id.uom_id.id
            return {'domain': {'product_uom_id': [('category_id', '=', self.product_id.uom_id.category_id.id)]}}

    salesforecast_id = fields.Many2one(
        'forecast.salesforecast', 'Salesforecast', store=True)
    product_id = fields.Many2one(
        'product.product', 'Product Name', store=True)

    product_qty = fields.Float(
        'Quantity Forecasted',
        default=1.0, digits='Product Unit of Measure',
        readonly=False, required=True, tracking=True)
    product_batch_size = fields.Float(
        'Batch Size',
        default=1.0, digits='Product Unit of Measure',
        required=True)
    bom_id = fields.Many2one(
        'mrp.bom', 'Bill of Material',
        domain="""[
        '&',
            '|',
                ('product_id','=',product_id),
                    '&',
                        ('product_tmpl_id.product_variant_ids','=',product_id),
                        ('product_id','=',False),
        ('type', '=', 'normal')]""",
        check_company=True, store=True,
        help="Bill of Materials allow you to define the list of required components to make a finished product.")

    salesforecast_product_items_id = fields.One2many('forecast.salesforecastproductsitems', 'salesforcast_product_id',
                                                     "Items List", store=True)


class SalesforecastProductsItems(models.Model):
    """ Manufacturing Orders """
    _name = 'forecast.salesforecastproductsitems'
    _description = 'Salesforecast BOM Items'

    salesforcast_product_id = fields.Many2one('forecast.salesforecastproducts', 'salesforecast product ref')
    salesforecast_id = fields.Many2one(
        'forecast.salesforecast', 'Salesforecast')
    item_id = fields.Many2one(
        'product.product', 'Item Name')
    product_id = fields.Many2one(
        'product.product', 'Product')
    item_qty = fields.Float(
        'Required Quantity',
        default=1.0, digits='Product Unit of Measure',
        readonly=False, required=True, tracking=True, group_operator="sum")

    item_available = fields.Float(
        'Qty available',
        related='item_id.qty_available',
        readonly=False, store=True)

    item_required = fields.Float(
        'Item required',
        default=1.0, digits='Ingredient Required',
        readonly=False, required=False, tracking=True)


class SalesforecastProductItems(models.Model):
    """ Items grouped """
    _name = 'forecast.salesforecastitemsgrouped'
    _description = 'Salesforecast ingredients grouped'

    salesforecast_id = fields.Many2one(
        'forecast.salesforecast', 'Salesforecast')
    item_id = fields.Many2one(
        'product.product', 'Item Name')
    item_qty = fields.Float(
        'Required Quantity',
        default=1.0, digits='Product Unit of Measure',
        readonly=False, required=True, tracking=True, group_operator="sum")

    item_available = fields.Float(
        'Qty available',
        related='item_id.qty_available',
        readonly=False, store=True)

    item_required = fields.Float(
        'Item required',
        default=1.0, digits='Ingredient Required',
        readonly=False, required=False, tracking=True)

