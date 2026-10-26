import os

par = {
    # "module_constraint": {"value": []},
    # "param_constraint": {"value": {}},
    "optimizables": {"value": []},
    "constraints": {"value": {}},
    "nest_modules": {"value": []},
    "prefix":{"value": "@"},
    "address_delimiter":{"value":"/"},
    "logger": {
        "value": "INFO",
        "member": ["INFO", "DEBUG", "ERROR", "WARNING"],
        # "dir": os.path.join(os.getcwd(), "logs"),
        "rotation": "1 day",
    },
}

par_key_info = {
    # "module_constraint": {"value": [object, None, -1]},
    # "param_constraint": {"value": [dict, None, 1]},
    "optimizables": {"value": [str, None, -1]},
    "nest_modules": {"value": [str, None, -1]},
    "constraints": {"value": [dict, None, 1]},
    "prefix": {"value": [str, None, 1]},
    "address_delimiter": {"value": [str, None, 1]},
    "logger": {"value": [str, None, 1]},
}
