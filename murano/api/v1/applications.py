
#    Copyright (c) 2015 Telefonica I+D.
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

import functools as func

from webob import exc


from murano.api.v1 import request_statistics
from murano.common.helpers import token_sanitizer
from murano.common import wsgi
from murano.db.services import core_services
from murano.openstack.common import log as logging
from murano import utils


LOG = logging.getLogger(__name__)

API_NAME = 'Services'


def normalize_path(f):
    @func.wraps(f)
    def f_normalize_path(*args, **kwargs):
        if 'path' in kwargs:
            if kwargs['path']:
                kwargs['path'] = '/services/' + kwargs['path']
            else:
                kwargs['path'] = '/services'
        return f(*args, **kwargs)

    return f_normalize_path


class Controller(object):
    @request_statistics.stats_count(API_NAME, 'Index')
    @utils.verify_template
    @normalize_path
    def index(self, request, template_id, path):
        LOG.debug('Applications:Get <TemplateId: {0}, '
                  'Path: {1}>'.format(template_id, path))

        try:
            result = core_services.CoreServices.get_template_data(template_id,
                                                         path)
        except (KeyError, ValueError, AttributeError):
            raise exc.HTTPNotFound
        return result

    @request_statistics.stats_count(API_NAME, 'Show')
    @utils.verify_template
    @normalize_path
    def show(self, request, template_id, path):
        LOG.debug('Applications:Get <TemplateId: {0}, '
                  'Path: {1}>'.format(template_id, path))

        try:
            result = core_services.CoreServices.get_template_data(template_id,
                                                         path)
            if result is None:
                raise exc.HTTPNotFound
        except (KeyError, ValueError, AttributeError):
            raise exc.HTTPNotFound
        return result

    @request_statistics.stats_count(API_NAME, 'Create')
    @utils.verify_template
    @normalize_path
    def post(self, request, template_id, path, body):
        secure_data = token_sanitizer.TokenSanitizer().sanitize(body)
        LOG.debug('Applications:Post <TempId: {0}, Path: {2}, '
                  'Body: {1}>'.format(template_id, secure_data, path))

        post_data = core_services.CoreServices.post_application_data
        try:
            result = post_data(template_id, body, path)
        except (KeyError, ValueError):
            raise exc.HTTPNotFound
        return result

    @request_statistics.stats_count(API_NAME, 'Update')
    @utils.verify_template
    @normalize_path
    def put(self, request, template_id, path, body):
        LOG.debug('Applications:Put <TempId: {0}, Path: {2}, '
                  'Body: {1}>'.format(template_id, body, path))

        put_data = core_services.CoreServices.put_data
        session_id = request.context.session

        try:
            result = put_data(template_id, session_id, body, path)
        except (KeyError, ValueError):
            raise exc.HTTPNotFound
        return result

    @request_statistics.stats_count(API_NAME, 'Delete')
    @utils.verify_template
    @normalize_path
    def delete(self, request, template_id, path):
        LOG.debug('Applications:Put <TempId: {0}, '
                  'Path: {1}>'.format(template_id, path))
        delete_data = core_services.CoreServices.delete_template_data
        try:
            delete_data(template_id, path)
        except (KeyError, ValueError):
            raise exc.HTTPNotFound


def create_resource():
    return wsgi.Resource(Controller())
