#    Copyright (c) 2015, Telefonica I+D.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import re
import types

from oslo.db import exception as db_exc
from webob import exc

from murano.api.v1 import request_statistics
from murano.common import policy
from murano.common import wsgi
from murano.common import utils
from murano.db import models
from murano.db.services import core_services
from murano.db.services import templates as temps
from murano.db.services import environments
from murano.db.services import sessions
from murano.db import session as db_session

from murano.openstack.common.gettextutils import _
from murano.openstack.common import log as logging

LOG = logging.getLogger(__name__)

API_NAME = 'Templates'

VALID_NAME_REGEX = re.compile('^[a-zA-Z]+[\w-]*$')


class Controller(object):
    @request_statistics.stats_count(API_NAME, 'Index')
    def index(self, request):
        LOG.debug('Templates:List')
        policy.check('list_templates', request.context)

        #Only templates from same tenant as user should be returned
        filters = {'tenant_id': request.context.tenant}
        templates = temps.TemplateServices.get_templates_by(filters)
        templates = [temp.to_dict() for temp in templates]

        return {"templates": templates}

    @request_statistics.stats_count(API_NAME, 'Create')
    def create(self, request, body):
        LOG.debug('Templates:Create <Body {0}>'.format(body))
        policy.check('create_template', request.context)
        LOG.debug('TEMP NAME: {0}>'.format(body['name']))
        if VALID_NAME_REGEX.match(str(body['name'])):
            try:
                template = temps.TemplateServices.create(
                    body.copy(),
                    request.context.tenant)
            except db_exc.DBDuplicateEntry:
                msg = _('Template with specified name already exists')
                LOG.exception(msg)
                raise exc.HTTPConflict(msg)
        else:
            msg = _('Template must contain only alphanumeric '
                    'or "_-." characters, must start with alpha')
            LOG.exception(msg)
            raise exc.HTTPClientError(msg)

        return template.to_dict()

    @request_statistics.stats_count(API_NAME, 'Show')
    def show(self, request, template_id):
        LOG.debug('Templates:Show <Id: {0}>'.format(template_id))
        target = {"template_id": template_id}
        policy.check('show_template', request.context, target)

        session = db_session.get_session()
        template = session.query(models.Template).get(template_id)

        if template is None:
            LOG.info(_('Template <TempId {0}> is not found').format(
                template_id))
            raise exc.HTTPNotFound

        if template.tenant_id != request.context.tenant:
            LOG.info(_('User is not authorized to access '
                       'this tenant resources.'))
            raise exc.HTTPUnauthorized

        temp = template.to_dict()

        #add services to temp
        get_data = core_services.CoreServices.get_template_data
        temp['services'] = get_data(template_id, '/services')

        return temp

    @request_statistics.stats_count(API_NAME, 'Update')
    def update(self, request, template_id, body):
        LOG.debug('Environments:Update <Id: {0}, '
                  'Body: {1}>'.format(template_id, body))
        target = {"template_id": template_id}
        policy.check('update_template', request.context, target)

        session = db_session.get_session()
        template = session.query(models.Template).get(template_id)

        if template is None:
            LOG.info(_('Template <TempId {0}> is not '
                       'found').format(template_id))
            raise exc.HTTPNotFound

        if template.tenant_id != request.context.tenant:
            LOG.info(_('User is not authorized to access '
                       'this tenant resources.'))
            raise exc.HTTPUnauthorized

        LOG.debug('TEMP NAME: {0}>'.format(body['name']))
        if VALID_NAME_REGEX.match(str(body['name'])):
            template.update(body)
            template.save(session)
        else:
            msg = _('Template name must contain only alphanumeric '
                    'or "_-." characters, must start with alpha')
            LOG.exception(msg)
            raise exc.HTTPClientError(msg)

        return template.to_dict()

    @request_statistics.stats_count(API_NAME, 'Delete')
    def delete(self, request, template_id):

        LOG.debug('Templates:Delete <Id: {0}>'.format(template_id))
        target = {"template_id": template_id}
        policy.check('delete_template', request.context, target)
        session = db_session.get_session()
        template = session.query(models.Template).get(template_id)

        if template is None:
            LOG.info(_('Template <TempId {0}> is not '
                       'found').format(template_id))
            raise exc.HTTPNotFound

        temps.TemplateServices.delete(template_id)
        temps.TemplateServices.remove(template_id)
        return

    def has_services(self, template):
        if 'services' in template.description.keys():
            return True
        return False


    @request_statistics.stats_count(API_NAME, 'Createenvironment')
    def create_environment(self, request, template_id, body):
        LOG.debug('Templates:Create environment <Id: {0}>'.
            format(template_id))

        if not VALID_NAME_REGEX.match(str(body['name'])):
            msg = _('Template name must contain only alphanumeric '
                    'or "_-." characters, must start with alpha')
            LOG.exception(msg)
            raise exc.HTTPClientError(msg)

        LOG.debug('Template name: {0}>'.format(body['name']))
        unit = db_session.get_session()
        template = unit.query(models.Template).get(template_id)

        if template is None:
            LOG.info(_('Template <TempId {0}> is not '
                       'found').format(template_id))
            raise exc.HTTPNotFound

        # create environment
        try:
            environment = environments.EnvironmentServices.create(
                body.copy(), request.context.tenant)
        except db_exc.DBDuplicateEntry:
            msg = _('Environment with specified name already exists')
            LOG.exception(msg)
            raise exc.HTTPConflict(msg)

        # configure

        user_id = request.context.user
        session = sessions.SessionServices.create(environment.id, user_id)

        if self.has_services(template):
            services_node = utils.TraverseHelper.get("services", template.description)
            utils.TraverseHelper.update("/Objects/services", services_node, environment.description)

        environments.EnvironmentServices.save_environment_description(session.id, environment.description, inner=False)

        return session.to_dict()


def create_resource():
    return wsgi.Resource(Controller())
