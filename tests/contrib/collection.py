# -*- coding:utf-8 -*-
from __future__ import unicode_literals

import time
import unittest

from limpyd import fields
from limpyd.contrib.collection import ExtendedCollectionManager, SORTED_SCORE, DEFAULT_STORE_TTL
from limpyd.utils import unique_key
from limpyd.exceptions import *
from tests.indexes import RangeIndexTestModel

from ..base import LimpydBaseTest, test_database, skip_if_no_zrangebylex
from ..model import TestRedisModel, Boat as BaseBoat


class Group(TestRedisModel):
    namespace = 'contrib-collection'
    collection_manager = ExtendedCollectionManager

    id = fields.AutoPKField()
    name = fields.InstanceHashField(indexable=True)
    active = fields.InstanceHashField(indexable=True, default=1)
    public = fields.InstanceHashField(indexable=True, default=1)


class GroupsContainer(TestRedisModel):
    namespace = 'contrib-collection'
    groups_set = fields.SetField()
    groups_list = fields.ListField()
    groups_sortedset = fields.SortedSetField()


class BaseTest(LimpydBaseTest):

    def setUp(self):
        super(BaseTest, self).setUp()
        self.groups = [
            Group(name='foo'),
            Group(name='bar', public=0),
            Group(name='baz', active=0),
            Group(name='qux', active=0, public=0),
        ]


class CompatibilityTest(BaseTest):

    def test_extended_collection_should_work_as_simple_one(self):

        # test "all"
        all_pks = set(Group.collection())
        self.assertEqual(all_pks, {'1', '2', '3', '4'})

        # test "sort by"
        all_pks_by_name = list(Group.collection().sort(by='name', alpha=True))
        self.assertEqual(all_pks_by_name, ['2', '3', '1', '4'])

        # test "filter"
        active_pks = set(Group.collection(active=1))
        self.assertEqual(active_pks, {'1', '2'})
        first_group_pk = list(Group.collection(pk=1))
        self.assertEqual(first_group_pk, ['1', ])
        bad_groups = list(Group.collection(pk=10, active=1))
        self.assertEqual(bad_groups, [])

        # test "instances"
        public_groups = list(Group.collection(public=1).instances())
        self.assertEqual(len(public_groups), 2)
        public_groups_pks = set([g._pk for g in public_groups])
        self.assertEqual(public_groups_pks, {'1', '3'})

        # test "values"
        active_public_dicts = list(Group.collection(public=1, active=1)
                                        .values('name', 'active', 'public'))
        self.assertEqual(len(active_public_dicts), 1)
        self.assertEqual(active_public_dicts[0], {'name': 'foo', 'active': '1', 'public': '1'})

        # test "values_list"
        active_public_tuples = list(Group.collection(public=1, active=1)
                                         .values_list('name', 'active', 'public'))
        self.assertEqual(len(active_public_tuples), 1)
        self.assertEqual(active_public_tuples[0], ('foo', '1', '1'))
        active_names = list(Group.collection(active=1).values_list('name', flat=True)
                                                      .sort(by='name', alpha=True))
        self.assertEqual(len(active_names), 2)
        self.assertEqual(active_names, ['bar', 'foo'])

    @unittest.skipIf(*skip_if_no_zrangebylex)
    def test_range_index_should_work(self):
        class TextRangeIndexTestModelExtended(RangeIndexTestModel):
            collection_manager = ExtendedCollectionManager

        obj1 = TextRangeIndexTestModelExtended(name='foo', category='cat1')
        pk1 = obj1.pk.get()
        TextRangeIndexTestModelExtended(name='bar')
        obj3 = TextRangeIndexTestModelExtended(name='foobar', category='cat1')
        pk3 = obj3.pk.get()
        TextRangeIndexTestModelExtended(name='foobar', category='cat2')
        TextRangeIndexTestModelExtended(name='qux')

        data = set(TextRangeIndexTestModelExtended.collection(name__gte='foo', category='cat1'))
        self.assertEqual(data, {
            pk1,  # foo and cat1
            pk3,  # foobar and cat1
        })

    def test_sort_by_pk_should_work(self):

        class Plane2(TestRedisModel):
            my_pk = fields.PKField()
            name = fields.InstanceHashField()
            is_first = fields.InstanceHashField(indexable=True)

            collection_manager = ExtendedCollectionManager

        Plane2(pk=2, name='Concorde', is_first=0)
        Plane2(pk=1, name='Wright Flyer', is_first=1)
        Plane2(pk=10, name='Air Force One', is_first=0)

        pks = ['1', '2', '10']
        revpks = pks[::-1]
        self.assertListEqual(list(Plane2.collection().sort()), pks)
        self.assertListEqual(list(Plane2.collection().sort(desc=True)), revpks)
        self.assertListEqual(list(Plane2.collection().sort(by='pk')), pks)
        self.assertListEqual(list(Plane2.collection().sort(by='-pk')), revpks)
        self.assertListEqual(list(Plane2.collection().sort(by='my_pk')), pks)
        self.assertListEqual(list(Plane2.collection().sort(by='-my_pk')), revpks)

        pks = ['1', '10', '2']
        revpks = pks[::-1]
        self.assertListEqual(list(Plane2.collection().sort(alpha=True)), pks)
        self.assertListEqual(list(Plane2.collection().sort(alpha=True, desc=True)), revpks)
        self.assertListEqual(list(Plane2.collection().sort(by='pk', alpha=True)), pks)
        self.assertListEqual(list(Plane2.collection().sort(by='-pk', alpha=True)), revpks)
        self.assertListEqual(list(Plane2.collection().sort(by='my_pk', alpha=True)), pks)
        self.assertListEqual(list(Plane2.collection().sort(by='-my_pk', alpha=True)), revpks)

        pks = ['2', '10']
        revpks = pks[::-1]
        self.assertListEqual(list(Plane2.collection(is_first=0).sort()), pks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(desc=True)), revpks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='pk')), pks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='-pk')), revpks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='my_pk')), pks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='-my_pk')), revpks)

        pks = ['10', '2']
        revpks = pks[::-1]
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(alpha=True)), pks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(alpha=True, desc=True)), revpks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='pk', alpha=True)), pks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='-pk', alpha=True)), revpks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='my_pk', alpha=True)), pks)
        self.assertListEqual(list(Plane2.collection(is_first=0).sort(by='-my_pk', alpha=True)), revpks)

        for plane in Plane2.collection().instances():
            plane.delete()

        for pk in ('8123', '8674', '7402', '87'):
            Plane2(pk=pk)

        sorted_pks = list(Plane2.collection().sort())
        self.assertListEqual(sorted_pks, ['87', '7402', '8123', '8674'])

class FieldOrModelAsValueForSortAndFilterTest(BaseTest):

    class Query(TestRedisModel):
        namespace = 'FieldOrModelAsValueForSortAndFilterTest'
        collection_manager = ExtendedCollectionManager
        name = fields.InstanceHashField()
        active = fields.InstanceHashField()
        public = fields.InstanceHashField()

    def test_sort_should_accept_field_or_fieldname(self):
        # test with field name
        groups = list(Group.collection().sort(by='name', alpha=True)
                                        .values_list('name', flat=True))
        self.assertEqual(groups, ['bar', 'baz', 'foo', 'qux'])
        # test with field
        name_field = self.groups[0].name
        groups = list(Group.collection().sort(by=name_field, alpha=True)
                                        .values_list('name', flat=True))
        self.assertEqual(groups, ['bar', 'baz', 'foo', 'qux'])

    def test_filter_should_accept_field_from_same_model(self):
        # test using field from same model, without updating its value
        group = Group(name='foo')
        collection = Group.collection(name=group.name)
        attended = {self.groups[0]._pk, group._pk}
        self.assertEqual(set(collection), attended)

        # test using a field from same model, updating its value before running the collection
        group = Group(name='foo')
        collection = Group.collection(name=group.name)
        attended = {self.groups[1]._pk, group._pk}
        group.name.hset('bar')
        self.assertEqual(set(collection), attended)

    def test_filter_should_accept_field_from_other_model(self):
        # test using a field from another model, without updating its value
        query = FieldOrModelAsValueForSortAndFilterTest.Query(name='foo')
        collection = Group.collection(name=query.name)
        attended = {self.groups[0]._pk}
        self.assertEqual(set(collection), attended)

        # test using a field from another model, updating its value before running the collection
        query = FieldOrModelAsValueForSortAndFilterTest.Query(name='foo')
        collection = Group.collection(name=query.name)
        attended = {self.groups[1]._pk}
        query.name.hset('bar')
        self.assertEqual(set(collection), attended)

        # test using a field from another model, really creating the object later
        query = FieldOrModelAsValueForSortAndFilterTest.Query()
        collection = Group.collection(name=query.name)
        attended = {self.groups[2]._pk}
        query.name.hset('baz')
        self.assertEqual(set(collection), attended)

    def test_filter_should_accept_pkfield_or_pkvalue(self):
        group = Group()
        # pass the pk, but value will be get when calling the collection
        collection = Group.collection(pk=group.pk)
        group.name.hset('aaa')  # create a pk for the object
        attended = {group.pk.get()}
        self.assertEqual(set(collection), attended)

    def test_filter_should_accept_instance_as_value(self):
        group = Group(name='foo')
        collection = Group.collection(pk=group)
        attended = {group._pk}
        self.assertEqual(set(collection), attended)


class FilterTest(BaseTest):

    def test_filter_method_should_add_filter(self):
        # test with one call
        collection = Group.collection(active=1).filter(public=1)
        self.assertEqual(set(collection), {'1'})
        # test with two calls
        collection = Group.collection(active=1)
        self.assertEqual(set(collection), {'1', '2'})
        collection.filter(public=1)
        self.assertEqual(set(collection), {'1'})
        # test with a pk
        collection = Group.collection(active=1).filter(pk=2)
        self.assertEqual(set(collection), {'2'})
        collection = Group.collection(active=1).filter(id=1)
        self.assertEqual(set(collection), {'1'})
        collection = Group.collection(active=1).filter(id=10)
        self.assertEqual(set(collection), set())
        # test with pk, then filter with other
        collection = Group.collection(pk=2).filter(active=1)
        self.assertEqual(set(collection), {'2'})

    def test_filter_calls_could_be_chained(self):
        collection = Group.collection().filter(active=1).filter(public=1).filter(pk=1)
        self.assertEqual(set(collection), {'1'})

    def test_redefining_filter_should_return_empty_result(self):
        collection = Group.collection(active=1).filter(active=0)
        self.assertEqual(set(collection), set())

    def test_filter_should_returns_the_collection(self):
        collection1 = Group.collection(active=1)
        collection2 = collection1.filter(active=0)
        self.assertEqual(collection1, collection2)

    def test_filter_should_accept_pks(self):
        collection = Group.collection(pk=1)
        self.assertEqual(set(collection), {'1'})
        collection.filter(id=1)
        self.assertEqual(set(collection), {'1'})
        collection.filter(pk=2)
        self.assertEqual(set(collection), set())


class IntersectTest(BaseTest):

    redis_zinterstore = None
    redis_sinterstore = None

    @staticmethod
    def zinterstore(*args, **kwargs):
        """
        Store arguments and call the real zinterstore command
        """
        IntersectTest.last_interstore_call = {
            'command': 'zinterstore',
            'sets': args[1]
        }
        return IntersectTest.redis_zinterstore(*args, **kwargs)

    @staticmethod
    def sinterstore(*args, **kwargs):
        """
        Store arguments and call the real sinterstore command
        """
        IntersectTest.last_interstore_call = {
            'command': 'sinterstore',
            'sets': args[1]
        }
        return IntersectTest.redis_sinterstore(*args, **kwargs)

    def setUp(self):
        """
        Update the redis zinterstore and sinterstore commands to be able to
        store locally arguments for testing them just after the commands are
        called. Store the original command to call it after logging, and to
        restore it in tearDown.
        """
        super(IntersectTest, self).setUp()
        IntersectTest.last_interstore_call = {'command': None, 'sets': [], }
        IntersectTest.redis_zinterstore = self.connection.zinterstore
        self.connection.zinterstore = IntersectTest.zinterstore
        IntersectTest.redis_sinterstore = self.connection.sinterstore
        self.connection.sinterstore = IntersectTest.sinterstore

    def tearDown(self):
        """
        Restore the zinterstore and sinterstore previously updated in setUp.
        """
        self.connection.zinterstore = IntersectTest.redis_zinterstore
        self.connection.sinterstore = IntersectTest.redis_sinterstore
        super(IntersectTest, self).tearDown()

    def test_intersect_should_accept_set_key_as_string(self):
        set_key = unique_key(self.connection)
        self.connection.sadd(set_key, 1, 2)
        collection = set(Group.collection().intersect(set_key))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        set_key = unique_key(self.connection)
        self.connection.sadd(set_key, 1, 2, 10, 50)
        collection = set(Group.collection().intersect(set_key))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_accept_sortedset_key_as_string(self):
        zset_key = unique_key(self.connection)
        self.connection.zadd(zset_key, 1.0, 1, 2.0, 2)
        collection = set(Group.collection().intersect(zset_key))
        self.assertEqual(self.last_interstore_call['command'], 'zinterstore')
        self.assertEqual(collection, {'1', '2'})

        zset_key = unique_key(self.connection)
        self.connection.zadd(zset_key, 1.0, 1, 2.0, 2, 10.0, 10, 50.0, 50)
        collection = set(Group.collection().intersect(zset_key))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_accept_list_key_as_string(self):
        list_key = unique_key(self.connection)
        self.connection.lpush(list_key, 1, 2)
        collection = set(Group.collection().intersect(list_key))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        list_key = unique_key(self.connection)
        self.connection.lpush(list_key, 1, 2, 10, 50)
        collection = set(Group.collection().intersect(list_key))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_not_accept_string_key_as_string(self):
        str_key = unique_key(self.connection)
        self.connection.set(str_key, 'foo')
        with self.assertRaises(ValueError):
            set(Group.collection().intersect(str_key))

    def test_intersect_should_not_accept_hkey_key_as_string(self):
        hash_key = unique_key(self.connection)
        self.connection.hset(hash_key, 'foo', 'bar')
        with self.assertRaises(ValueError):
            set(Group.collection().intersect(hash_key))

    def test_intersect_should_consider_non_existent_key_as_set(self):
        no_key = unique_key(self.connection)
        collection = set(Group.collection().intersect(no_key))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, set())

    def test_intersect_should_accept_set(self):
        collection = set(Group.collection().intersect({1, 2}))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        collection = set(Group.collection().intersect({1, 2, 10, 50}))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_accept_list(self):
        collection = set(Group.collection().intersect([1, 2]))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        collection = set(Group.collection().intersect([1, 2, 10, 50]))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_accept_tuple(self):
        collection = set(Group.collection().intersect((1, 2)))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        collection = set(Group.collection().intersect((1, 2, 10, 50)))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_accept_setfield(self):
        container = GroupsContainer()

        container.groups_set.sadd(1, 2)
        collection = set(Group.collection().intersect(container.groups_set))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        container.groups_set.sadd(10, 50)
        collection = set(Group.collection().intersect(container.groups_set))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_accept_listfield_without_scripting(self):
        container = GroupsContainer()

        container.groups_list.lpush(1, 2)
        collection = set(Group.collection().intersect(container.groups_list))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        container.groups_list.lpush(10, 50)
        collection = set(Group.collection().intersect(container.groups_list))
        self.assertEqual(collection, {'1', '2'})

    @unittest.skipUnless(test_database.support_scripting(), "Redis scripting not available")
    def test_intersect_should_accept_listfield_via_scripting(self):
        container = GroupsContainer()

        container.groups_list.lpush(1, 2)
        collection = set(Group.collection().intersect(container.groups_list))
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        self.assertEqual(collection, {'1', '2'})

        container.groups_list.lpush(10, 50)
        collection = set(Group.collection().intersect(container.groups_list))
        self.assertEqual(collection, {'1', '2'})

    def test_intersect_should_accept_sortedsetfield(self):
        container = GroupsContainer()

        container.groups_sortedset.zadd(1.0, 1, 2.0, 2)
        collection = set(Group.collection().intersect(container.groups_sortedset))
        self.assertEqual(collection, {'1', '2'})

        container.groups_sortedset.zadd(10.0, 10, 50.0, 50)
        collection = set(Group.collection().intersect(container.groups_sortedset))
        self.assertEqual(collection, {'1', '2'})

    def test_passing_sortedset_in_intersect_use_zinterstore(self):
        container = GroupsContainer()
        container.groups_sortedset.zadd(1.0, 1, 2.0, 2)
        collection = Group.collection().intersect(container.groups_sortedset)

        # execute the collection
        result = list(collection)
        # check that we called an interstore
        self.assertEqual(self.last_interstore_call['command'], 'zinterstore')
        # check the intersection is done with the sorted set AND the whole
        # collection, because we have no filters
        self.assertIn(Group.get_field('pk').collection_key,
                      self.last_interstore_call['sets'])
        self.assertEqual(result, ['1', '2'])

        # add a filter to the collection
        collection.filter(public=1)
        # execute the collection
        result = list(collection)
        # check that we called an interstore
        self.assertEqual(self.last_interstore_call['command'], 'zinterstore')
        # check the intersection is not done with the whole collection, but
        # only the sorted set and the set from the filter
        self.assertNotIn(Group.get_field('pk').collection_key,
                         self.last_interstore_call['sets'])
        self.assertEqual(result, ['1', ])

    def test_intersect_should_raise_if_unsupported_type(self):
        # unsupported type
        with self.assertRaises(ValueError):
            Group.collection().intersect({})
        # unbound MultiValuesField
        with self.assertRaises(ValueError):
            Group.collection().intersect(GroupsContainer.get_field('groups_set'))
        with self.assertRaises(ValueError):
            Group.collection().intersect(GroupsContainer.get_field('groups_list'))
        with self.assertRaises(ValueError):
            Group.collection().intersect(GroupsContainer.get_field('groups_sortedset'))

    def test_intersect_can_be_called_many_times(self):
        collection = set(Group.collection().intersect([1, 2, 3, 10]).intersect([2, 3, 50]))
        self.assertEqual(collection, {'2', '3'})

    def test_intersect_can_be_called_with_filter(self):
        collection = Group.collection(active=1).filter(public=1).intersect([1, 2, 3, 10])
        self.assertEqual(set(collection), {'1'})
        self.assertEqual(self.last_interstore_call['command'], 'sinterstore')
        collection = collection.intersect([2, 3, 50])
        self.assertEqual(set(collection), set())

    def test_intersect_should_returns_the_collection(self):
        collection1 = Group.collection(active=1)
        collection2 = collection1.intersect([1, 2])
        self.assertEqual(collection1, collection2)

    def test_slicing_sortedset(self):
        container = GroupsContainer()
        container.groups_sortedset.zadd(1.0, 1, 2.0, 2, 3.0, 3, 4.0, 4)

        self.assertSlicingIsCorrect(
            collection=Group.collection().intersect(container.groups_sortedset),
            check_data=[str(val) for val in range(1, 5)],
        )


class SortByScoreTest(BaseTest):
    def setUp(self):
        super(SortByScoreTest, self).setUp()
        self.container = GroupsContainer()
        self.container.groups_sortedset.zadd(1000, 1, 200, 2, 3000, 3, 40, 4)
        self.sorted_pks = ['4', '2', '1', '3']
        self.reversed_sorted_pks = list(reversed(self.sorted_pks))
        self.active_sorted_pks = ['2', '1']
        self.reversed_active_sorted_pks = list(reversed(self.active_sorted_pks))

    def test_sort_by_sortedset(self):
        collection = Group.collection()

        unsorted = set(collection)
        self.assertEqual(unsorted, set(self.sorted_pks))

        sorted_by_score = list(collection.sort(by_score=self.container.groups_sortedset))
        self.assertEqual(sorted_by_score, self.sorted_pks)

        sorted_by_reverse_score = list(collection.sort(by_score=self.container.groups_sortedset,
                                                       desc=True))
        self.assertEqual(sorted_by_reverse_score, self.reversed_sorted_pks)

    def test_sort_by_sortedset_with_slice(self):
        # will compare slicing from the collection to a real python list

        collection = Group.collection().sort(by_score=self.container.groups_sortedset)

        # will be used to compare result from redis to result from real list
        test_list = ['4', '2', '1', '3']

        # check we have the correct dataset
        assert list(collection) == test_list, 'Wrong dataset for this test'

        limit = 3
        total, optimized, not_optimized = 0, 0, 0
        for start in list(range(-limit, limit+1)) + [None]:
            for stop in list(range(-limit, limit+1)) + [None]:
                for step in range(-limit, limit+1):
                    if not step: continue
                    with self.subTest(Start=start, Stop=stop, step=step):
                        total += 1
                        self.assertEqual(
                            list(collection[start:stop:step]),
                            test_list[start:stop:step],
                            'Unexpected result for `%s:%s:%s`' % (
                                '' if start is None else start,
                                '' if stop is None else stop,
                                '' if step is None else step,
                            )
                        )
                        if collection._optimized_slicing:
                            optimized += 1
                        else:
                            not_optimized += 1

        self.assertGreaterEqual(optimized * 100.0 / total, 65,
                                "Less than 65% slicing resulted in non-optimized calls")

    def test_sort_by_sortedset_with_index(self):
        # will compare indexing from the collection to a real python list

        collection = Group.collection().sort(by_score=self.container.groups_sortedset)

        # will be used to compare result from redis to result from real list
        test_list = ['4', '2', '1', '3']

        # check we have the correct dataset
        assert list(collection) == test_list, 'Wrong dataset for this test'

        limit = 3
        for index in range(-limit, limit+1):
            with self.subTest(index=index):
                try:
                    expected = test_list[index]
                except IndexError:
                    with self.assertRaises(IndexError):
                        collection[index]
                else:
                    self.assertEqual(collection[index], expected)

    def test_sort_by_sortedset_with_filter(self):
        collection = Group.collection(active=1)

        sorted_by_score = list(collection.sort(by_score=self.container.groups_sortedset))
        self.assertEqual(sorted_by_score, self.active_sorted_pks)

        sorted_by_reverse_score = list(collection.sort(by_score=self.container.groups_sortedset,
                                                       desc=True))
        self.assertEqual(sorted_by_reverse_score, self.reversed_active_sorted_pks)

        with_smallest_score = collection.sort(by_score=self.container.groups_sortedset)[0]
        self.assertEqual(with_smallest_score, self.active_sorted_pks[0])

        with_bigger_score = collection.sort(by_score=self.container.groups_sortedset,
                                            desc=True)[0]
        self.assertEqual(with_bigger_score, self.reversed_active_sorted_pks[0])

    def test_sort_by_sortedset_could_retrieve_instances(self):
        collection = Group.collection(active=1).instances()

        sorted_by_score_instances = list(collection.sort(by_score=self.container.groups_sortedset))
        self.assertEqual(len(sorted_by_score_instances), len(self.active_sorted_pks))

        sorted_by_score_pks = [g._pk for g in sorted_by_score_instances]
        self.assertEqual(sorted_by_score_pks, self.active_sorted_pks)

    def test_sort_by_sortedset_could_retrieve_values(self):
        collection = Group.collection(active=1).values('name', 'active', 'public')

        sorted_by_score_dicts = list(collection.sort(by_score=self.container.groups_sortedset))
        self.assertEqual(len(sorted_by_score_dicts), len(self.active_sorted_pks))
        self.assertEqual(sorted_by_score_dicts[0], {'name': 'bar', 'active': '1', 'public': '0'})

    def test_sort_by_sortedset_could_retrieve_values_list(self):
        collection = Group.collection(active=1)

        sorted_by_score_tuples = list(collection.values_list('name', 'active', 'public')
                                                .sort(by_score=self.container.groups_sortedset))
        self.assertEqual(len(sorted_by_score_tuples), len(self.active_sorted_pks))
        self.assertEqual(sorted_by_score_tuples[0], ('bar', '1', '0'))

        sorted_by_score_names = list(collection.values_list('name', flat=True)
                                               .sort(by_score=self.container.groups_sortedset))
        self.assertEqual(sorted_by_score_names, ['bar', 'foo'])

    def test_sort_by_sortedset_should_work_without_filter(self):
        collection = Group.collection().sort(by_score=self.container.groups_sortedset)
        self.assertEqual(list(collection), self.sorted_pks)
        sorted_by_score_names = list(collection.values_list('name', flat=True))
        self.assertEqual(sorted_by_score_names, ['qux', 'bar', 'foo', 'baz'])

        collection = Group.collection().sort(by_score=self.container.groups_sortedset)
        self.assertEqual(collection[0:2], self.sorted_pks[0:2])
        sorted_by_score_names = collection.values_list('name', flat=True)[0:2]
        self.assertEqual(sorted_by_score_names, ['qux', 'bar'])

    def test_sort_by_sortedset_should_work_with_pk(self):
        # only pk
        collection = Group.collection(pk=1).sort(by_score=self.container.groups_sortedset)
        self.assertEqual(list(collection), ['1'])
        sorted_by_score_names = list(collection.values_list('name', flat=True))
        self.assertEqual(sorted_by_score_names, ['foo'])

        # pk and matching filter
        collection = Group.collection(pk=1, active=1).sort(
                                                        by_score=self.container.groups_sortedset)
        self.assertEqual(list(collection), ['1'])
        sorted_by_score_names = list(collection.values_list('name', flat=True))
        self.assertEqual(sorted_by_score_names, ['foo'])

        # pk and not matching filter
        collection = Group.collection(pk=1, active=0).sort(
                                                        by_score=self.container.groups_sortedset)
        self.assertEqual(list(collection), [])
        sorted_by_score_names = list(collection.values_list('name', flat=True))
        self.assertEqual(sorted_by_score_names, [])

        # pk and slice
        collection = Group.collection(pk=1).sort(by_score=self.container.groups_sortedset)
        self.assertEqual(collection[0:2], ['1'])
        sorted_by_score_names = collection.values_list('name', flat=True)[0:2]
        self.assertEqual(sorted_by_score_names, ['foo'])

    def test_score_should_be_retrieved_in_values(self):
        # test values
        collection = Group.collection(active=1).values('name', SORTED_SCORE).sort(
                                                        by_score=self.container.groups_sortedset)
        self.assertEqual(list(collection), [
            {'name': 'bar', SORTED_SCORE: '200.0'},
            {'name': 'foo', SORTED_SCORE: '1000.0'},
        ])

        # tests values_list
        collection = Group.collection(active=1).values_list('name', SORTED_SCORE).sort(
                                                        by_score=self.container.groups_sortedset)
        self.assertEqual(list(collection), [('bar', '200.0'), ('foo', '1000.0')])

        # test without sorting by score
        collection = Group.collection(active=1).values_list('name', SORTED_SCORE)
        self.assertEqual(set(collection), {('bar', None), ('foo', None)})

        # test with pk
        collection = Group.collection(pk=1).values('name', SORTED_SCORE).sort(
                                                        by_score=self.container.groups_sortedset)
        self.assertEqual(list(collection), [{'name': 'foo', SORTED_SCORE: '1000.0'}])


class StoreTest(BaseTest):

    def test_calling_store_should_return_a_new_collection(self):
        collection = Group.collection(active=1).sort(by='-name', alpha=True)
        stored_collection = collection.store()
        self.assertNotEqual(collection, stored_collection)
        self.assertEqual(list(collection), list(stored_collection))

    def test_ttl_of_stored_collection_should_be_set(self):
        collection = Group.collection(active=1).sort(by='-name', alpha=True)

        # default ttl
        stored_collection = collection.store()
        self.assertTrue(0 <= self.connection.ttl(stored_collection.stored_key) <= DEFAULT_STORE_TTL)
        self.assertTrue(self.connection.exists(stored_collection.stored_key))

        # no ttl
        stored_collection = collection.store(ttl=None)
        self.assertEqual(self.connection.ttl(stored_collection.stored_key), -1)
        self.assertTrue(self.connection.exists(stored_collection.stored_key))

        # test expire
        stored_collection = collection.store(ttl=1)
        self.assertTrue(0 <= self.connection.ttl(stored_collection.stored_key) <= 1)
        time.sleep(1.1)
        self.assertFalse(self.connection.exists(stored_collection.stored_key))

    def test_stored_key_should_be_the_given_one_if_set(self):
        collection = Group.collection(active=1).sort(by='-name', alpha=True)
        stored_collection = collection.store(key='mycollection')
        self.assertEqual(stored_collection.stored_key, 'mycollection')
        self.assertTrue(0 <= self.connection.ttl('mycollection') <= DEFAULT_STORE_TTL)
        self.assertTrue(self.connection.exists('mycollection'))

    def test_stored_collection_should_raise_if_key_expired(self):
        collection = Group.collection(active=1).sort(by='-name', alpha=True)

        # try with short ttl
        stored_collection = collection.store(ttl=1)
        time.sleep(1.1)
        with self.assertRaises(DoesNotExist):
            list(stored_collection)

        # try by deleting the key
        stored_collection = collection.store()
        self.connection.delete(stored_collection.stored_key)
        with self.assertRaises(DoesNotExist):
            list(stored_collection)

    def test_stored_call_should_be_faster(self):
        collection = Group.collection(active=1, public=1).intersect([1, 2, 3, 5, 7, 8, 10]).sort(
                                                                            by='-name', alpha=True)

        commands_before = self.count_commands()
        time_before = time.time()
        list(collection)
        default_duration = time.time() - time_before
        default_commands = self.count_commands() - commands_before

        stored_collection = collection.store()

        commands_before = self.count_commands()
        time_before = time.time()
        list(stored_collection)
        stored_duration = time.time() - time_before
        stored_commands = self.count_commands() - commands_before

        self.assertTrue(default_duration > stored_duration)
        self.assertTrue(default_commands > stored_commands)

        with self.assertNumCommands(2):
            # 2 commands: one to check key existence, one for the lrange
            list(stored_collection)

    def test_stored_collection_could_be_filtered(self):
        # but it's not recommanded as we have to convert the list into a set
        collection = Group.collection(active=1)
        stored_collection = collection.store()
        public_groups = list(stored_collection.filter(public=1))
        self.assertEqual(public_groups, ['1'])

    def test_stored_collection_should_accept_values_or_instances(self):
        collection = Group.collection(active=1)
        stored_collection = collection.store()

        instances = list(stored_collection.instances())
        self.assertEqual(len(instances), 2)
        self.assertEqual(instances[0]._pk, '1')

        dicts = list(stored_collection.values('pk', 'name'))
        self.assertEqual(len(dicts), 2)
        self.assertEqual(dicts[0], {'pk': '1', 'name': 'foo'})

        tuples = list(stored_collection.values_list('pk', 'name'))
        self.assertEqual(len(tuples), 2)
        self.assertEqual(tuples[0], ('1', 'foo'))

    def test_stored_collection_could_be_stored(self):
        collection = Group.collection(active=1)
        stored_collection = collection.store()
        stored_collection.filter(public=1)
        final_collection = stored_collection.store()
        result = self.connection.lrange(final_collection.stored_key, 0, -1)
        self.assertEqual(result, ['1'])

    def test_stored_collection_could_be_sorted(self):
        collection = Group.collection(active=1)
        stored_collection = collection.store()
        sorted_groups = list(stored_collection.sort(by='name', alpha=True))
        self.assertEqual(sorted_groups, ['2', '1'])

    def test_stored_collection_could_be_empty(self):
        collection = Group.collection(active=1, name='foobar')
        stored_collection = collection.store()
        self.assertEqual(list(stored_collection), [])

    def test_slicing_stored_collection(self):

        self.assertSlicingIsCorrect(
            collection=Group.collection().store(ttl=6000),
            check_data=[str(val) for val in range(1, 5)],
        )


class LenTest(BaseTest):
    def test_len_should_work_with_sortedsets(self):
        container = GroupsContainer()
        container.groups_sortedset.zadd(1.0, 1, 2.0, 2)
        collection = Group.collection().intersect(container.groups_sortedset)
        collection.sort(by='name')  # to fail if sort called, becase alpha not set
        self.assertEqual(len(collection), 2)

    def test_len_should_work_with_stored_collection(self):
        collection = Group.collection(active=1)
        stored_collection = collection.store().sort(by='name')
        self.assertEqual(len(stored_collection), 2)

    def test_len_should_work_with_values(self):
        collection = Group.collection(active=1).sort(by='name').values()
        self.assertEqual(len(collection), 2)


class Boat(BaseBoat):
    namespace = 'contrib-collection'
    collection_manager = ExtendedCollectionManager


class BaseValuesTest(BaseTest):
    def setUp(self):
        super(BaseTest, self).setUp()
        self.assertEqual(set(Boat.collection()), set())
        self.boat1 = Boat(name="Pen Duick I", length=15.1, launched=1898)
        self.boat2 = Boat(name="Pen Duick II", length=13.6, launched=1964)
        self.boat3 = Boat(name="Pen Duick III", length=17.45, launched=1966)
        self.boat4 = Boat(name="Rainbow Warrior I", power="engine", length=40, launched=1955)


class ValuesTest(BaseValuesTest):
    def test_values_should_return_a_list_of_dicts(self):
        boats = list(Boat.collection().values('pk', 'name', 'launched'))
        self.assertEqual(len(boats), 4)
        for boat in boats:
            self.assertTrue(isinstance(boat, dict))
            self.assertEqual(set(boat.keys()), {'pk', 'name', 'launched'})
            test_boat = Boat(boat['pk'])
            self.assertEqual(test_boat.name.get(), boat['name'])
            self.assertEqual(test_boat.launched.get(), boat['launched'])

    def test_values_without_argument_returns_all_fields(self):
        boats = list(Boat.collection().values())
        self.assertEqual(len(boats), 4)
        self.assertTrue(isinstance(boats[0], dict))
        self.assertEqual(set(boats[0].keys()), {'pk', 'name', 'power', 'launched', 'length'})

    def test_values_should_only_accept_simple_fields(self):
        with self.assertRaises(ValueError):
            # test a field that does not exist
            Boat.collection().values('foo')

        class BoatWithSet(Boat):
            passengers = fields.SetField()

        with self.assertRaises(ValueError):
            # test a field that is not a *simple* field
            Boat.collection().values('passengers')

    def test_values_should_accept_pk(self):
        #... but pk only has no advantage over simple collection result
        boats = list(Boat.collection(pk=self.boat1._pk).values('pk'))
        self.assertEqual(boats[0]['pk'], self.boat1._pk)

        class BoatWithNewPk(Boat):
            id = fields.AutoPKField()
        boat = BoatWithNewPk(name="Pen Duick I")

        boats = list(BoatWithNewPk.collection(pk=boat._pk).values('pk'))
        self.assertFalse('id' in boats[0])
        self.assertEqual(boats[0]['pk'], boat._pk)

        boats = list(BoatWithNewPk.collection(pk=boat._pk).values('id'))
        self.assertFalse('pk' in boats[0])
        self.assertEqual(boats[0]['id'], boat._pk)

    def test_call_to_primary_keys_should_cancel_values(self):
        boats = set(Boat.collection().values('pk', 'name', 'launched').primary_keys())
        self.assertEqual(boats, {'1', '2', '3', '4'})


class ValuesListTest(BaseValuesTest):
    def test_values_list_should_return_a_list_of_tuples(self):
        boats = list(Boat.collection().values_list('pk', 'name', 'launched'))
        self.assertEqual(len(boats), 4)
        for boat in boats:
            self.assertTrue(isinstance(boat, tuple))
            self.assertTrue(len(boat), 3)
            test_boat = Boat(boat[0])
            self.assertEqual(test_boat.name.get(), boat[1])
            self.assertEqual(test_boat.launched.get(), boat[2])

    def test_values_list_without_argument_returns_all_fields(self):
        boats = list(Boat.collection().values_list())
        self.assertEqual(len(boats), 4)
        self.assertTrue(isinstance(boats[0], tuple))
        self.assertEqual(len(boats[0]), 5)
        test_boat = Boat(boats[0][0])
        self.assertEqual(test_boat.name.get(), boats[0][1])
        self.assertEqual(test_boat.power.hget(), boats[0][2])
        self.assertEqual(test_boat.launched.get(), boats[0][3])
        self.assertEqual(test_boat.length.get(), boats[0][4])

    def test_values_list_should_only_accept_simple_fields(self):
        with self.assertRaises(ValueError):
            # test a field that does not exist
            Boat.collection().values_list('foo')

        class BoatWithSet(Boat):
            namespace = Boat.namespace + 'values_list'
            passengers = fields.SetField()

        with self.assertRaises(ValueError):
            # test a field that is not a *simple* field
            Boat.collection().values_list('passengers')

    def test_values_list_should_accept_pk(self):
        #... but pk only has no advantage over simple collection result
        boats = list(Boat.collection(pk=self.boat1._pk).values_list('pk'))
        self.assertEqual(boats[0][0], self.boat1._pk)

        class BoatWithNewPk(Boat):
            namespace = Boat.namespace + 'values_list'
            id = fields.AutoPKField()
        boat = BoatWithNewPk(name="Pen Duick I")
        boats = list(BoatWithNewPk.collection(pk=boat._pk).values_list('pk'))
        self.assertEqual(boats[0][0], boat._pk)

        boats = list(BoatWithNewPk.collection(pk=boat._pk).values_list('id'))
        self.assertEqual(boats[0][0], boat._pk)

    def test_flat_argument_should_return_flat_list(self):
        names = list(Boat.collection().values_list('name', flat=True))
        self.assertTrue(isinstance(names, list))
        self.assertEqual(names, [self.boat1.name.get(), self.boat2.name.get(),
                                 self.boat3.name.get(), self.boat4.name.get(), ])

    def test_flat_argument_should_be_refused_if_many_fields(self):
        with self.assertRaises(ValueError):
            Boat.collection().values_list('name', 'length', flat=True)

        with self.assertRaises(ValueError):
            Boat.collection().values_list(flat=True)

    def test_call_to_primary_keys_should_cancel_values_list(self):
        boats = set(Boat.collection().values_list('pk', 'name', 'launched').primary_keys())
        self.assertEqual(boats, {'1', '2', '3', '4'})
        boats = set(Boat.collection().values_list('name', flat=True).primary_keys())
        self.assertEqual(boats, {'1', '2', '3', '4'})
