from inspect import signature
from numbers import Number
from typing import Iterable
from dispatchio import dispatchio
import pytest


@dispatchio
def func_test(a:int, b:float, c=None, *args, **kwargs): return 1

@func_test.register
def _(a: float, g:float): return 2

@func_test.register
def _(a: Number, g:Number): return 3

@func_test.register
def _(a: Iterable[Number]): return 4


def test_1():
    assert(func_test(1,1.0) == 1)
    assert(func_test(1,1.0,"dfdf", x="b") == 1)

def test_4():
    assert(func_test([10,10,10]) == 4)
    assert(func_test([None,10,10]) == 4)
    

print(func_test(1, 1.0))