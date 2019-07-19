# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2019 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

"""
Tests for the SQL abstraction layer.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from relstorage.tests import TestCase

from .._sql import Table
from .._sql import HistoryVariantTable
from .._sql import Column
from .._sql import bindparam
from .._sql import DefaultDialect
from .._sql import OID
from .._sql import TID
from .._sql import State

current_object = Table(
    'current_object',
    Column('zoid', OID),
    Column('tid', TID)
)

object_state = Table(
    'object_state',
    Column('zoid', OID),
    Column('tid', TID),
    Column('state', State),
)

hp_object_and_state = current_object.natural_join(object_state)

objects = HistoryVariantTable(
    current_object,
    object_state,
)

object_and_state = HistoryVariantTable(
    hp_object_and_state,
    object_state
)

class TestTableSelect(TestCase):

    def test_simple_eq_select(self):
        table = object_state

        stmt = table.select().where(table.c.zoid == table.c.tid)

        self.assertEqual(
            str(stmt),
            'SELECT zoid, tid, state FROM object_state WHERE (zoid = tid)'
        )

    def test_simple_eq_select_and(self):

        table = object_state

        stmt = table.select().where(table.c.zoid == table.c.tid)

        self.assertEqual(
            str(stmt),
            'SELECT zoid, tid, state FROM object_state WHERE (zoid = tid)'
        )

        stmt = stmt.and_(table.c.zoid > 5)
        self.assertEqual(
            str(stmt),
            'SELECT zoid, tid, state FROM object_state WHERE ((zoid = tid AND zoid > %(param_0)s))'
        )

    def test_simple_eq_select_literal(self):
        table = object_state

        # This is a useless query
        stmt = table.select().where(table.c.zoid == 7)

        self.assertEqual(
            str(stmt),
            'SELECT zoid, tid, state FROM object_state WHERE (zoid = %(param_0)s)'
        )

        self.assertEqual(
            stmt.compiled().params,
            {'param_0': 7})

    def test_column_query_variant_table(self):
        stmt = objects.select(objects.c.tid, objects.c.zoid).where(
            objects.c.tid > bindparam('tid')
        )

        self.assertEqual(
            str(stmt),
            'SELECT tid, zoid FROM current_object WHERE (tid > %(tid)s)'
        )

    def test_natural_join(self):
        stmt = object_and_state.select(
            object_and_state.c.zoid, object_and_state.c.state
        ).where(
            object_and_state.c.zoid == object_and_state.bindparam('oid')
        )

        self.assertEqual(
            str(stmt),
            'SELECT zoid, state '
            'FROM current_object '
            'JOIN object_state '
            'USING (zoid, tid) WHERE (zoid = %(oid)s)'
        )

        class H(object):
            keep_history = False
            dialect = DefaultDialect()

        stmt = stmt.bind(H())

        self.assertEqual(
            str(stmt),
            'SELECT zoid, state '
            'FROM object_state '
            'WHERE (zoid = %(oid)s)'
        )

    def test_bind(self):
        select = objects.select(objects.c.tid, objects.c.zoid).where(
            objects.c.tid > bindparam('tid')
        )
        # Unbound we assume history
        self.assertEqual(
            str(select),
            'SELECT tid, zoid FROM current_object WHERE (tid > %(tid)s)'
        )

        class Context(object):
            dialect = DefaultDialect()
            keep_history = True

        context = Context()
        dialect = context.dialect
        select = select.bind(context)

        self.assertEqual(select.context, dialect)
        self.assertEqual(select.table.context, dialect)
        self.assertEqual(select._where.context, dialect)
        self.assertEqual(select._where.expression.context, dialect)
        # We take up its history setting
        self.assertEqual(
            str(select),
            'SELECT tid, zoid FROM current_object WHERE (tid > %(tid)s)'
        )

        # Bound to history-free we use history free
        context.keep_history = False
        select = select.bind(context)

        self.assertEqual(
            str(select),
            'SELECT tid, zoid FROM object_state WHERE (tid > %(tid)s)'
        )

    def test_bind_descriptor(self):
        class Context(object):
            keep_history = True
            dialect = DefaultDialect()
            select = objects.select(objects.c.tid, objects.c.zoid).where(
                objects.c.tid > bindparam('tid')
            )

        # Unbound we assume history
        self.assertEqual(
            str(Context.select),
            'SELECT tid, zoid FROM current_object WHERE (tid > %(tid)s)'
        )

        context = Context()
        context.keep_history = False
        self.assertEqual(
            str(context.select),
            'SELECT tid, zoid FROM object_state WHERE (tid > %(tid)s)'
        )

    def test_prepared_insert_values(self):
        stmt = current_object.insert(
            current_object.c.zoid
        )

        self.assertEqual(
            str(stmt),
            'INSERT INTO current_object(zoid) VALUES (%s)'
        )

        stmt = stmt.prepared()
        self.assertTrue(
            str(stmt).startswith('EXECUTE rs_prep_stmt')
        )

        stmt = stmt.compiled()
        self.assertRegex(
            stmt._prepare_stmt,
            r"PREPARE rs_prep_stmt_[0-9]* \(BIGINT\) AS.*"
        )
