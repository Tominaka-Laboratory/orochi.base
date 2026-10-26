import numpy as np
import sympy
import copy
import json, os
from importlib import import_module as imod
import inspect
from .meta import DependencyMeta
from .params import common as default
from .logger import Logger

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, (np.integer, int)): 
            return int(obj)
        elif isinstance(obj, (np.floating, float)): 
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

def unpack(key, attribute="value", index1=None, index2=None):
    """Unpacks a key and its associated attributes and indices.

    Parameters
    ----------
    key : str
        The primary key.
    attribute : str, optional
        The attribute of the key, by default "value".
    index1 : int, optional
        The first index for array-like data, by default None.
    index2 : int, optional
        The second index for 2D array-like data, by default None.

    Returns
    -------
    tuple
        A tuple containing (key, attribute, index1, index2).
    """
    key = str(key)
    return key, attribute, index1, index2


def unpack_key_info(out_type=float, dummy=None, out_shape=1):
    """Unpacks key information related to output type and shape.

    Parameters
    ----------
    out_type : type, optional
        The desired output data type, by default float.
    dummy : any, optional
        A dummy parameter, not currently used, by default None.
    out_shape : int or tuple of int, optional
        The desired output shape, by default 1.

    Returns
    -------
    tuple
        A tuple containing (out_type, dummy, out_shape).
    """
    return out_type, dummy, out_shape


class OrochiBase(metaclass=DependencyMeta):
    """Base class for Orochi modules, handling parameter management,
    logging, and physical constants.

    This class provides a robust framework for managing parameters,
    applying constraints, and interacting with related modules within
    the Orochi ecosystem. It uses a metaclass for dependency injection
    and integrates a custom logger.

    Attributes
    ----------
    cons_h : float
        Planck's constant in J·s.
    cons_c : float
        Speed of light in m/s.
    cons_ec : float
        Elementary charge in J/eV.
    module_name : str
        The name of the module where this instance was created.
    id : str
        Unique identifier for the module instance.
    name : str
        Name of the module instance.
    optimize_keys : list
        List of parameter keys currently configured for optimization.
    """

    cons_h = 6.62606957 * 10 ** (-34)  # J.s
    cons_c = 2.99792458 * 10**8  # m/s
    cons_ec = 1.602176565 * 10**-19  # J/eV

    def __init__(self):
        """Initializes the OrochiBase instance.

        Sets up common and module-specific parameters, initializes
        the module name, and prepares internal tracking mechanisms
        for changed parameters and related modules. It also initializes
        the logger.
        """
        initial_par = getattr(self, "_par", getattr(self, "par", None))
        if initial_par is not None:
            merged_par = copy.deepcopy(default.par)
            merged_par.update(initial_par)
            self._par = merged_par
        else:
            self._par = copy.deepcopy(default.par)

        key_info = copy.deepcopy(default.par_key_info)
        initial_key_info = getattr(self, "_par_key_info", getattr(self, "par_key_info", None))
        if initial_key_info is not None:
            key_info.update(initial_key_info)
        self._par_key_info = key_info

        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        self.module_name = module.__name__ if module is not None else "__main__"
        self._work_dir = None
        self._study_name = None

        self._changed_parameters = set()
        if not hasattr(self, "_method_dependencies"):
            self._method_dependencies = {}

        self._id = "0"
        self._name = self.__class__.__name__
        self._related_modules = {}
        self._init_logger()
        self._state = "INIT"

    def __call__(self, force: bool = False):
        """Executes the primary action of the instance.

        Parameters
        ----------
        force : bool, optional
            If True, resets internal state to 'INIT' to force full re-evaluation
            without skipping cached methods, by default False.
        """
        if force:
            self._state = "INIT"
        self._apply_constraints()

    def run(self, force: bool = False):
        """Explicit execution entry point for user scripts and interactive environments.

        Parameters
        ----------
        force : bool, optional
            If True, forces a complete recalculation by bypassing cached state, by default False.
        """
        return self.__call__(force=force)

    def save(self, save_dir=None):
        """Saves the current parameters to a json file.
        """
        target_dir = save_dir if save_dir is not None else self.work_dir
        if target_dir is None:
            return
        
        target_dir = os.path.join(target_dir, self.study_name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        file_path = os.path.join(
            target_dir, self._name + ".json")
            
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._par, f, cls=NumpyEncoder, ensure_ascii=False, indent=4)

    def load(self, file_path=None):
        """Loads parameters from a json file.
        """
        if file_path is None:
            return None
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_par = json.load(f)

        for key, info in raw_par.items():
            if isinstance(info, dict):
                for attribute, value in info.items():
                    self[key, attribute] = value
            else:
                self[key] = info

    def update(self, params: dict):
        """
        update parameters
        """
        for key, val in params.items():
            if key in self._par:
                self[key] = val

    def _clear_changed_parameters(self):
        """Clears the set of changed parameters after an update cycle."""
        self._changed_parameters.clear()

    def _set_related_modules(self, module):
        """Adds a related module to the internal tracking dictionary.

        Parameters
        ----------
        module : OrochiBase
            An instance of an OrochiBase (or derived) module.
        """
        self._related_modules[module._id] = module

    def __contains__(self, key: str) -> bool:
        """Checks if a parameter key exists in this instance."""
        return key in self._par

    def __iter__(self):
        """Iterates over parameter keys."""
        return iter(self._par)

    def __len__(self) -> int:
        """Returns the number of parameters."""
        return len(self._par)

    def __getitem__(self, input_key):
        """Retrieves a parameter value by key.

        Parameters
        ----------
        input_key : str or tuple
            The key of the parameter to retrieve. Can be a string
            (e.g., "param_name") or a tuple for specific attributes
            or indices (e.g., ("param_name", "attribute"),
            ("param_name", "value", 0)). If the key starts with self["prefix"],
            it's treated as a string address to another module's parameter.

        Returns
        -------
        any
            The retrieved parameter value.

        Raises
        ------
        KeyError
            If the key or address does not exist.
        """
        prefix = self._par["prefix"]["value"]
        delimiter = self._par["address_delimiter"]["value"]

        if input_key in ("optimizables", "optimize_keys", "fit_keys", "fitables"):
            return self.fit_keys
        elif input_key == "prefix":
            return prefix
        elif isinstance(input_key, (list, tuple)):
            value = self._get_key_attribute(input_key)
        else:
            if input_key.startswith(prefix) and delimiter in input_key:
                value = self._get_using_string_address(input_key)
            else:
                value = self._get_key_attribute(input_key)
        return value

    def _get_key_attribute(self, input_key):
        """Internal method to retrieve a parameter value based on its key, attribute, and indices.

        Parameters
        ----------
        input_key : str or tuple
            The key or a tuple containing key, attribute, index1, and index2.

        Returns
        -------
        any
            The value of the specified parameter.

        Raises
        ------
        KeyError
            If the key or attribute is not found.
        IndexError
            If the indices are out of bounds for array-like values.
        """
        if isinstance(input_key, (list, tuple)):
            key, attribute, index1, index2 = unpack(*input_key)
        else:
            key, attribute, index1, index2 = unpack(input_key)

        out_type = None
        out_shape = None
        key_info_dict = getattr(self, "_par_key_info", getattr(self, "par_key_info", {}))
        attr_lookup = attribute
        if key in key_info_dict:
            if attr_lookup not in key_info_dict[key] and attr_lookup in ("fit", "optimize"):
                alt = "fit" if attr_lookup == "optimize" else "optimize"
                if alt in key_info_dict[key]:
                    attr_lookup = alt
            if attr_lookup in key_info_dict[key]:
                key_info = key_info_dict[key][attr_lookup]
                if isinstance(key_info, (list, tuple)):
                    out_type, dummy, out_shape = unpack_key_info(*key_info)
                else:
                    out_type, dummy, out_shape = unpack_key_info(key_info)

        value = self._par[key]

        if isinstance(value, (list, np.ndarray)):
            if np.size(value) == 1:
                value = value[0]
            else:
                if isinstance(index1, str):
                    index1 = int(index1)
                if isinstance(index2, str):
                    index2 = int(index2)
                value = value[index1, index2]
        else:
            # If the value itself is a dict, get the attribute from it.
            if attribute not in value and attribute in ("fit", "optimize"):
                alt = "fit" if attribute == "optimize" else "optimize"
                if alt in value:
                    attribute = alt
            value = value[attribute]
            if out_type is not None:
                value = np.array(value, dtype=out_type).reshape(out_shape)

            if isinstance(value, (list, np.ndarray)):
                value_dim = np.ndim(value)
                if index1 is not None or index2 is not None:
                    if isinstance(index1, str):
                        index1 = int(index1)
                    if isinstance(index2, str):
                        index2 = int(index2)
                    if index1 is None:
                        index1 = slice(None)
                    if index2 is None:
                        value = value[index1]
                    else:
                        value = value[index1, index2]
                else:
                    if value_dim == 0:
                        if out_type is not None and out_shape == 1:
                            value = value[0]
                    elif value_dim > 0 and np.size(value) == 1 and out_shape == 1:
                        value = value[0]

            elif isinstance(value, dict):
                if index1 != None:
                    value = value[index1]

        return value

    def __setitem__(self, input_key, value):
        """Sets a parameter value by key.

        Parameters
        ----------
        input_key : str or tuple
            The key of the parameter to set. Can be a string
            (e.g., "param_name") or a tuple for specific attributes
            or indices (e.g., ("param_name", "attribute"),
            ("param_name", "value", 0)). If the key starts with self["prefix"],
            it's treated as a string address to another module's parameter.
        value : any
            The value to set for the parameter.

        Returns
        -------
        tuple
            A tuple containing (key, attribute, index1, index2) of the set parameter.
        """
        delimiter = self._par["address_delimiter"]["value"]
        prefix = self._par["prefix"]["value"]

        if isinstance(input_key, (list, tuple)):
            key, attribute, index1, index2 = self._set_key_attributes(
                input_key, value
            )
        else:
            if input_key.startswith(prefix) and delimiter in input_key:
                key, attribute, index1, index2 = (
                    self._set_using_string_address(input_key, value)
                )
            else:
                key, attribute, index1, index2 = self._set_key_attributes(
                    input_key, value
                )
        return key, attribute, index1, index2

    def _set_key_attributes(self, input_key, value):
        """Internal method to set a parameter value based on its key, attribute, and indices.

        Parameters
        ----------
        input_key : str or tuple
            The key or a tuple containing key, attribute, index1, and index2.
        value : any
            The value to set.

        Returns
        -------
        tuple
            A tuple containing (key, attribute, index1, index2) of the set parameter.

        Raises
        ------
        KeyError
            If the key does not exist and cannot be implicitly created for attributes.
        IndexError
            If the indices are out of bounds for array-like values.
        """

        if isinstance(input_key, (list, tuple)):
            key, attribute, index1, index2 = unpack(*input_key)
        else:
            key, attribute, index1, index2 = unpack(input_key)

        if attribute in ("fit", "optimize") and key in self._par and isinstance(self._par[key], dict):
            if attribute not in self._par[key]:
                alt = "fit" if attribute == "optimize" else "optimize"
                if alt in self._par[key]:
                    attribute = alt

        if key not in self._par:
            self._par[key] = {attribute: value}

        elif attribute not in self._par[key]:
            if index1 == None:
                self._par[key][attribute] = value
            else:
                # This assumes 'value' attribute exists and has a compatible shape
                # which might not always be true if 'value' is being initialized for 'key'
                values = self._par[key]["value"]
                if isinstance(index1, str):
                    index1 = int(index1)

                if np.size(values) == 1:
                    if index1 == 0:
                        self._par[key][attribute] = value
                    else:
                        print(f"index {index1} is out of range")
                else:
                    attrs = np.zeros_like(self._par[key]["value"])
                    attrs[index1] = value
                    self._par[key][attribute] = attrs
        else:
            value_attr = self._par[key][attribute]
            if attribute in ["min", "max", "std"]:
                values = self._par[key]["value"]
                if np.size(value_attr) < np.size(values):
                    num = np.size(values) - np.size(value_attr)
                    add = np.full(num, None)
                    value_attr = np.append(value_attr, add)
                    self._par[key][attribute] = value_attr
                elif np.size(value_attr) > np.size(values):
                    self._par[key][attribute] = value_attr[:np.size(values)]

            if isinstance(value, (list, tuple, np.ndarray)):
                if isinstance(value, np.ndarray) and np.size(value) == 1:
                    value = value.item() if value.ndim == 0 else value[0]
                elif isinstance(value, (list, tuple)) and len(value) == 1:
                    value = value[0]
            if (
                isinstance(value_attr, (str, float, int, bool))
                or value_attr is None
            ):
                self._par[key][attribute] = value

            elif isinstance(value_attr, (list, np.ndarray)):
                if np.size(value_attr) == 1:
                    value_dim = 0
                else:
                    value_dim = np.size(np.shape(value_attr))

                if isinstance(index1, str):
                    index1 = int(index1)
                if isinstance(index2, str):
                    index2 = int(index2)
                if index1 == None and value_dim > 0:
                    index1 = slice(None)
                    value = np.array(value, dtype=object)
                elif index2 == None and value_dim > 1:
                    index2 = slice(None)
                    value = np.array(value, dtype=object)

                # ========= Automatic array padding =========
                if isinstance(value_attr, np.ndarray):
                    # Use np.nan for floating-point types, otherwise None
                    pad_val = np.nan if np.issubdtype(value_attr.dtype, np.floating) else None
                    needs_update = False

                    if index2 is None and isinstance(index1, int):
                        # Expansion for 1D access
                        if index1 >= value_attr.shape[0]:
                            pad_len = index1 - value_attr.shape[0] + 1
                            pad_width = ((0, pad_len),) + ((0, 0),) * (value_attr.ndim - 1)
                            value_attr = np.pad(value_attr, pad_width, mode='constant', constant_values=pad_val)
                            needs_update = True
                            
                    elif isinstance(index1, int) and isinstance(index2, int):
                        # Expansion for 2D access
                        # Convert 1D array to 2D array (N, 1) first
                        if value_attr.ndim == 1:
                            value_attr = value_attr[:, np.newaxis]
                            needs_update = True

                        if value_attr.ndim >= 2:
                            req_r = max(value_attr.shape[0], index1 + 1)
                            req_c = max(value_attr.shape[1], index2 + 1)
                            if req_r > value_attr.shape[0] or req_c > value_attr.shape[1]:
                                pad_r = req_r - value_attr.shape[0]
                                pad_c = req_c - value_attr.shape[1]
                                pad_width = ((0, pad_r), (0, pad_c)) + ((0, 0),) * (value_attr.ndim - 2)
                                value_attr = np.pad(value_attr, pad_width, mode='constant', constant_values=pad_val)
                                needs_update = True

                    # Update underlying dictionary only when expansion or dimension change occurred
                    if needs_update:
                        self._par[key][attribute] = value_attr

                elif isinstance(value_attr, list):
                    # Safe 1D expansion for list types
                    if index2 is None and isinstance(index1, int) and index1 >= len(value_attr):
                        value_attr.extend([None] * (index1 - len(value_attr) + 1))
                        self._par[key][attribute] = value_attr
                # ===========================================

                if (
                    (index1 == None)
                    or (np.size(value_attr) == 0)
                    or (value_dim == 0)
                ):
                    self._par[key][attribute] = value
                elif index2 == None:
                    if np.size(self._par[key][attribute][index1]) == np.size(
                        value
                    ):
                        shaped_value = np.reshape(value, np.shape(self._par[key][attribute][index1]))
                        self._par[key][attribute][index1] = shaped_value
                    else:
                        self._par[key][attribute] = value
                else:
                    self._par[key][attribute][index1, index2] = value

            else:
                if index1 == None:
                    self._par[key][attribute] = value
                elif index2 == None:
                    self._par[key][attribute][index1] = value
                else:
                    self._par[key][attribute][index1][index2] = value

        if attribute in ("fit", "optimize") and key in self._par and isinstance(self._par[key], dict):
            alt = "optimize" if attribute == "fit" else "fit"
            self._par[key][alt] = copy.deepcopy(self._par[key][attribute])

        self._changed_parameters.add(key)
        return key, attribute, index1, index2

    def __getattr__(self, name: str):
        if name == "par_key_info":
            return getattr(self, "_par_key_info", {})
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    @property
    def fit_keys(self) -> list:
        """Dynamically retrieves parameter keys that have at least one element with fit=True (or legacy optimize=True).

        Returns
        -------
        list of str
            List of parameter keys in self._par marked for fitting.
        """
        keys = []
        if not hasattr(self, "_par") or not isinstance(self._par, dict):
            return keys
        for k, v in self._par.items():
            if isinstance(v, dict):
                opt = v.get("fit", v.get("optimize", None))
                if opt is not None:
                    if isinstance(opt, (bool, int, np.bool_)):
                        if bool(opt):
                            keys.append(k)
                    elif hasattr(opt, "__iter__"):
                        try:
                            arr = np.asanyarray(opt)
                            if arr.size > 0 and np.any(arr):
                                keys.append(k)
                        except Exception:
                            pass
        return keys

    @fit_keys.setter
    def fit_keys(self, value):
        # Gracefully accept assignments for backward compatibility
        pass

    @property
    def optimize_keys(self) -> list:
        """Backward-compatible alias for fit_keys."""
        return self.fit_keys

    @optimize_keys.setter
    def optimize_keys(self, value):
        # Gracefully accept assignments for backward compatibility
        pass

    @property
    def par(self) -> dict:
        """Backward-compatible proxy for internal parameter dictionary."""
        if not hasattr(self, "_par"):
            self._par = {}
        return self._par

    @par.setter
    def par(self, value):
        self._par = value

    @property
    def id(self) -> str:
        """Backward-compatible proxy for internal _id."""
        return str(getattr(self, "_id", "0"))

    @id.setter
    def id(self, value):
        self._id = str(value)

    @property
    def name(self) -> str:
        """Backward-compatible proxy for internal _name."""
        return getattr(self, "_name", self.__class__.__name__)

    @name.setter
    def name(self, value):
        self._name = str(value)

    @property
    def module_id(self) -> str:
        """Backward-compatible proxy for module_id."""
        return self.id

    @module_id.setter
    def module_id(self, value):
        self.id = value

    def _set_equations(self):
        """Sets equations as attributes of the instance.

        Equations are loaded from modules specified in `self["equations"]`.
        """
        for key, eqs in list(self["equations"].items()):
            setattr(self, key, getattr(imod(eqs), key))

    def _update_equations(self):
        """Updates equations by reloading them from their respective modules.

        This is typically used when the underlying equation definitions have changed.
        """
        for key, eqs in list(self["equations"].items()):
            setattr(self, key, getattr(imod(eqs[1], eqs[0]), key))

    def get(self, key):
        """Retrieves a parameter value by key, safely handling missing keys.

        Parameters
        ----------
        key : str or tuple
            The key of the parameter to retrieve.

        Returns
        -------
        any or None
            The parameter value if found, otherwise None.
        """
        try:
            value = self.__getitem__(key)
        except:
            value = None
        return value

    def set(self, key, value):
        """Sets a parameter value by key.

        This is a convenience method that calls `__setitem__`.

        Parameters
        ----------
        key : str or tuple
            The key of the parameter to set.
        value : any
            The value to set.
        """
        self.__setitem__(key, value)

    def _get_using_string_address(self, address):
        """Gets a parameter value using a string address, potentially across modules.

        Parameters
        ----------
        address : str
            The string address of the parameter.
            Examples:
            - "@1/key"
            - "@1/key/attribute"
            - "@1/key/attribute/index1"
            - "@1/key/attribute/index1/index2"

        Returns
        -------
        any or None
            The value at the specified address, or None if not found.
        """
        delimiter = self._par["address_delimiter"]["value"]
        prefix = self._par["prefix"]["value"]

        address_list = address.split(delimiter)
        module_id = address_list[0].lstrip(prefix)

        if self._id == module_id or module_id == "":
            address_list = address_list[1:]
            if len(address_list) == 1:
                return self._get_key_attribute(address_list[0])
            else:
                return self._get_key_attribute(address_list)
        else:
            return None

        #     if address_list[0].strip(self["prefix"]) in self._related_modules:
        #         # This recursive call might lead to infinite recursion if modules refer to each other cyclically
        #         # without proper base cases or depth limits.
        #         return self._related_modules[address_list[0].strip(self["prefix"])][
        #             address
        #         ]
        #     else:
        #         return None

    def _set_using_string_address(self, address, value):
        """Sets a parameter value using a string address, potentially across modules.

        Parameters
        ----------
        address : str
            The string address of the parameter to set.
            Examples:
            - "@1/key"
            - "@1/key/attribute"
            - "@1/key/attribute/index1"
            - "@1/key/attribute/index1/index2"
        value : any
            The value to set.

        Returns
        -------
        tuple
            A tuple containing (key, attribute, index1, index2) of the set parameter.
        """
        address_list = address.split(self["address_delimiter"])
        module_id = address_list[0].strip(self["prefix"])

        if self._id == module_id or module_id == "":
            address_list = address_list[1:]
            if len(address_list) == 1:
                return self._set_key_attributes(address_list[0], value)
            else:
                return self._set_key_attributes(address_list, value)
        else:
            # Setting values across modules is not directly supported via _set_using_string_address
            # for external modules. This only returns None.
            return None, None, None, None

    def _check_if_address_constrained(self, address):
        """Checks if a given address is subject to a constraint.

        Parameters
        ----------
        address : str
            The string address to check (e.g., "@1/param/value").

        Returns
        -------
        bool
            True if the address is constrained, False otherwise.
        """
        prefix = self._par["prefix"]["value"]
        delimiter = self._par["address_delimiter"]["value"]
        key = address.split(delimiter, 1)[1]

        if address in self["constraints"]:
            return True
        elif f"{prefix}{delimiter}{key}" in self["constraints"]:
            return True
        else:
            return False

    def _make_string_address(
        self, key, attribute=None, index1=None, index2=None
    ):
        """Constructs a string address for a parameter.

        Parameters
        ----------
        key : str
            The primary key.
        attribute : str, optional
            The attribute of the parameter, by default None.
        index1 : int, optional
            The first index for 1D or multi-dimensional data, by default None.
        index2 : int, optional
            The second index for 2D data, by default None.

        Returns
        -------
        str
            The formatted string address (e.g., "@id/key/attribute/index1/index2").
        """
        prefix = self._par["prefix"]["value"]
        delimiter = self._par["address_delimiter"]["value"]
        address_list = [
            str(v) for v in [key, attribute, index1, index2] if v is not None
        ]
        str_key = prefix + str(self._id) + delimiter + str(delimiter).join(address_list)
        return str_key

    def _apply_constraints(self):
        """Applies constraints defined as dictionary items in `self["constraints"]`.

        Constraints are applied by evaluating a string equation for a given
        parameter address and then setting the parameter's value to the result.

        Examples
        --------
        {
        "@1/occ/value/1": "@1/occ/value/0 * 2.",
        "@1/occ/value/2": "1.",
        }
        """

        for key, equation_string in self["constraints"].items():
            if isinstance(equation_string, (float, int)):
                result = equation_string
            else:
                terms = filter(None, equation_string.split(" "))
                eq = []
                for term in terms:
                    if term.startswith(self["prefix"]):
                        eq.append(self[term])
                    elif term in self._par:
                        eq.append(self[term])
                    else:
                        eq.append(term)
                # Ensure all elements in 'eq' are suitable for joining.
                # If 'self[term]' returns non-string/non-numeric objects,
                # this join might not produce a valid expression string.
                eq = np.array(eq).flatten()
                expression_string = "".join(map(str, eq))
                # sympy.sympify can handle basic arithmetic and variable names.
                # It's important that the 'expression_string' is a valid sympy expression.
                result = sympy.sympify(expression_string).evalf()
            self[key] = result

    def _reset_constraints(self):
        """Delete all the constraints
        """
        self["constraints"] = {}


    def keys(self):
        """Returns a list of all parameter keys.

        Returns
        -------
        list
            A list of strings representing the parameter keys.
        """
        return list(self._par.keys())

    def values(self):
        """Returns a list of all parameter values.

        Returns
        -------
        list
            A list of all parameter values.
        """
        return list(self._par.values())

    def items(self):
        """Returns a list of all parameter key-value pairs.

        Returns
        -------
        list
            A list of (key, value) tuples for all parameters.
        """
        return list(self._par.items())

    # def save_params(self, name=".pkl"):
    #     """Saves the current parameters to a pickle file.

    #     Parameters
    #     ----------
    #     name : str, optional
    #         The filename to save the parameters to, by default ".pkl".
    #     """
    #     import pickle

    #     with open(name, "wb") as f:
    #         pickle.dump(self.par, f)

    # def load_params(self, name=".pkl"):
    #     """Loads parameters from a pickle file.

    #     The loaded parameters will overwrite the current parameters of the instance.

    #     Parameters
    #     ----------
    #     name : str, optional
    #         The filename to load the parameters from, by default ".pkl".
    #     """
    #     import pickle

    #     with open(name, "rb") as f:
    #         par = pickle.load(f)
    #     self.par = par

    def _init_logger(self):
        """Initializes the logger for the instance.

        It retrieves logging configuration (rotation, directory, level)
        from the instance's parameters and creates a Logger object.
        """
        rotation = self["logger", "rotation"]
        level = self["logger"]
        work_dir = os.path.join(self.work_dir,"logs") if self.work_dir is not None else None
        self._logger = Logger(level=level, 
                              work_dir=work_dir, 
                              study_name=self.study_name, 
                              rotation=rotation)

    def set_energy_from_rambda(self):
        """Calculates and sets the energy parameter based on the 'rambda' (wavelength) parameter.

        This calculation uses fundamental physical constants (`cons_c`, `cons_h`, `cons_ec`).
        The 'rambda' value is assumed to be in Angstroms and converted to meters.
        The 'energy' parameter is set in eV.
        """
        self._par["energy"]["value"] = (
            self.cons_c
            * self.cons_h
            / (self["rambda"] * 10**-10 * self.cons_ec)
        )
        self._changed_parameters.add("energy")

    def set_rambda_from_energy(self):
        """Calculates and sets the 'rambda' (wavelength) parameter based on the 'energy' parameter.

        This calculation uses fundamental physical constants (`cons_c`, `cons_h`, `cons_ec`).
        The 'energy' value is assumed to be in eV.
        The 'rambda' parameter is set in Angstroms.
        """
        self._par["rambda"]["value"] = (
            self.cons_c
            * self.cons_h
            / (self["energy"] * 10**-10 * self.cons_ec)
        )
        self._changed_parameters.add("rambda")

    def twotheta_to_q(self, tt):
        """Converts 2-theta angle to scattering vector q.

        Parameters
        ----------
        tt : float or np.ndarray
            The 2-theta angle(s) in degrees.

        Returns
        -------
        float or np.ndarray
            The scattering vector q value(s) in inverse Angstroms.
        """
        q = 4.0 * np.pi / self["rambda"] * np.sin(np.radians(tt / 2.0))
        return q

    def q_to_twotheta(self, q):
        """Converts scattering vector q to 2-theta angle.

        Parameters
        ----------
        q : float or np.ndarray
            The scattering vector q value(s) in inverse Angstroms.

        Returns
        -------
        float or np.ndarray
            The 2-theta angle(s) in degrees.
        """
        tt = (
            np.arcsin(q / (4.0 * np.pi / self["rambda"])) / np.pi * 180.0 * 2.0
        )
        return tt
    
    @property
    def work_dir(self):
        return self._work_dir
    
    @work_dir.setter
    def work_dir(self, value):
        self._work_dir = value
        self._logger.work_dir = os.path.join(value, "logs") if value is not None else None

    @property
    def study_name(self):
        return self._study_name
    
    @study_name.setter
    def study_name(self, value):
        self._study_name = value
        self._logger.study_name = value





