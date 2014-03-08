#    Copyright (c) 2013 Mirantis, Inc.
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

"""
SQLAlchemy models for muranoapi data
"""
import anyjson

import sqlalchemy as sa
from sqlalchemy.ext import compiler as sa_compiler
from sqlalchemy.ext import declarative as sa_decl
from sqlalchemy import orm as sa_orm

from muranoapi.common import uuidutils
from muranoapi.db import session as db_session
from muranoapi.openstack.common import timeutils


BASE = sa_decl.declarative_base()


@sa_compiler.compiles(sa.BigInteger, 'sqlite')
def compile_big_int_sqlite(type_, compiler, **kw):
    return 'INTEGER'


class ModelBase(object):
    __protected_attributes__ = set(["created", "updated"])

    created = sa.Column(sa.DateTime, default=timeutils.utcnow,
                        nullable=False)
    updated = sa.Column(sa.DateTime, default=timeutils.utcnow,
                        nullable=False, onupdate=timeutils.utcnow)

    def save(self, session=None):
        """Save this object"""
        session = session or db_session.get_session()
        session.add(self)
        session.flush()

    def update(self, values):
        """dict.update() behaviour."""
        self.updated = timeutils.utcnow()
        for k, v in values.iteritems():
            self[k] = v

    def __setitem__(self, key, value):
        self.updated = timeutils.utcnow()
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def __iter__(self):
        self._i = iter(sa_orm.object_mapper(self).columns)
        return self

    def next(self):
        n = self._i.next().name
        return n, getattr(self, n)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def to_dict(self):
        dictionary = self.__dict__.copy()
        return dict((k, v) for k, v in dictionary.iteritems()
                    if k != '_sa_instance_state')


class JsonBlob(sa.TypeDecorator):
    impl = sa.Text

    def process_bind_param(self, value, dialect):
        return anyjson.serialize(value)

    def process_result_value(self, value, dialect):
        return anyjson.deserialize(value)


class Environment(BASE, ModelBase):
    """Represents a Environment in the metadata-store"""
    __tablename__ = 'environment'

    id = sa.Column(sa.String(32),
                   primary_key=True,
                   default=uuidutils.generate_uuid)
    name = sa.Column(sa.String(255), nullable=False)
    tenant_id = sa.Column(sa.String(32), nullable=False)
    version = sa.Column(sa.BigInteger, nullable=False, default=0)
    description = sa.Column(JsonBlob(), nullable=False, default={})
    networking = sa.Column(JsonBlob(), nullable=True, default={})

    sessions = sa_orm.relationship("Session", backref='environment',
                                   cascade='save-update, merge, delete')
    deployments = sa_orm.relationship("Deployment", backref='environment',
                                      cascade='save-update, merge, delete')

    def to_dict(self):
        dictionary = super(Environment, self).to_dict()
        del dictionary['description']
        return dictionary


class Session(BASE, ModelBase):
    __tablename__ = 'session'

    id = sa.Column(sa.String(32),
                   primary_key=True,
                   default=uuidutils.generate_uuid)
    environment_id = sa.Column(sa.String(32), sa.ForeignKey('environment.id'))

    user_id = sa.Column(sa.String(36), nullable=False)
    state = sa.Column(sa.String(36), nullable=False)
    description = sa.Column(JsonBlob(), nullable=False)
    version = sa.Column(sa.BigInteger, nullable=False, default=0)

    def to_dict(self):
        dictionary = super(Session, self).to_dict()
        del dictionary['description']
        #object relations may be not loaded yet
        if 'environment' in dictionary:
            del dictionary['environment']
        return dictionary


class Deployment(BASE, ModelBase):
    __tablename__ = 'deployment'

    id = sa.Column(sa.String(32),
                   primary_key=True,
                   default=uuidutils.generate_uuid)
    started = sa.Column(sa.DateTime, default=timeutils.utcnow, nullable=False)
    finished = sa.Column(sa.DateTime, default=None, nullable=True)
    description = sa.Column(JsonBlob(), nullable=False)
    environment_id = sa.Column(sa.String(32), sa.ForeignKey('environment.id'))

    statuses = sa_orm.relationship("Status", backref='deployment',
                                   cascade='save-update, merge, delete')

    def to_dict(self):
        dictionary = super(Deployment, self).to_dict()
        # del dictionary["description"]
        if 'statuses' in dictionary:
            del dictionary['statuses']
        if 'environment' in dictionary:
            del dictionary['environment']
        return dictionary


class Status(BASE, ModelBase):
    __tablename__ = 'status'

    id = sa.Column(sa.String(32),
                   primary_key=True,
                   default=uuidutils.generate_uuid)
    entity_id = sa.Column(sa.String(32), nullable=True)
    entity = sa.Column(sa.String(10), nullable=True)
    deployment_id = sa.Column(sa.String(32), sa.ForeignKey('deployment.id'))
    text = sa.Column(sa.String(), nullable=False)
    level = sa.Column(sa.String(32), nullable=False)
    details = sa.Column(sa.Text(), nullable=True)

    def to_dict(self):
        dictionary = super(Status, self).to_dict()
        #object relations may be not loaded yet
        if 'deployment' in dictionary:
            del dictionary['deployment']
        return dictionary


def register_models(engine):
    """
    Creates database tables for all models with the given engine
    """
    models = (Environment, Status, Session, Deployment)
    for model in models:
        model.metadata.create_all(engine)


def unregister_models(engine):
    """
    Drops database tables for all models with the given engine
    """
    models = (Environment, Status, Session, Deployment)
    for model in models:
        model.metadata.drop_all(engine)
