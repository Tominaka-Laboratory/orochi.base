from functools import wraps


class DependencyMeta(type):
    """
    A metaclass that wraps methods of the class to conditionally execute
    them based on parameter dependencies.
    """

    def __new__(cls, name, bases, attrs):
        wrapped_attrs = {}
        for attr_name, attr_value in attrs.items():
            if (
                callable(attr_value)
                and not isinstance(attr_value, type)
                and not attr_name.startswith("_")
            ):
                wrapped_attrs[attr_name] = cls.create_conditional_wrapper(
                    attr_name, attr_value
                )
            else:
                wrapped_attrs[attr_name] = attr_value
        return super().__new__(cls, name, bases, wrapped_attrs)

    @staticmethod
    def create_conditional_wrapper(method_name, func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self._state == "INIT":
                return func(self, *args, **kwargs)

            if hasattr(self, "_changed_parameters") and hasattr(
                self, "_method_dependencies"
            ):
                if method_name in self._method_dependencies:
                    dependencies = self._method_dependencies.get(
                        method_name, []
                    )
                    for module_name, params in dependencies.items():
                        if module_name == "self":
                            module = self
                        else:
                            module = getattr(self, module_name)
                        changed_parameters = module._changed_parameters

                        if set(params) & set(changed_parameters):
                            return func(self, *args, **kwargs)

                    return
                else:
                    return func(self, *args, **kwargs)
            else:
                return func(self, *args, **kwargs)

        return wrapper
