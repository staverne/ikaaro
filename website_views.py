# -*- coding: UTF-8 -*-
# Copyright (C) 2005-2008 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007-2008 Sylvain Taverne <sylvain@itaapy.com>
# Copyright (C) 2008 Nicolas Deram <nicolas@itaapy.com>
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

# Import from the Standard Library
from getpass import getuser
from json import dumps
from socket import gethostname

# Import from itools
from itools.core import get_abspath, merge_dicts
from itools.csv import Property
from itools.datatypes import Email, String, Unicode, Integer
from itools.datatypes import Enumerate
from itools.gettext import MSG
from itools.fs import lfs
from itools.web import BaseView, STLView, INFO

# Import from ikaaro
from autoform import AutoForm
from autoform import HiddenWidget, SelectWidget, MultilineWidget, TextWidget
from buttons import Button
from config_captcha import CaptchaDatatype, CaptchaWidget
from messages import MSG_NEW_RESOURCE
from registry import get_resource_class
from views_new import NewInstance



class NotFoundView(STLView):
    template = '/ui/root/not_found.xml'

    def get_namespace(self, resource, context):
        return {'uri': str(context.uri)}


class ForbiddenView(STLView):
    template = '/ui/root/forbidden.xml'

    def POST(self, resource, context):
        return self.GET



class UploadStatsView(BaseView):

    access = True
    query_schema = {'upload_id': Integer}

    def GET(self, resource, context):
        context.content_type = 'text/plain'

        upload_id = context.query.get('upload_id')
        if upload_id is None:
            return dumps({'valid_id': False})

        stats = context.server.upload_stats.get(upload_id)
        if stats is None:
            return dumps({'valid_id': False})

        uploaded_size, total_size = stats
        if total_size != 0:
            percent = float(uploaded_size) / total_size * 100.0
        else:
            percent = 0.0
        return dumps({'valid_id': True,
                      'percent': percent,
                      'uploaded_size': uploaded_size,
                      'total_size': total_size})



class ContactOptions(Enumerate):

    def get_options(cls):
        resource = cls.resource
        users = resource.get_resource('/users')
        options = []
        for name in resource.get_property('contacts'):
            user = users.get_resource(name, soft=True)
            if user is None:
                continue
            options.append({'name': name, 'value': user.get_title()})
        return options



class ContactForm(AutoForm):

    access = True
    title = MSG(u'Contact')
    actions = [Button(access=True, css='button-ok', title=MSG(u'Send'))]
    query_schema = {'to': String,
                    'subject': Unicode,
                    'message_body': Unicode}

    def get_schema(self, resource, context):
        to = ContactOptions(resource=resource, mandatory=True)
        if len(to.get_options()) == 1:
            to = String(mandatory=True)

        return {
            'to': to,
            'from': Email(mandatory=True),
            'subject': Unicode(mandatory=True),
            'message_body': Unicode(mandatory=True),
            'captcha': CaptchaDatatype}


    def get_widgets(self, resource, context):
        if len(ContactOptions(resource=resource).get_options()) == 1:
            to = HiddenWidget('to')
        else:
            to = SelectWidget('to', title=MSG(u'Recipient'))

        return [
            to,
            TextWidget('from', title=MSG(u'Your email address'), size=40),
            TextWidget('subject', title=MSG(u'Message subject'), size=40),
            MultilineWidget('message_body', title=MSG(u'Message body'),
                            rows=8, cols=50),
            CaptchaWidget('captcha')]


    def get_value(self, resource, context, name, datatype):
        if name == 'to':
            options = ContactOptions(resource=resource).get_options()
            if len(options) == 1:
                return options[0]['name']

        if name == 'from':
            user = context.user
            if user is not None:
                return user.get_property('email')
            return datatype.get_default()

        query = context.query
        if name in query:
            return query[name]

        return datatype.get_default()


    def action(self, resource, context, form):
        # Get form values
        contact = form['to']
        from_addr = form['from'].strip()
        subject = form['subject'].strip()
        body = form['message_body'].strip()

        # Find out the "to" address
        contact = resource.get_resource('/users/%s' % contact)
        contact_title = contact.get_title()
        contact = contact.get_property('email')
        if contact_title != contact:
            contact = (contact_title, contact)
        # Send the email
        root = resource.get_root()
        root.send_email(contact, subject, from_addr=from_addr, text=body)
        # Ok
        context.message = INFO(u'Message sent.')



class AboutView(STLView):

    access = True
    title = MSG(u'About')
    template = '/ui/root/about.xml'


    def get_namespace(self, resource, context):
        # Case 1: not admin
        ac = resource.get_access_control()
        if not ac.is_admin(context.user, resource):
            return {'is_admin': False}

        # Case 2: admin
        package2title = {
            'gio': u'pygobject',
            'lpod': u'lpOD',
            'sys': u'Python',
            'os': MSG(u'Operating System')}
        root = context.root
        packages = [
            {'name': package2title.get(x, x),
             'version': y or MSG('no version found')}
                 for x, y in root.get_version_of_packages(context).items()]

        location = (getuser(), gethostname(), context.server.target)
        return {'is_admin': True,
                'packages': packages,
                'location': u'%s@%s:%s' % location}



class CreditsView(STLView):

    access = True
    title = MSG(u'Credits')
    template = '/ui/root/credits.xml'
    styles = ['/ui/credits.css']


    def get_namespace(self, resource, context):
        # Build the namespace
        credits = get_abspath('CREDITS')
        lines = lfs.open(credits).readlines()
        names = [ x[3:].strip() for x in lines if x.startswith('N: ') ]

        return {'hackers': names}



vhosts_widget = MultilineWidget('vhosts', title=MSG(u'Domain names'),
    tip=MSG(u'Type the hostnames this website will apply to, each one in a'
            u' different line.'))

class WebSite_NewInstance(NewInstance):

    schema = merge_dicts(NewInstance.schema, vhosts=String)
    widgets = NewInstance.widgets + [vhosts_widget]


    def action(self, resource, context, form):
        # Get the container
        container = form['container']
        # Make the resource
        class_id = context.query['type']
        cls = get_resource_class(class_id)
        child = container.make_resource(form['name'], cls)
        # Set properties
        language = container.get_edit_languages(context)[0]
        title = Property(form['title'], lang=language)
        child.metadata.set_property('title', title)
        vhosts = form['vhosts']
        vhosts = [ x.strip() for x in vhosts.splitlines() ]
        vhosts = [ x for x in vhosts if x ]
        child.metadata.set_property('vhosts', vhosts)
        # Add initial user
        child.set_user_role(context.user.name, 'admins')
        # Ok
        goto = str(resource.get_pathto(child))
        return context.come_back(MSG_NEW_RESOURCE, goto=goto)
