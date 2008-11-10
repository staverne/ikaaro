# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Import from itools
from itools.csv import UniqueError, Property
from itools.datatypes import DataType, is_datatype, copy_datatype
from itools.datatypes import Integer, Enumerate, Tokens, Unicode
from itools.gettext import MSG
from itools.web import MSG_MISSING_OR_INVALID, INFO, ERROR
from itools.xapian import PhraseQuery

# Import from ikaaro
from buttons import Button, RemoveButton
from forms import AutoForm
import messages
from resource_views import EditLanguageMenu
from views import SearchForm



class Multiple(DataType):

    def decode(self, data):
        if isinstance(data, list):
            lines = data
        else:
            lines = data.splitlines()

        return [ self.type.decode(x) for x in lines ]



class Table_View(SearchForm):

    access = 'is_allowed_to_view'
    access_POST = 'is_allowed_to_edit'
    title = MSG(u'View')
    icon = 'view.png'

    schema = {
        'ids': Integer(multiple=True, mandatory=True),
    }

    def get_widgets(self, resource, context):
        return resource.get_form()


    def get_search_schema(self, resource, context):
        return resource.handler.record_schema


    def get_items(self, resource, context):
        search_query = None

        # Build the search query
        if self.search_template is not None:
            query = context.query
            search_term = query['search_term'].strip()
            if search_term:
                search_field = query['search_field']
                search_query = PhraseQuery(search_field, search_term)

        # Ok
        items = resource.handler.search(search_query)
        return list(items)


    def get_search_fields(self, resource, context):
        search_fields = []
        schema = self.get_search_schema(resource, context)
        for widget in self.get_widgets(resource, context):
            if hasattr(schema[widget.name], 'index'):
                title = getattr(widget, 'title', widget.name)
                search_fields.append((widget.name, title))
        return search_fields


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        reverse = context.query['reverse']
        if sort_by:
            items.sort(cmp=lambda x,y: cmp(getattr(x, sort_by),
                       getattr(y, sort_by)), reverse=reverse)

        # Batch
        start = context.query['batch_start']
        size = context.query['batch_size']
        return items[start:start+size]


    def get_table_columns(self, resource, context):
        columns = [
            ('checkbox', None),
            ('id', MSG(u'id'))]
        # From the schema
        for widget in self.get_widgets(resource, context):
            column = (widget.name, getattr(widget, 'title', widget.name))
            columns.append(column)

        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'checkbox':
            return item.id, False
        elif column == 'id':
            id = item.id
            link = context.get_link(resource)
            return id, '%s/;edit_record?id=%s' % (link, id)

        # Columns
        handler = resource.handler
        value = handler.get_record_value(item, column)
        datatype = handler.get_record_datatype(column)

        # Multiple
        is_unicode = is_datatype(datatype, Unicode)
        is_multiple = getattr(datatype, 'multiple', False)
        is_tokens = is_datatype(datatype, Tokens)

        if (is_multiple and not is_unicode) or is_tokens:
            if is_multiple:
                value.sort()
            value_length = len(value)
            if value_length > 0:
                rmultiple = value_length > 1
                value = value[0]
            else:
                rmultiple = False
                value = None

        # Enumerate
        is_enumerate = getattr(datatype, 'is_enumerate', False)
        if is_enumerate:
            value = datatype.get_value(value)

        if (is_multiple and not is_unicode) or is_tokens:
            return value, rmultiple
        return value


    table_actions = [RemoveButton]


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.handler.del_record(id)

        context.message = INFO(u'Record deleted.')



class Table_AddRecord(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Add Record')
    icon = 'new.png'
    submit_value = MSG(u'Add')


    def get_schema(self, resource, context):
        schema = resource.get_schema()
        # Change Unicode datatypes to be not-multiple
        schema = schema.copy()
        for name in schema:
            datatype = schema[name]
            if is_datatype(datatype, Unicode):
                schema[name] = copy_datatype(datatype, multiple=False)
        # Ok
        return schema


    def get_widgets(self, resource, context):
        return resource.get_form()


    def action(self, resource, context, form):
        schema = self.get_schema(resource, context)
        handler = resource.handler
#       # check form
#       check_fields = {}
#       for name in schema:
#           datatype = handler.get_record_datatype(name)
#           if getattr(datatype, 'multiple', False) is True:
#               datatype = Multiple(type=datatype)
#           check_fields[name] = datatype

#       try:
#           form = self.check_form_input(resource, check_fields)
#       except FormError:
#           context.message = MSG_MISSING_OR_INVALID
#           return

        language = resource.get_content_language(context)
        record = {}
        for name in schema:
            datatype = handler.get_record_datatype(name)
            if getattr(datatype, 'multiple', False) is True:
                if is_datatype(datatype, Enumerate):
                    value = form[name]
                elif is_datatype(datatype, Unicode):
                    value = form[name]
                    value = Property(value, {'language': language})
                else: # textarea -> string
                    values = form[name]
                    values = values.splitlines()
                    value = []
                    for index in range(len(values)):
                        tmp = values[index].strip()
                        if tmp:
                            value.append(datatype.decode(tmp))
            else:
                value = form[name]
            record[name] = value
        try:
            handler.add_record(record)
            context.message = INFO(u'New record added.')
        except UniqueError, error:
            title = resource.get_field_title(error.name)
            context.message = ERROR(error, field=title, value=error.value)
        except ValueError, error:
            message = ERROR(u'Error: $message', message=str(error))
            context.message = message



class Table_EditRecord(AutoForm):

    access = 'is_allowed_to_edit'
    title = MSG(u'Edit record ${id}')
    query_schema = {'id': Integer}

    context_menus = [EditLanguageMenu()]


    def get_value(self, resource, context, name, datatype):
        handler = resource.get_handler()
        # Get the record
        id = context.query['id']
        record = handler.get_record(id)
        # Is mulitilingual
        if is_datatype(datatype, Unicode):
            language = resource.get_content_language(context)
            return handler.get_record_value(record, name, language=language)

        return handler.get_record_value(record, name)


    def get_schema(self, resource, context):
        schema = resource.get_schema()
        # Change Unicode datatypes to be not-multiple
        schema = schema.copy()
        for name in schema:
            datatype = schema[name]
            if is_datatype(datatype, Unicode):
                schema[name] = copy_datatype(datatype, multiple=False)
        # Ok
        return schema


    def get_widgets(self, resource, context):
        return resource.get_form()


    def get_title(self, context):
        id = context.query['id']
        return self.title.gettext(id=id)


    def action(self, resource, context, form):
        id = context.query.get('id')
        if id is None:
            context.message = MSG_MISSING_OR_INVALID
            return

        # Check form
        handler = resource.handler
        check_fields = {}
        for widget in resource.get_form():
            datatype = handler.get_record_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                datatype = Multiple(type=datatype)
            check_fields[widget.name] = datatype

        # Get the record
        language = resource.get_content_language(context)
        record = {}
        for widget in resource.get_form():
            datatype = handler.get_record_datatype(widget.name)
            if getattr(datatype, 'multiple', False) is True:
                if is_datatype(datatype, Enumerate):
                    value = form[widget.name]
                elif is_datatype(datatype, Unicode):
                    value = form[widget.name]
                    value = Property(value, {'language': language})
                else: # textarea -> string
                    values = form[widget.name]
                    values = values.splitlines()
                    value = []
                    for index in range(len(values)):
                        tmp = values[index].strip()
                        if tmp:
                            value.append(datatype.decode(tmp))
            else:
                value = form[widget.name]
            record[widget.name] = value

        try:
            handler.update_record(id, **record)
            context.message = messages.MSG_CHANGES_SAVED
        except UniqueError, error:
            title = resource.get_field_title(error.name)
            context.message = ERROR(error, field=title, value=error.value)
        except ValueError, error:
            message = ERROR(u'Error: $message', message=str(error))
            context.message = message



class OrderedTable_View(Table_View):

    def get_items(self, resource, context):
        items = resource.handler.get_records_in_order()
        return list(items)


    def sort_and_batch(self, resource, context, items):
        # Sort
        sort_by = context.query['sort_by']
        if sort_by == 'order':
            reverse = context.query['reverse']
            ordered_ids = list(resource.handler.get_record_ids_in_order())
            f = lambda x: ordered_ids.index(x.id)
            items.sort(cmp=lambda x,y: cmp(f(x), f(y)), reverse=reverse)

            # Batch
            start = context.query['batch_start']
            size = context.query['batch_size']
            return items[start:start+size]

        return Table_View.sort_and_batch(self, resource, context, items)


    def get_table_columns(self, resource, context):
        columns = Table_View.get_table_columns(self, resource, context)
        columns.append(('order', MSG(u'Order')))

        return columns


    def get_item_value(self, resource, context, item, column):
        if column == 'order':
            ordered_ids = list(resource.handler.get_record_ids_in_order())
            return ordered_ids.index(item.id) + 1

        return Table_View.get_item_value(self, resource, context, item, column)


    table_actions = [
        RemoveButton,
        Button(name='order_up', title=MSG(u'Order up'),
               access='is_allowed_to_edit'),
        Button(name='order_down', title=MSG(u'Order down'),
               access='is_allowed_to_edit'),
        Button(name='order_top', title=MSG(u'Order top'),
               access='is_allowed_to_edit'),
        Button(name='order_bottom', title=MSG(u'Order bottom'),
               access='is_allowed_to_edit'),
    ]


    #######################################################################
    # Form Actions
    #######################################################################
    def action_remove(self, resource, context, form):
        ids = form['ids']
        for id in ids:
            resource.handler.del_record(id)

        context.message = INFO(u'Record deleted.')


    def action_order_up(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order up.')
            context.message = message
            return

        resource.handler.order_up(ids)
        context.message = INFO(u'Resources ordered up.')


    def action_order_down(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order down.')
            context.message = message
            return

        resource.handler.order_down(ids)
        context.message = INFO(u'Resources ordered down.')


    def action_order_top(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order on top.')
            context.message = message
            return

        resource.handler.order_top(ids)
        context.message = INFO(u'Resources ordered on top.')


    def action_order_bottom(self, resource, context, form):
        ids = form['ids']
        if not ids:
            message = ERROR(u'Please select the resources to order on bottom.')
            context.message = message
            return

        resource.handler.order_bottom(ids)
        context.message = INFO(u'Resources ordered on bottom.')

