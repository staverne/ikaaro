# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007-2008 Nicolas Deram <nicolas@itaapy.com>
# Copyright (C) 2008 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2008 Sylvain Taverne <sylvain@itaapy.com>
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
from itools.core import get_abspath, merge_dicts
from itools.datatypes import DataType, Date, Enumerate, Boolean
from itools.gettext import MSG
from itools.html import stream_to_str_as_xhtml, stream_to_str_as_html
from itools.html import xhtml_doctype, sanitize_stream
from itools.http import get_context
from itools.stl import stl, STLTemplate
from itools import vfs
from itools.web import STLForm
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.globals import ui
from ikaaro.workflow import get_workflow_preview



xhtml_namespaces = {None: 'http://www.w3.org/1999/xhtml'}



###########################################################################
# DataTypes
###########################################################################
class XHTMLBody(DataType):
    """Read and write XHTML.
    """
    sanitize_html = True

    def decode(cls, data):
        events = XMLParser(data, namespaces=xhtml_namespaces,
                           doctype=xhtml_doctype)
        if cls.sanitize_html is True:
            events = sanitize_stream(events)
        return list(events)


    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return stream_to_str_as_xhtml(value)



class HTMLBody(XHTMLBody):
    """TinyMCE specifics: read as XHTML, rendered as HTML.
    """

    @staticmethod
    def encode(value):
        if value is None:
            return ''
        return stream_to_str_as_html(value)



###########################################################################
# Widgets
###########################################################################

stl_namespaces = {
    None: 'http://www.w3.org/1999/xhtml',
    'stl': 'http://www.hforge.org/xml-namespaces/stl'}
def make_stl_template(data):
    return list(XMLParser(data, stl_namespaces))



def get_default_widget(datatype):
    if issubclass(datatype, Boolean):
        return RadioWidget
    elif issubclass(datatype, Date):
        return DateWidget
    elif issubclass(datatype, Enumerate):
        return SelectWidget

    return TextWidget



class Widget(STLTemplate):

    size = None
    tip = None
    suffix = None
    type = 'text'

    template = make_stl_template("""
    <input type="${type}" name="${name}" value="${value}" size="${size}" />""")


    def __init__(self, name=None, **kw):
        if name:
            self.name = name
        for key in kw:
            setattr(self, key, kw[key])


    def get_template(self):
        return self.template


    def render(self):
        template = self.get_template()
        return stl(events=template, namespace=self)



class TextWidget(Widget):

    size = 40



class HiddenWidget(Widget):

    type = 'hidden'



class FileWidget(Widget):

    type = 'file'



class PasswordWidget(Widget):

    type = 'password'



class ReadOnlyWidget(Widget):

    template = make_stl_template("""
    <input type="hidden" name="${name}" value="${value}" />${displayed}""")


    def get_namespace(self, datatype, value):
        displayed = getattr(self, 'displayed', None)

        if issubclass(datatype, Enumerate) and isinstance(value, list):
            for option in value:
                if not option['selected']:
                    continue
                value = option['name']
                if displayed is None:
                    displayed = option['value']
                break
            else:
                value = datatype.default
                if displayed is None:
                    displayed = datatype.get_value(value)

        if displayed is None:
            displayed = value

        return {
            'name': self.name,
            'value': value,
            'displayed': displayed}



class MultilineWidget(Widget):

    rows = 5
    cols = 60

    template = make_stl_template("""
    <textarea rows="${rows}" cols="${cols}" name="${name}" >${value}</textarea>
    """)


    def get_namespace(self, datatype, value):
        return {
            'name': self.name,
            'value': value,
            'rows': self.rows,
            'cols': self.cols}



class RadioWidget(Widget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="radio" id="${name}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${name}-${option/name}">${option/value}</label>
      <br stl:if="not oneline" />
    </stl:block>""")

    oneline = False
    has_empty_option = True # Only makes sense for enumerates
                            # FIXME Do this other way


    def get_namespace(self, datatype, value):
        # Case 1: Enumerate
        if issubclass(datatype, Enumerate):
            # Check whether the value is already a list of options
            # FIXME This is done to avoid a bug when using a select widget in
            # an auto-form, where the 'datatype.get_namespace' method is
            # called twice (there may be a better way of handling this).
            if type(value) is not list:
                options = datatype.get_namespace(value)
            else:
                options = value

            # Empty option
            if self.has_empty_option:
                options.insert(0,
                    {'name': '', 'value': '',  'is_selected': False})

            # Select first item if none selected
            for option in options:
                if option['selected'] is True:
                    break
            else:
                if options:
                    options[0]['selected'] = True
        # Case 2: Boolean
        elif issubclass(datatype, Boolean):
            default_labels = {'yes': MSG(u'Yes'), 'no': MSG(u'No')}
            labels = getattr(self, 'labels', default_labels)
            options = [
                {'name': '1', 'value': labels['yes'], 'is_selected': value},
                {'name': '0', 'value': labels['no'], 'is_selected': not value}]
        # Case 3: Error
        else:
            err = 'datatype "%s" should be enumerate or boolean'
            raise ValueError, err % self.name

        # Ok
        return {
            'name': self.name,
            'oneline': self.oneline,
            'options': options}



class CheckboxWidget(Widget):

    template = make_stl_template("""
    <stl:block stl:repeat="option options">
      <input type="checkbox" id="${name}-${option/name}" name="${name}"
        value="${option/name}" checked="${option/selected}" />
      <label for="${name}-${option/name}">${option/value}</label>
      <br stl:if="not oneline" />
    </stl:block>""")

    oneline = False


    def get_namespace(self, datatype, value):
        # Case 1: Enumerate
        if issubclass(datatype, Enumerate):
            # Check whether the value is already a list of options
            # FIXME This is done to avoid a bug when using a select widget in
            # an auto-form, where the 'datatype.get_namespace' method is
            # called twice (there may be a better way of handling this).
            if type(value) is not list:
                options = datatype.get_namespace(value)
            else:
                options = value
        # Case 2: Boolean
        elif issubclass(datatype, Boolean):
            options = [
                {'name': '1', 'value': '', 'is_selected': value}]
        # Case 3: Error
        else:
            raise ValueError, 'expected boolean or enumerate datatype'

        # Ok
        return {
            'name': self.name,
            'oneline': self.oneline,
            'options': options}



class SelectWidget(Widget):

    template = make_stl_template("""
    <select name="${name}" multiple="${multiple}" size="${size}"
        class="${css}">
      <option value="" stl:if="has_empty_option"></option>
      <option stl:repeat="option options" value="${option/name}"
        selected="${option/selected}">${option/value}</option>
    </select>""")


    def get_namespace(self, datatype, value):
        # Check whether the value is already a list of options
        # FIXME This is done to avoid a bug when using a select widget in an
        # auto-form, where the 'datatype.get_namespace' method is called
        # twice (there may be a better way of handling this).
        if type(value) is not list:
            value = datatype.get_namespace(value)
        return {
            'css': getattr(self, 'css', None),
            'has_empty_option': getattr(self, 'has_empty_option', True),
            'name': self.name,
            'multiple': datatype.multiple,
            'options': value,
            'size':  getattr(self, 'size', None)}



class DateWidget(Widget):

    tip = MSG(u"Format: 'yyyy-mm-dd'")

    template = make_stl_template("""
    <input type="text" name="${name}" value="${value}" id="${name}"
      size="${size}"/>
    <input id="trigger-date-${name}" type="button" value="..."
      name="trigger_date_${name}" class="${class}" />
    <script language="javascript">
      Calendar.setup({inputField: "${name}", ifFormat: "${format}",
                      showsTime: ${show_time}, timeFormat: "24",
                      button: "trigger-date-${name}"});
    </script>""")

    template_multiple = make_stl_template("""
    <table class="table-calendar">
      <tr>
        <td>
          <textarea rows="5" cols="25" name="${name}" id="${name}"
            >${value}</textarea>
          <input type="button" value="update" id="btn-blur-${name}"
            onclick="tableFlatOuputOnBlur(elt_${name}, cal_${name});" />
        </td>
        <td>
          <div id="calendar-flat-${name}" style="float: left;"> </div>
          <script type="text/javascript">
            var MA_${name} = [];
            <stl:block stl:repeat="date dates">
            MA_${name}.push(str_to_date('${date}'));
            </stl:block>
            var cal_${name} = Calendar.setup({
                displayArea  : '${name}',
                flat         : 'calendar-flat-${name}',
                flatCallback : tableFlatCallback,
                multiple     : MA_${name},
                ifFormat     : '${format}'});
            var elt_${name} = document.getElementById('${name}');
            if (!browser.isIE) {
                $("#btn_blur_${name}").style.display = 'none';
                elt_${name}.setAttribute('onblur',
                    'tableFlatOuputOnBlur(elt_${name}, cal_${name})');
            }
          </script>
        </td>
      </tr>
    </table>""")


    def get_template(self):
        if self.datatype.multiple:
            return self.template_multiple
        return self.template


    def get_namespace(self, datatype, value):
        if value is None:
            value = ''
        format = getattr(self, 'format', '%Y-%m-%d')
        show_time = getattr(self, 'show_time', False)
        # True -> true for Javascript
        show_time = str(show_time).lower()
        css = getattr(self, 'css', None)
        size = getattr(self, 'size', None)

        if datatype.multiple:
            if isinstance(value, list): # ['2007-08-01\r\n2007-08-02']
                value = value[0]
            return {'name': self.name, 'format': format,
                    'show_time': show_time, 'class': css,
                    'value': value, 'dates': value.splitlines()}

        return {'name': self.name, 'format': format,
                'show_time': show_time, 'class': css,
                'size': size, 'value': value}



class PathSelectorWidget(TextWidget):

    action = 'add_link'
    display_workflow = True

    template = make_stl_template("""
    <input type="text" id="selector-${name}" size="${size}" name="${name}"
      value="${value}" />
    <input id="selector-button-${name}" type="button" value="..."
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${name}&amp;mode=input', 620, 300);"/>
    ${workflow_state}""")


    def get_namespace(self, datatype, value):
        workflow_state = None
        if self.display_workflow:
            context = get_context()
            path = datatype.encode(value)
            if path:
                resource = context.resource.get_resource(path, soft=True)
                if resource:
                    workflow_state = get_workflow_preview(resource, context)

        return {
            'type': self.type,
            'name': self.name,
            'value': value,
            'size': self.size,
            'action': self.action,
            'workflow_state': workflow_state}



class ImageSelectorWidget(PathSelectorWidget):

    action = 'add_image'
    width = 128
    height = 128

    template = make_stl_template("""
    <input type="text" id="selector-${name}" size="${size}" name="${name}"
      value="${value}" />
    <input id="selector-button-${name}" type="button" value="..."
      name="selector_button_${name}"
      onclick="popup(';${action}?target_id=selector-${name}&amp;mode=input', 620, 300);" />
    ${workflow_state}
    <br/>
    <img src="${value}/;thumb?width=${width}&amp;height=${height}" stl:if="value"/>""")


    def get_namespace(self, datatype, value):
        return merge_dicts(PathSelectorWidget.get_namespace(self, datatype, value),
                           width=self.width, height=self.height)



class RTEWidget(Widget):

    template = 'tiny_mce/rte.xml'
    rte_css = ['/ui/aruni/style.css', '/ui/tiny_mce/content.css']
    rte_scripts = [
        '/ui/tiny_mce/tiny_mce_src.js',
        '/ui/tiny_mce/javascript.js']

    # Configuration
    # See http://wiki.moxiecode.com/index.php/TinyMCE:Configuration
    width = None
    height = '340px'
    # toolbar
    toolbar1 = ('newdocument,code,|,bold,italic,underline,strikethrough,|,'
                'justifyleft,justifycenter,justifyright, justifyfull,|,'
                'bullist,numlist,|, outdent, indent,|,undo,redo,|,link,'
                'unlink,image,media')
    toolbar2 = ('tablecontrols,|,removeformat,forecolor,backcolor,|,'
                'formatselect')
    toolbar3 = None
    resizing = True
    plugins = 'safari,table,media'
    # Extending the existing rule set.
    extended_valid_elements = None
    # css
    advanced_styles = None
    table_styles = None


    def get_rte_css(self):
        return self.rte_css


    def get_template(self):
        handler = ui.get_template(self.template)
        return handler.events


    def get_namespace(self, datatype, value):
        # Language
        path = get_abspath('ui/tiny_mce/langs')
        tiny_mce_languages = [ x[:-3] for x in vfs.get_names(path) ]
        accept = get_context().accept_language
        current_language = accept.select_language(tiny_mce_languages)

        css_names = self.get_rte_css()
        return {
            'advanced_styles': self.advanced_styles,
            'css': ','.join(css_names),
            'extended_valid_elements': self.extended_valid_elements,
            'form_name': self.name,
            'height': self.height,
            'language': current_language,
            'plugins': self.plugins,
            'resizing': 'true' if self.resizing else 'false',
            'scripts': self.rte_scripts,
            'source': value,
            'table_styles': self.table_styles,
            'toolbar1': self.toolbar1,
            'toolbar2': self.toolbar2,
            'toolbar3': self.toolbar3,
            'width': self.width}


###########################################################################
# Common widgets to reuse
###########################################################################
name_widget = TextWidget('name', title=MSG(u'Name'), default='')
title_widget = TextWidget('title', title=MSG(u'Title'))
description_widget = MultilineWidget('description',
                                     title=MSG(u'Description'), rows=8)
subject_widget = TextWidget('subject',
                            title=MSG(u'Keywords (Separated by comma)'))
rte_widget = RTEWidget('data', title=MSG(u'Body'))
timestamp_widget = HiddenWidget('timestamp')
file_widget = FileWidget('file', title=MSG(u'Replace file'))


###########################################################################
# Generate Form
###########################################################################
class AutoForm(STLForm):
    """Fields is a dictionnary:

      {'firstname': Unicode(mandatory=True),
       'lastname': Unicode(mandatory=True)}

    Widgets is a list:

      [TextWidget('firstname', title=MSG(u'Firstname')),
       TextWidget('lastname', title=MSG(u'Lastname'))]
    """

    widgets = []
    required_msg = None
    template = 'auto_form.xml'
    submit_value = MSG(u'Save')
    submit_class = 'button-ok'


    def get_widgets(self, resource, context):
        return self.widgets


    def get_namespace(self, resource, context):
        widgets_namespace = STLForm.get_namespace(self, resource, context)

        here = context.resource
        # Local Variables
        fields = self.get_schema(resource, context)
        widgets = self.get_widgets(resource, context)

        # Set and translate the required_msg
        required_msg = self.required_msg
        if required_msg is None:
            required_msg = MSG(
                u'The <span class="field-is-required">emphasized</span> fields'
                u' are required.')
        required_msg = required_msg.gettext()
        required_msg = required_msg.encode('utf-8')
        required_msg = XMLParser(required_msg)

        # Build widgets namespace
        has_required_widget = False
        ns_widgets = []
        for widget in widgets:
            datatype = fields[widget.name]
            is_mandatory = getattr(datatype, 'mandatory', False)
            if is_mandatory:
                has_required_widget = True
            widget_namespace = widgets_namespace[widget.name]
            value = widget_namespace['value']
            widget_namespace['title'] = getattr(widget, 'title', None)
            widget_namespace['mandatory'] = is_mandatory
            widget_namespace['multiple'] = datatype.multiple
            widget_namespace['is_date'] = issubclass(datatype, Date)
            widget_namespace['tip'] = widget.tip
            widget_namespace['suffix'] = widget.suffix
            widget = widget(datatype=datatype, value=value)
            widget_namespace['widget'] = widget.render()
            ns_widgets.append(widget_namespace)

        # Build namespace
        return {
            'title': self.get_title(context),
            'required_msg': required_msg,
            'first_widget': widgets[0].name,
            'action': context.uri,
            'submit_value': self.submit_value,
            'submit_class': self.submit_class,
            'widgets': ns_widgets,
            'has_required_widget': has_required_widget,
            }
