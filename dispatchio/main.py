from inspect import Parameter, getmro, signature, isabstract
from functools import wraps
from itertools import chain
import inspect
from numbers import Number
import numbers
from collections.abc import Mapping, Sequence, Iterable
import typing
from typing import Any, DefaultDict, FrozenSet, Literal, NamedTuple, Tuple, Sequence, Union, List, get_args, get_origin, TypeVar
from operator import indexOf, itemgetter, sub
from warnings import warn
from dataclasses import dataclass

hard_coded_ABC_spec= {
    Mapping: 0,
    Literal: 0,
    tuple: 0,
    Union: 1,
    Number: 1,
    Sequence: 1,
    Iterable: 2
}

def conforms_to_sig_names(in_param:typing.Tuple[typing.Tuple, typing.Mapping[str, Any]], to_params:List[Parameter]):
    args, kwargs = in_param
    has_to_be_keyword_params = set(x.name for x in to_params[len(args):] if x.default is inspect._empty)
    return has_to_be_keyword_params.issubset(set(kwargs.keys()))

def calculate_specificity(in_param:typing.Tuple[typing.Tuple, typing.Mapping[str, Any]], to_params:List[Parameter]):
    specificity = 0
    args, kwargs = in_param
    param_name_map = {param.name: param for param in to_params[len(in_param):]}

    def calc_type(a, b, obj = None):
        origin, subscript = get_origin(b), get_args(b)

        # go from type alias to actual type if possible
        if origin is not None:
            b = origin

        # Simple check for typevar such as AnyStr, TODO: make more robust
        if(type(b) == TypeVar):
            is_sub = issubclass(a, b.__constraints__)
        elif(b is Union):
            is_sub = True # True for now, we check the subscripts later
        else:
            is_sub = issubclass(a,b)
            
        if is_sub:          

            specificity = 0

            if subscript:
                if b is Union:
                    sp = tuple(calc_type(a,b) for b in subscript)
                    if all( x is None for x in sp):
                        return None
                    else:
                        specificity += min(x for x in sp if x is not None) + hard_coded_ABC_spec[Union]
                elif issubclass(b, Mapping):
                    # Only check first element of mapping
                    k,v = next(iter(obj.items()))
                    sp = (calc_type(type(k), subscript[0], k), calc_type(type(v), subscript[1], v))
                    if None in sp:
                        return None
                    else:
                        specificity += sum(sp)+hard_coded_ABC_spec[Mapping]
                elif issubclass(b, Iterable):
                    el = next(iter(obj))
                    sp = calc_type(type(el), subscript[0], el)
                    if sp is None:
                        return None
                    else:
                        specificity += sp

                else:
                    warn(f"{b}, {subscript} not yet supported")


            if a is b: 
                return specificity
            
            specificity += 1

            if not isabstract(b):
                try:
                    specificity += indexOf(getmro(a), b)
                except ValueError:
                    warn(f"using some issubclass override that does not respect isabstract(), {b}")

                return specificity                
            else:
                val = hard_coded_ABC_spec.get(b, None)
                if val is None:
                    warn(f"using some abstract base class without a predefined specificity, {b}")
                    val = 9
                return val + specificity
        else:
            return None

    # map the incoming keyword arguments to the defined function keyword arguments
    keyword_argument_in_to_pair = [(arg, param_name_map.get(name, None)) for name, arg in kwargs.items()]

    # loop over all incoming parameters to the outgoing
    for in_arg, to_arg in chain(zip(args, to_params), keyword_argument_in_to_pair):
        if to_arg == None: continue #TODO: check if func is vararg here
        # If there is no annotation we can skip
        if to_arg.annotation is inspect._empty:
            continue

        r = calc_type(type(in_arg), to_arg.annotation, in_arg)      
        if r is None: return None
        else: specificity += r  

    return specificity    

@dataclass
class FuncMap():
    min = DefaultDict(set)
    max = DefaultDict(set)
    max_seen = 0
    

def dispatchio(func):
    mapping = FuncMap()

    @wraps(func)
    def wrapped(*args, **kwargs):
        number_of_params = len(args)+len(kwargs)
        
        min_funcs = set()
        max_funcs = set()
        for i in range(0, number_of_params+1):
            min_funcs.update(mapping.min[i])

        for i in range(number_of_params, mapping.max_seen+1):
            max_funcs.update(mapping.max[i])
        #var_arg funcs
        max_funcs.update(mapping.max[-1])

        possible_funcs = min_funcs.intersection(max_funcs)

        # Are all keyword names included
        possible_funcs = [f for f in possible_funcs if conforms_to_sig_names((args, kwargs), f[0])]
        specificities = [(f,calculate_specificity((args, kwargs), f[0])) for f in possible_funcs]
        specificities = [s for s in specificities if s[1] is not None]
        result = list(sorted(specificities, key=itemgetter(1)))
        if len(result)==0:
            raise Exception("No method found")
        return result[0][0][1](*args, **kwargs)

    def register(func2):
        sig = list(signature(func2).parameters.values())

        non_var_parameters = [par for par in sig if par.kind in [Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_OR_KEYWORD, Parameter.POSITIONAL_ONLY]]
        nr_of_arguments = len(non_var_parameters)

        contains_var_parameters = True if len(sig)-len(non_var_parameters)>0 else False

        mandatory_params = [par for par in non_var_parameters if par.default is inspect._empty]
        nr_of_mandatory_args = len(mandatory_params)

        # Having kwargs or args means that the function must contain AT LEAST nr_of_arguments
        # informally encode that as -nr_of_arguments in the dict
        
        for param in non_var_parameters:
            # Remove default parameter to make parameter type hashable. TODO: make this less hackey
            param._default = None if param.default is not inspect._empty else inspect._empty
        s = (tuple(non_var_parameters),func2)
        mapping.min[nr_of_mandatory_args].add(s)
        mapping.max[nr_of_arguments if not contains_var_parameters else -1].add(s)
        mapping.max_seen = nr_of_arguments if nr_of_arguments > mapping.max_seen else mapping.max_seen
        
        @wraps(func2)
        def registered_func(*args, **kwargs):
            return func2(*args, **kwargs)
        return registered_func  
    
    register(func)
    setattr(wrapped, "mapping", mapping)
    setattr(wrapped, "register", register)

    return wrapped


