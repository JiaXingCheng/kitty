# -*- coding: utf-8 -*-
# Copyright (C) 2016 Cisco Systems, Inc. and/or its affiliates. All rights reserved.
#
# This file is part of Kitty.
#
# Kitty is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Kitty is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Kitty.  If not, see <http://www.gnu.org/licenses/>.

'''
Tests calculated fields
'''
from common import metaTest, BaseTestCase
from bitstring import Bits
import hashlib
from struct import unpack
from kitty.model import String, Static
from kitty.model import BitField, UInt32
from kitty.model import Clone, Size, SizeInBytes, Md5, Sha1, Sha224, Sha256, Sha384, Sha512
from kitty.model import ElementCount, IndexOf, Offset, AbsoluteOffset
from kitty.model import Container
from kitty.model import ENC_INT_BE
from kitty.core import KittyException


class CalculatedTestCase(BaseTestCase):
    __meta__ = True

    def setUp(self, cls=None):
        super(CalculatedTestCase, self).setUp(cls)
        self.depends_on_name = 'depends_on'
        self.depends_on_value = 'the_value'

    def calculate(self, field):
        '''
        :param field: field to base calculation on
        :return: calculated value
        '''
        raise NotImplemented

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, fuzzable=fuzzable, name='uut')

    def get_original_field(self):
        return String(self.depends_on_value, name=self.depends_on_name)

    @metaTest
    def testCalculatedAfterField(self):
        original_field = self.get_original_field()
        calculated_field = self.get_default_field()
        container = Container([original_field, calculated_field])
        expected = self.calculate(original_field)
        actual = calculated_field.render()
        self.assertEqual(expected, actual)
        while container.mutate():
            expected = self.calculate(original_field)
            actual = calculated_field.render()
            self.assertEqual(expected, actual)

    @metaTest
    def testCalculatedBeforeField(self):
        original_field = self.get_original_field()
        calculated_field = self.get_default_field()
        container = Container([calculated_field, original_field])
        expected = self.calculate(original_field)
        actual = calculated_field.render()
        self.assertEqual(expected, actual)
        while container.mutate():
            expected = self.calculate(original_field)
            actual = calculated_field.render()
            self.assertEqual(expected, actual)


class CloneTests(CalculatedTestCase):
    __meta__ = False

    def setUp(self, cls=Clone):
        super(CloneTests, self).setUp(cls)

    def calculate(self, field):
        return field.render()


class ElementCountTests(CalculatedTestCase):

    __meta__ = False

    def setUp(self, cls=ElementCount):
        super(ElementCountTests, self).setUp(cls)
        self.length = 32
        self.bit_field = BitField(value=0, length=self.length)

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, length=self.length, fuzzable=fuzzable, name='uut')

    def calculate(self, field):
        self.bit_field.set_current_value(len(field.get_rendered_fields()))
        return self.bit_field.render()

    def testContainerWithInternalContainer(self):
        container = Container(
            name=self.depends_on_name,
            fields=[
                String('abc'),
                String('def'),
                Container(
                    name='counts_as_one',
                    fields=[
                        String('ghi'),
                        String('jkl'),
                    ])
            ])
        uut = self.get_default_field()
        full = Container([container, uut])
        full.render()
        self.assertEqual(uut.render(), self.calculate(container))
        del full

    def testInternalContainer(self):
        internal_container = Container(
            name=self.depends_on_name,
            fields=[
                String('ghi', name='field3'),
                String('jkl', name='field4'),
            ])
        container = Container(
            name='this_doesnt_count',
            fields=[
                String('abc', name='field1'),
                String('def', name='field2'),
                internal_container
            ])
        uut = self.get_default_field()
        full = Container([container, uut])
        full.render()
        self.assertEqual(uut.render(), self.calculate(internal_container))
        del full


class IndexOfTestCase(CalculatedTestCase):

    __meta__ = False

    def setUp(self, cls=IndexOf):
        super(IndexOfTestCase, self).setUp(cls)
        self.length = 32
        self.bit_field = BitField(value=0, length=self.length)

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, length=self.length, fuzzable=fuzzable, name='uut')

    def calculate(self, field):
        rendered = field._enclosing.get_rendered_fields()
        if field in rendered:
            value = rendered.index(field)
        else:
            value = len(rendered)
        self.bit_field.set_current_value(value)
        return self.bit_field.render()

    def _testCorrectIndex(self, expected_index):
        field_list = [String('%d' % i) for i in range(20)]
        field_list[expected_index] = self.get_original_field()
        uut = self.get_default_field()
        t = Container(name='level1', fields=[uut, Container(name='level2', fields=field_list)])
        rendered = uut.render().tobytes()
        result = unpack('>I', rendered)[0]
        self.assertEqual(result, expected_index)
        del t

    def testCorrectIndexFirst(self):
        self._testCorrectIndex(0)

    def testCorrectIndexMiddle(self):
        self._testCorrectIndex(10)

    def testCorrectIndexLast(self):
        self._testCorrectIndex(19)

    def testFieldNotRenderedAlone(self):
        expected_index = 0
        uut = self.get_default_field()
        the_field = Static(name=self.depends_on_name, value='')
        t = Container(name='level1', fields=[uut, Container(name='level2', fields=the_field)])
        rendered = uut.render().tobytes()
        result = unpack('>I', rendered)[0]
        self.assertEqual(result, expected_index)
        del t

    def testFieldNotRenderedWithOtherFields(self):
        expected_index = 3
        uut = self.get_default_field()
        fields = [
            Static(name=self.depends_on_name, value=''),
            Static('field1'),
            Static('field2'),
            Static('field3'),
        ]
        t = Container(name='level1', fields=[uut, Container(name='level2', fields=fields)])
        rendered = uut.render().tobytes()
        result = unpack('>I', rendered)[0]
        self.assertEqual(result, expected_index)
        del t


class SizeTests(CalculatedTestCase):
    __meta__ = False

    def setUp(self, cls=Size, length=32):
        super(SizeTests, self).setUp(cls)
        self.bit_field = BitField(value=0, length=length)
        self.length = length

    def get_default_field(self, length=None, calc_func=None, fuzzable=False):
        if length is None:
            length = self.length
        if calc_func is None:
            return self.cls(self.depends_on_name, length=length, fuzzable=fuzzable, name='uut')
        else:
            return self.cls(self.depends_on_name, length=length, calc_func=calc_func, fuzzable=fuzzable, name='uut')

    def calculate(self, field, calc_func=None):
        value = field.render()
        if calc_func:
            val = calc_func(value)
        else:
            val = len(value.bytes)
        self.bit_field.set_current_value(val)
        return self.bit_field.render()

    def testCustomFuncValid(self):
        def func(x):
            return len(x)
        original_field = self.get_original_field()
        calculated_field = self.get_default_field(calc_func=func)
        container = Container([original_field, calculated_field])
        expected = self.calculate(original_field, calc_func=func)
        actual = calculated_field.render()
        self.assertEqual(expected, actual)
        while container.mutate():
            expected = self.calculate(original_field, calc_func=func)
            actual = calculated_field.render()
            self.assertEqual(expected, actual)

    def testInvalidLength0(self):
        with self.assertRaises(KittyException):
            self.cls(self.depends_on_name, length=0)

    def testInvalidLengthNegative(self):
        with self.assertRaises(KittyException):
            self.cls(self.depends_on_name, length=-3)

    def testSizeInclusiveAlone(self):
        self.length = 32
        container = Container(
            name=self.depends_on_name,
            fields=[
                self.get_default_field()
            ])
        rendered = container.render()
        self.assertEqual(len(rendered), self.length)
        self.assertEquals(unpack('>I', rendered.tobytes())[0], self.length / 8)


class SizeInBytesTest(CalculatedTestCase):
    __meta__ = False

    def setUp(self, cls=SizeInBytes, length=32):
        super(SizeInBytesTest, self).setUp(cls)
        self.bit_field = BitField(value=0, length=length)
        self.length = length

    def get_default_field(self, fuzzable=False):
        return self.cls(self.depends_on_name, length=self.length, fuzzable=fuzzable, name='uut')

    def calculate(self, field):
        value = field.render()
        self.bit_field.set_current_value(len(value.bytes))
        return self.bit_field.render()


class OffsetTests(BaseTestCase):
    __meta__ = False

    def setUp(self):
        super(OffsetTests, self).setUp(Offset)
        self.frm = None
        self.to = UInt32(name='to', value=1)
        self.uut_len = 32
        self.correction = 0
        self.encoder = ENC_INT_BE
        self.fuzzable = False
        self.name = 'uut'

    def get_uut(self):
        return self.cls(
            self.frm,
            self.to,
            self.uut_len,
            correction=self.correction,
            encoder=self.encoder,
            fuzzable=self.fuzzable,
            name=self.name
        )

    def testAbsoluteOffsetOfPostField(self):
        uut = self.get_uut()
        container = Container(name='container', fields=[uut, self.to])
        container.render()
        uut_rendered = uut.render()
        uut_val = unpack('>I', uut_rendered.tobytes())[0]
        self.assertEqual(len(uut_rendered), uut_val)
        self.assertEqual(32, uut_val)

    def testAbsoluteOffsetOfPostFieldFixed(self):
        uut = self.get_uut()
        container = Container(name='container', fields=[uut, self.to])
        container.render()
        uut_rendered = uut.render()
        uut_val = unpack('>I', uut_rendered.tobytes())[0]
        self.assertEqual(32, uut_val)

    def testAbsoluteOffsetOfPreFieldAtTheBeginning(self):
        uut = self.get_uut()
        container = Container(name='container', fields=[self.to, uut])
        container.render()
        uut_rendered = uut.render()
        uut_val = unpack('>I', uut_rendered.tobytes())[0]
        self.assertEqual(0, uut_val)

    def testAbsoluteOffsetOfPreFieldNotAtTheBeginning(self):
        uut = self.get_uut()
        pre_field = String(name='first', value='first')
        container = Container(name='container', fields=[pre_field, self.to, uut])
        while container.mutate():
            container.render()
            uut_rendered = uut.render()
            uut_val = unpack('>I', uut_rendered.tobytes())[0]
            self.assertEqual(len(pre_field.render()), uut_val)

    def testDefaultCorrectionFunctionIsBytes(self):
        self.correction = None
        uut = self.get_uut()
        pre_field = String(name='first', value='first')
        container = Container(name='container', fields=[pre_field, self.to, uut])
        while container.mutate():
            container.render()
            uut_rendered = uut.render()
            uut_val = unpack('>I', uut_rendered.tobytes())[0]
            self.assertEqual(len(pre_field.render().tobytes()), uut_val)

    def testCorrectionInt(self):
        self.correction = 5
        uut = self.get_uut()
        pre_field = String(name='first', value='first')
        container = Container(name='container', fields=[pre_field, self.to, uut])
        while container.mutate():
            container.render()
            uut_rendered = uut.render()
            uut_val = unpack('>I', uut_rendered.tobytes())[0]
            self.assertEqual(len(pre_field.render()) + 5, uut_val)


class AbsoluteOffsetTests(BaseTestCase):
    __meta__ = False

    def setUp(self):
        super(AbsoluteOffsetTests, self).setUp(AbsoluteOffset)
        self.to = UInt32(name='to', value=1)
        self.uut_len = 32
        self.correction = 0
        self.encoder = ENC_INT_BE
        self.fuzzable = False
        self.name = 'uut'

    def get_uut(self):
        return self.cls(
            self.to,
            self.uut_len,
            correction=self.correction,
            encoder=self.encoder,
            fuzzable=self.fuzzable,
            name=self.name
        )

    def testAbsoluteOffsetOfPostField(self):
        uut = self.get_uut()
        container = Container(name='container', fields=[uut, self.to])
        container.render()
        uut_rendered = uut.render()
        uut_val = unpack('>I', uut_rendered.tobytes())[0]
        self.assertEqual(len(uut_rendered), uut_val)
        self.assertEqual(32, uut_val)

    def testAbsoluteOffsetOfPostFieldFixed(self):
        uut = self.get_uut()
        container = Container(name='container', fields=[uut, self.to])
        container.render()
        uut_rendered = uut.render()
        uut_val = unpack('>I', uut_rendered.tobytes())[0]
        self.assertEqual(32, uut_val)

    def testAbsoluteOffsetOfPreFieldAtTheBeginning(self):
        uut = self.get_uut()
        container = Container(name='container', fields=[self.to, uut])
        container.render()
        uut_rendered = uut.render()
        uut_val = unpack('>I', uut_rendered.tobytes())[0]
        self.assertEqual(0, uut_val)

    def testAbsoluteOffsetOfPreFieldNotAtTheBeginning(self):
        uut = self.get_uut()
        pre_field = String(name='first', value='first')
        container = Container(name='container', fields=[pre_field, self.to, uut])
        while container.mutate():
            container.render()
            uut_rendered = uut.render()
            uut_val = unpack('>I', uut_rendered.tobytes())[0]
            self.assertEqual(len(pre_field.render()), uut_val)

    def testDefaultCorrectionFunctionIsBytes(self):
        self.correction = None
        uut = self.get_uut()
        pre_field = String(name='first', value='first')
        container = Container(name='container', fields=[pre_field, self.to, uut])
        while container.mutate():
            container.render()
            uut_rendered = uut.render()
            uut_val = unpack('>I', uut_rendered.tobytes())[0]
            self.assertEqual(len(pre_field.render().tobytes()), uut_val)

    def testCorrectionInt(self):
        self.correction = 5
        uut = self.get_uut()
        pre_field = String(name='first', value='first')
        container = Container(name='container', fields=[pre_field, self.to, uut])
        while container.mutate():
            container.render()
            uut_rendered = uut.render()
            uut_val = unpack('>I', uut_rendered.tobytes())[0]
            self.assertEqual(len(pre_field.render()) + 5, uut_val)


class HashTests(CalculatedTestCase):
    __meta__ = True

    def setUp(self, cls=None, hasher=None):
        super(HashTests, self).setUp(cls)
        self.hasher = hasher

    def calculate(self, field):
        value = field.render()
        digest = self.hasher(value.bytes).digest()
        return Bits(bytes=digest)


class Md5Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Md5Tests, self).setUp(Md5, hashlib.md5)


class Sha1Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha1Tests, self).setUp(Sha1, hashlib.sha1)


class Sha224Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha224Tests, self).setUp(Sha224, hashlib.sha224)


class Sha256Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha256Tests, self).setUp(Sha256, hashlib.sha256)


class Sha384Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha384Tests, self).setUp(Sha384, hashlib.sha384)


class Sha512Tests(HashTests):
    __meta__ = False

    def setUp(self):
        super(Sha512Tests, self).setUp(Sha512, hashlib.sha512)


