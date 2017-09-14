# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2017 Acysos S.L. (http://acysos.com) All Rights Reserved.
#                       Ignacio Ibeas <ignacio@acysos.com>
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api
from openerp.tools.translate import _


class purchase_order_line(models.Model):
    _inherit = 'purchase.order.line'
    _order = 'sequence asc'

    extra_parent_line_id = fields.Many2one(
        comodel_name='purchase.order.line', string='Extra Price',
        help='The line that contain the product with the extra price')
    extra_child_line_id = fields.Many2one(
        comodel_name='purchase.order.line', string='Line extra price',
        help='')
    sequence = fields.Integer(
        string='Sequence', default=10,
        help="Gives the sequence order when displaying a "
        "list of purchase order lines.")

    @api.multi
    def unlink(self):
        for res in self:
            if res.extra_child_line_id:
                res.extra_child_line_id.unlink()
            return super(purchase_order_line, self).unlink()

    @api.multi
    def update_child(self, line, vals):
        if 'product_qty' in vals and line.extra_child_line_id:
                line.extra_child_line_id.rpoduct_qty = vals['product_uom_qty']

    @api.multi
    def write(self, vals):
        for res in self:
            self.update_child(res, vals)
            return super(purchase_order_line, self).write(vals)


class purchase_order(models.Model):
    _inherit = 'purchase.order'

    def create(self, cr, uid, vals, context=None):
        result = super(purchase_order,self).create(cr, uid, vals, context)
        self.expand_extra_prices(cr, uid, [result], context)
        return result

    def write(self, cr, uid, ids, vals, context=None):
        result = super(purchase_order,self).write(cr, uid, ids, vals, context)
        self.expand_extra_prices(cr, uid, ids, context)
        return result

    def prepare_expand_extra_prices(self, line, tax_ids, extra_price,order,sequence):
        vals = {'name': '-- '+line.product_id.name_extra_price or ' ',
                'product_qty': line.product_qty,
                'date_planned': line.date_planned,
                'taxes_id': [(6, 0, tax_ids)],
                'product_uom': line.product_uom.id,
                'move_ids': [(6, 0, [])],
                'move_dest_id': False,
                'price_unit': extra_price,
                'order_id': order.id,
                'account_analytic_id': line.account_analytic_id.id,
                'state': 'draft',
                'invoiced': True,
                'sequence': sequence,
                'extra_parent_line_id': line.id,
                'product_id': line.product_id.product_id_extra.id or None,
                }
        return vals

    def expand_extra_prices(self, cr, uid, ids, context={}):
        if type(ids) in [int, long]:
            ids = [ids]
        updated_orders = []
        for order in self.browse(cr, uid, ids, context):
            fiscal_position = order.fiscal_position and self.pool.get(
                'account.fiscal.position').browse(
                cr, uid, order.fiscal_position.id, context) or False
            sequence = -1
            reorder = []
            for line in order.order_line:
                sequence += 1
                if sequence > line.sequence:
                    self.pool.get('purchase.order.line').write(
                        cr, uid, [line.id], {
                            'sequence': sequence,
                        }, context)
                else:
                    sequence = line.sequence
                if line.state != 'draft':
                    continue
                if not line.product_id:
                    continue
                if line.extra_child_line_id:
                    continue

                extra_price = line.product_id.extra_price_purchase
#                 supplier_info_ids = self.pool.get('product.supplierinfo').search(cr, uid, [('name','=',line.order_id.partner_id.id),('product_id','=',line.product_id.id)])
#                 pl_partner_ids = self.pool.get('pricelist.partnerinfo').search(cr,uid,[('suppinfo_id','=',supplier_info_ids[0])], order='min_quantity DESC')
#                 pl_partner = self.pool.get('pricelist.partnerinfo').browse(cr,uid,pl_partner_ids)
#                 for pl in pl_partner:
#                     if pl.min_quantity <  line.product_qty:
#                         extra_price = pl.extra_price
                if extra_price == 0:
                    continue
                sequence += 1
                tax_ids = self.pool.get('account.fiscal.position').map_tax(
                    cr, uid, fiscal_position, line.product_id.product_id_extra.taxes_id)
                vals = self.prepare_expand_extra_prices(
                    line, tax_ids, extra_price, order, sequence)
                extra_line = self.pool.get('purchase.order.line').create(
                    cr, uid, vals, context)
                if not order.id in updated_orders:
                    updated_orders.append( order.id )
                self.pool.get('purchase.order.line').write(cr,uid,[line.id],{'extra_child_line_id':extra_line})
                for id in reorder:
                    sequence += 1
                    self.pool.get('purchase.order.line').write(cr, uid, [id], {
                        'sequence': sequence,
                    }, context)
                
        return
    
