# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Sylvain Taverne <sylvain@agicia.com>
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
from itools.database import AndQuery, PhraseQuery
from itools.gettext import MSG
from itools.validators import validator

# Import from ikaaro
from ikaaro.autoedit import AutoEdit
from fields import SelectAbspath_Field


class GroupsField(SelectAbspath_Field):

    title = MSG(u'Groupes')
    base_path = '/config/groups'


class UsersByGroupsField(SelectAbspath_Field):

    field_id = 'user-by-groups'
    title = MSG(u'Users du group')

    the_format = 'user'
    linked_key = 'groups'
    linked_value = None


class TestLinked(AutoEdit):

    access = True
    title = MSG(u"Test linked")

    fields = ['field_1', 'field_2', 'field_3']

    field_1 = GroupsField
    field_2 = UsersByGroupsField
    field_3 = UsersByGroupsField(linked_value='/config/groups/admins')

    def _get_datatype(self, resource, context, name):
          field = self.get_field(resource, name)
          return field(resource=resource)

    def action(self, resource, context, form):
        print form
