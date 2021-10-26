from inspect import signature
from numbers import Number
from typing import Iterable
from dispatchio import dispatchio
import pytest


@dispatchio
def func_test(a:int, b:float, c=None, **kwargs): return 1

@func_test.register
def _(a: float, g:float): return 2

@func_test.register
def _(a: Number, **kwargs): return 6


@func_test.register
def _(a: Number, g:Number): return 3

@func_test.register
def _(a: Iterable[Number]): return 4

@func_test.register
def _(b: Iterable): return 5


def test_1():
    assert(func_test(1,1.0) == 1)
    assert(func_test(1,1.0,"dfdf", x="b") == 1)

def test_4():
    assert(func_test([10,10,10]) == 4)
    with pytest.raises(Exception):
        assert(func_test([None,10,10]) == 4)

def test_5():
    assert(func_test(list())==5)
    
def test_6():
    assert(func_test(1)==6)

def test_7():
    assert(func_test(2,1)==3)