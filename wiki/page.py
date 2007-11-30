# -*- coding: UTF-8 -*-
# Copyright (C) 2007 Henry Obein <henry@itaapy.com>
# Copyright (C) 2007 Hervé Cauwelier <herve@itaapy.com>
# Copyright (C) 2007 Juan David Ibáñez Palomar <jdavid@itaapy.com>
# Copyright (C) 2007 Sylvain Taverne <sylvain@itaapy.com>
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
from datetime import datetime
from tempfile import mkdtemp
from subprocess import call
from urllib import urlencode

# Import from docutils
from docutils import core
from docutils import io
from docutils import readers
from docutils import nodes

# Import from itools
from itools.datatypes import DateTime, Unicode, FileName
from itools.handlers import checkid
from itools.stl import stl
from itools import vfs
from itools.xml import XMLParser

# Import from ikaaro
from ikaaro.base import DBObject
from ikaaro.messages import MSG_EDIT_CONFLICT, MSG_CHANGES_SAVED
from ikaaro.text import Text
from ikaaro.registry import register_object_class
from ikaaro.binary import Image
from ikaaro.skins import UIFile


class WikiPage(Text):
    class_id = 'WikiPage'
    class_version = '20061229'
    class_title = u"Wiki Page"
    class_description = u"Wiki contents"
    class_icon16 = 'wiki/WikiPage16.png'
    class_icon48 = 'wiki/WikiPage48.png'
    class_views = [['view', 'to_pdf'],
                   ['edit_form', 'externaledit', 'upload_form'],
                   ['edit_metadata_form'],
                   ['state_form'],
                   ['help']]

    overrides = {
        # Security
        'file_insertion_enabled': 0,
        'raw_enabled': 0,
        # Encodings
        'input_encoding': 'utf-8',
        'output_encoding': 'utf-8',
    }

    #######################################################################
    # User interface
    #######################################################################
    @staticmethod
    def new_instance_form(cls, context):
        return DBObject.new_instance_form(cls, context)


    GET__mtime__ = None
    GET__access__ = True
    def GET(self, context):
        return context.uri.resolve2(';view')


    view__sublabel__ = u'HTML'
    def view(self, context):
        context.styles.append('/ui/wiki/wiki.css')
        parent = self.parent
        here = context.object

        # Override dandling links handling
        StandaloneReader = readers.get_reader_class('standalone')
        class WikiReader(StandaloneReader):
            supported = ('wiki',)

            def wiki_reference_resolver(target):
                refname = target['name']
                name = checkid(refname)

                # It may be the page or its container
                # It may a page title to convert or a path
                ref = None
                for container, path in ((self, name),
                                        (parent, name),
                                        (self, refname),
                                        (parent, refname)):
                    try:
                        ref = container.get_object(path)
                    except (NotImplementedError, LookupError,
                            UnicodeEncodeError):
                        continue
                    # Found, exit now
                    break

                if ref is None:
                    target['wiki_refname'] = False
                    target['wiki_title'] = refname
                    target['wiki_name'] = name
                else:
                    target['wiki_refname'] = refname
                    target['wiki_title'] = refname
                    target['wiki_name'] = str(here.get_pathto(ref))
                return True

            wiki_reference_resolver.priority = 851
            unknown_reference_resolvers = [wiki_reference_resolver]

        # Manipulate publisher directly (from publish_doctree)
        reader = WikiReader(parser_name='restructuredtext')
        pub = core.Publisher(reader=reader, source_class=io.StringInput,
                destination_class=io.NullOutput)
        pub.set_components(None, 'restructuredtext', 'null')
        pub.process_programmatic_settings(None, self.overrides, None)
        pub.set_source(self.handler.to_str(), None)
        pub.set_destination(None, None)

        # Publish!
        pub.publish(enable_exit_status=None)
        document = pub.document

        # Fix the wiki links
        for node in document.traverse(condition=nodes.reference):
            refname = node.get('wiki_refname')
            if refname is None:
                if node.get('refid'):
                    node['classes'].append('internal')
                elif node.get('refuri'):
                    node['classes'].append('external')
            else:
                title = node['wiki_title']
                name = node['wiki_name']
                if refname is False:
                    params = {'type': self.__class__.__name__,
                              'dc:title': title.encode('utf_8'),
                              'name': name}
                    refuri = ";new_resource_form?%s" % urlencode(params)
                    prefix = here.get_pathto(parent)
                    refuri = '%s/%s' % (prefix, refuri)
                    css_class = 'nowiki'
                else:
                    # 'name' is now the path to existing handler
                    refuri = name
                    css_class = 'wiki'
                node['refuri'] = refuri
                node['classes'].append(css_class)

        # Allow to reference images by name without their path
        for node in document.traverse(condition=nodes.image):
            node_uri = node['uri']
            # Is the path is correct?
            image = None
            for container in (self, parent):
                try:
                    image = container.get_object(node_uri)
                except (NotImplementedError, LookupError):
                    continue
                # Found, exit now
                break

            if image is not None:
                node['uri'] = str(here.get_pathto(image))

        # Manipulate publisher directly (from publish_from_doctree)
        reader = readers.doctree.Reader(parser_name='null')
        pub = core.Publisher(reader, None, None,
                source=io.DocTreeInput(document),
                destination_class=io.StringOutput)
        pub.set_writer('html')
        pub.process_programmatic_settings(None, self.overrides, None)
        pub.set_destination(None, None)
        pub.publish(enable_exit_status=None)
        parts = pub.writer.parts
        body = parts['html_body']

        return body.encode('utf_8')


    to_pdf__access__ = 'is_allowed_to_view'
    to_pdf__label__ = u"View"
    to_pdf__sublabel__ = u"PDF"
    def to_pdf(self, context):
        parent = self.parent
        pages = [self.name]
        images = []

        # Override dandling links handling
        StandaloneReader = readers.get_reader_class('standalone')
        class WikiReader(StandaloneReader):
            supported = ('wiki',)

            def wiki_reference_resolver(target):
                refname = target['name']
                name = checkid(refname)
                if refname not in pages:
                    pages.append(refname)
                target['wiki_refname'] = refname
                target['wiki_name'] = name
                return True

            wiki_reference_resolver.priority = 851
            unknown_reference_resolvers = [wiki_reference_resolver]

        reader = WikiReader(parser_name='restructuredtext')
        document = core.publish_doctree(self.handler.to_str(), reader=reader,
                settings_overrides=self.overrides)

        # Fix the wiki links
        for node in document.traverse(condition=nodes.reference):
            refname = node.get('wiki_refname')
            if refname is None:
                continue
            name = node['name'].lower()
            document.nameids[name] = refname

        # Append referenced pages
        for refname in pages[1:]:
            references = document.refnames[refname.lower()]
            reference = references[0]
            reference.parent.remove(reference)
            name = reference['wiki_name']
            try:
                page = parent.get_object(name)
            except LookupError:
                continue
            title = reference.astext()
            if isinstance(page, Image):
                # Link to image?
                images.append(('../%s' % name, name))
                continue
            elif not isinstance(page, WikiPage):
                # Link to file
                continue
            source = page.handler.to_str()
            subdoc = core.publish_doctree(source,
                    settings_overrides=self.overrides)
            if isinstance(subdoc[0], nodes.section):
                for node in subdoc.children:
                    if isinstance(node, nodes.section):
                        document.append(node)
            else:
                subtitle = subdoc.get('title', u'')
                section = nodes.section(*subdoc.children, **subdoc.attributes)
                section.insert(0, nodes.title(text=subtitle))
                document.append(section)

        # Find the list of images to append
        for node in document.traverse(condition=nodes.image):
            node_uri = node['uri']
            image = None
            for container in (self, parent):
                try:
                    image = container.get_object(node_uri)
                except (NotImplementedError, LookupError):
                    continue
                # Found, exit now
                break
            if image is None:
                # missing image but prevent pdfLaTeX failure
                node_uri = '/ui/wiki/missing.png'
                filename = 'missing.png'
            else:
                node_uri = image.get_abspath()
                filename = image.name
            name, ext, lang = FileName.decode(filename)
            if ext == 'jpeg':
                # pdflatex does not support this extension
                ext = 'jpg'
            filename = FileName.encode((name, ext, lang))
            # Remove all path so the image is found in tempdir
            node['uri'] = filename
            images.append((node_uri, filename))

        overrides = dict(self.overrides)
        overrides['stylesheet'] = 'style.tex'
        output = core.publish_from_doctree(document, writer_name='latex',
                settings_overrides=overrides)

        dirname = mkdtemp('wiki', 'itools')
        tempdir = vfs.open(dirname)

        # Save the document...
        file = tempdir.make_file(self.name)
        try:
            file.write(output)
        finally:
            file.close()
        # The stylesheet...
        stylesheet = self.get_object('/ui/wiki/style.tex')
        file = tempdir.make_file('style.tex')
        try:
            stylesheet.save_state_to_file(file)
        finally:
            file.close()
        # The 'powered' image...
        image = self.get_object('/ui/images/ikaaro_powered.png')
        file = tempdir.make_file('ikaaro.png')
        try:
            image.save_state_to_file(file)
        finally:
            file.close()
        # And referenced images
        for node_uri, filename in images:
            if tempdir.exists(filename):
                continue
            image = self.get_object(node_uri)
            file = tempdir.make_file(filename)
            try:
                if isinstance(image, UIFile):
                    image.save_state_to_file(file)
                else:
                    image.handler.save_state_to_file(file)
            finally:
                file.close()

        try:
            call(['pdflatex', '-8bit', '-no-file-line-error',
                  '-interaction=batchmode', self.name], cwd=dirname)
            # Twice for correct page numbering
            call(['pdflatex', '-8bit', '-no-file-line-error',
                  '-interaction=batchmode', self.name], cwd=dirname)
        except OSError:
            msg = u"PDF generation failed. Please install pdflatex."
            return context.come_back(msg)

        pdfname = '%s.pdf' % self.name
        if tempdir.exists(pdfname):
            file = tempdir.open(pdfname)
            try:
                data = file.read()
            finally:
                file.close()
        else:
            data = None
        vfs.remove(dirname)

        if data is None:
            return context.come_back(u"PDF generation failed.")

        response = context.response
        response.set_header('Content-Type', 'application/pdf')
        response.set_header('Content-Disposition',
                'attachment; filename=%s' % pdfname)

        return data


    def edit_form(self, context):
        context.styles.append('/ui/wiki/wiki.css')
        text_size = context.get_form_value('text_size');
        text_size_cookie = context.get_cookie('wiki_text_size')

        if text_size_cookie is None:
            if not text_size:
                text_size = 'small'
            context.set_cookie('wiki_text_size', text_size)
        elif text_size is None:
            text_size = context.get_cookie('wiki_text_size')
        elif text_size != text_size_cookie:
            context.set_cookie('wiki_text_size', text_size)

        namespace = {}
        namespace['timestamp'] = DateTime.encode(datetime.now())
        namespace['data'] = self.handler.to_str()
        namespace['text_size'] = text_size

        handler = self.get_object('/ui/wiki/WikiPage_edit.xml')
        return stl(handler, namespace)


    def edit(self, context):
        timestamp = context.get_form_value('timestamp', type=DateTime)
        if timestamp is None:
            return context.come_back(MSG_EDIT_CONFLICT)
        page = self.handler
        if page.timestamp is not None and timestamp < page.timestamp:
            return context.come_back(MSG_EDIT_CONFLICT)

        data = context.get_form_value('data', type=Unicode)
        text_size = context.get_form_value('text_size');
        # Ensure source is encoded to UTF-8
        data = data.encode('utf_8')
        page.load_state_from_string(data)

        if 'class="system-message"' in self.view(context):
            message = u"Syntax error, please check the view for details."
        else:
            message = MSG_CHANGES_SAVED

        goto = context.come_back(message, keep=['text_size'])
        if context.has_form_value('view'):
            query = goto.query
            goto = goto.resolve(';view')
            goto.query = query
        else:
            goto.fragment = 'bottom'
        return goto


    help__access__ = 'is_allowed_to_view'
    help__label__ = u"Help"
    def help(self, context):
        context.styles.append('/ui/wiki/wiki.css')
        namespace = {}

        source = self.get_object('/ui/wiki/help.txt')
        source = source.to_str()
        html = core.publish_string(source, writer_name='html',
                settings_overrides=self.overrides)

        namespace['help_source'] = source
        namespace['help_html'] = XMLParser(html)

        handler = self.get_object('/ui/wiki/WikiPage_help.xml')
        return stl(handler, namespace)


###########################################################################
# Register
###########################################################################
register_object_class(WikiPage)
