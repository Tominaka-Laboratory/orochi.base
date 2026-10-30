.. image:: images/orochi_icon.png
   :align: center
   :width: 80px
   :target: https://github.com/Tominaka-Laboratory/orochi.base
   :alt: Orochi Logo

===========
orochi.base
===========

.. |title| replace:: orochi.base
.. _title: https://Tominaka-Laboratory.github.io/orochi.base

.. |Icon| image:: images/orochi_icon.png
   :target: https://github.com/Tominaka-Laboratory/orochi.base
   :height: 100px

|PyPi| |Forge| |PythonVersion| |ChemRxiv| |PR|

|CI| |Codecov| |Black| |Tracking|

.. |ChemRxiv| image:: https://img.shields.io/badge/ChemRxiv-10.26434%2Fchemrxiv.15010802%2Fv2-blue.svg
        :target: https://doi.org/10.26434/chemrxiv.15010802/v2

.. |Black| image:: https://img.shields.io/badge/code_style-black-black
        :target: https://github.com/psf/black

.. |CI| image:: https://github.com/Tominaka-Laboratory/orochi.base/actions/workflows/tests.yml/badge.svg
        :target: https://github.com/Tominaka-Laboratory/orochi.base/actions/workflows/tests.yml

.. |Codecov| image:: https://codecov.io/gh/Tominaka-Laboratory/orochi.base/branch/main/graph/badge.svg
        :target: https://codecov.io/gh/Tominaka-Laboratory/orochi.base

.. |Forge| image:: https://img.shields.io/conda/vn/conda-forge/orochi.base
        :target: https://anaconda.org/conda-forge/orochi.base

.. |PR| image:: https://img.shields.io/badge/PR-Welcome-29ab47ff

.. |PyPi| image:: https://img.shields.io/pypi/v/orochi.base
        :target: https://pypi.org/project/orochi.base/

.. |PythonVersion| image:: https://img.shields.io/pypi/pyversions/orochi.base
        :target: https://pypi.org/project/orochi.base/

.. |Tracking| image:: https://img.shields.io/badge/issue_tracking-github-blue
        :target: https://github.com/Tominaka-Laboratory/orochi.base/issues

Orochi Core: Unified Parameter Management
=========================================

The ``orochi.base`` package forms the central body of the Orochi framework, providing a **unified and robust system for parameter management, constraint enforcement, and cross-module interoperability**. In Orochi's architecture, calculation modules branch out as decentralized heads, while ``orochi.base`` acts as the common trunk that externalizes physical and instrumental variables.

Key Features
------------
* **Centralized Parameter Control**: All physical variables, boundaries, and active refinement flags are managed in a standardized dictionary format.
* **Hierarchical String-Address Namespace**: Parameters across the entire framework are uniquely addressable via flat string paths (e.g., ``@phase_0/a/val``, ``@pixia_0/beam_x/val``), enabling external optimizers (SciPy, CMA-ES, Optuna) to manipulate multi-module parameters without glue code.
* **Automatic Change Detection & Caching**: Methods decorated via ``DependencyMeta`` automatically track ``_changed_parameters`` and skip unneeded expensive computations when dependent parameters remain unchanged.
* **Execution Control**: Provides both automated execution (``__call__(force=False)``) with dependency caching and explicit manual execution (``run(force=True)``) for full pipeline recalculation.
* **Symbolic Constraints & Symmetry**: Integrates SymPy for symbolic mathematical relationships and binds space-group crystallographic constraints dynamically.
* **Diagnostic Introspection**: Standardizes structured diagnostic reporting (``.explain()``) for autonomous AI agents and user feedback.

Parameter Management Specification
----------------------------------

Parameters are internally stored as standardized dictionaries containing physical values and scientific metadata:

.. code-block:: python

    from orochi.base.core import OrochiBase

    # Subclass or instantiate
    obj = OrochiBase()

    # 1. Direct dictionary value access
    # Get and set primary value
    obj["scale"] = 1.05
    val = obj["scale"]

    # 2. Accessing scientific attributes (bounds, active refinement toggle)
    obj["scale", "min"] = 0.0
    obj["scale", "max"] = 10.0
    obj["scale", "fit"] = True   # Participates in optimization

    # 3. Flat string-addressing across registered instances
    # Format: @<instance_id>/<parameter_key>/<attribute>
    # e.g., @phase_0/a/val, @pixia_0/beam_x/val

Developer Guide: Creating an Orochi Module
------------------------------------------

Third-party developers and beamline scientists can create custom Orochi calculation modules by subclassing ``OrochiBase``. Subclasses automatically inherit unified parameter storage, Gradio UI synthesis compatibility (``param_boxes``), dependency caching, and cross-module optimization interfaces.

What is a Custom Orochi Module?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A custom Orochi module does **not** need to be written completely from scratch. In fact, one of the primary design strengths of the Orochi architecture is **wrapping existing, battle-tested scientific Python packages into standardized Orochi heads**.

For example:

* **``orochi.fit``**: Wraps `LMFIT <https://lmfit.github.io/lmfit-py/>`_ and `Optuna <https://optuna.org/>`_, turning external numerical optimization and Bayesian sampling libraries into seamless Orochi components that directly inspect, bound, and refine parameters across multiple physical modules (such as ``orochi.pdfsim`` and ``orochi.phase``).
* **``orochi.pixia``**: Bridges 2D image processing libraries and detector integration algorithms into the Orochi pipeline.

By subclassing ``OrochiBase``, existing libraries instantly acquire:

1. **Unified Parameter Control**: Parameters, search boundaries, and active refinement flags (``fit``, with backward-compatible alias ``optimize``) are stored in standardized dictionaries accessible via flat string paths (e.g., ``@phase_0/a/val``).
2. **Dependency-Aware Caching**: Expensive external calls or simulations are automatically skipped when inputs have not changed.
3. **Pipeline & UI Interoperability**: Automatic integration into multi-step execution graphs and automated Gradio web UI generation via ``param_boxes``.

Example: Wrapping an External Library (The ``orochi.fit`` LMFIT Pattern)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Below is an illustrative example demonstrating how an external library (such as LMFIT) is wrapped into an Orochi module:

.. code-block:: python

    from orochi.base.core import OrochiBase
    import lmfit

    class CustomLmfitAdapter(OrochiBase):
        """Wraps LMFIT to optimize parameters across attached Orochi simulators."""

        def __init__(self):
            super().__init__()
            # 1. Define optimizer hyperparameters
            self["method"] = "leastsq"
            self["max_nfev"] = 1000
            self["ftol"] = 1e-5
            self.simulators = []

        def build_lmfit_params(self) -> lmfit.Parameters:
            """Translate Orochi parameters marked for optimization into lmfit Parameters."""
            params = lmfit.Parameters()
            for sim in self.simulators:
                for key in sim.keys():
                    if sim.get((key, "fit"), False):
                        pname = f"{sim.id}_{key}"
                        val = sim[key]
                        pmin = sim.get((key, "min"), -float("inf"))
                        pmax = sim.get((key, "max"), float("inf"))
                        params.add(pname, value=val, min=pmin, max=pmax, vary=True)
            return params

        def objective(self, params: lmfit.Parameters, y_obs):
            """Objective function evaluated at each optimization iteration."""
            # Update Orochi simulators with trial values
            for sim in self.simulators:
                for key in sim.keys():
                    pname = f"{sim.id}_{key}"
                    if pname in params:
                        sim[key] = params[pname].value
                # Run simulator (benefits from Orochi's internal caching!)
                sim()

            y_calc = sum(sim.y for sim in self.simulators)
            return y_obs - y_calc

        def __call__(self, y_obs, force: bool = False):
            """Primary execution: run the wrapped external optimizer."""
            if force:
                self._state = "INIT"
            lmfit_params = self.build_lmfit_params()
            result = lmfit.minimize(self.objective, lmfit_params, args=(y_obs,), method=self["method"])
            self.result = result
            self._state = "DONE"
            return result

        def run(self, y_obs, force: bool = False):
            """Explicit execution entry point for manual scripts."""
            return self.__call__(y_obs, force=force)

Standalone Custom Head Template (From Scratch)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For specialized physics models or custom data processing created from scratch, subclass ``OrochiBase`` and register method dependencies for selective caching:

.. code-block:: python

    from orochi.base.core import OrochiBase

    class CustomScatteringHead(OrochiBase):
        """Custom Orochi calculation head."""

        def __init__(self):
            super().__init__()
            # 1. Define module-specific parameters
            self["wavelength"] = 0.18033
            self["attenuation"] = 1.0
            self["attenuation", "min"] = 0.0
            self["attenuation", "max"] = 5.0
            self["attenuation", "fit"] = True

            # 2. Register method dependencies for automatic caching
            # When self["wavelength"] changes, 'calc_geometry' will re-execute;
            # otherwise it will be skipped during repeated calls.
            self._method_dependencies["calc_geometry"] = {
                "self": ["wavelength"]
            }

        def calc_geometry(self):
            """Heavy calculation step executed only when dependent parameters change."""
            # Expensive calculation here...
            pass

        def calc_output(self):
            """Fast calculation step."""
            pass

        def __call__(self, force: bool = False):
            """Primary execution entry point."""
            if force:
                self._state = "INIT"
            super().__call__(force=force)
            self.calc_geometry()
            self.calc_output()
            self._state = "DONE"

        def run(self, force: bool = False):
            """Explicit execution entry point for manual scripts."""
            return self.__call__(force=force)

        def explain(self) -> str:
            """Structured Markdown diagnostic report for AI agents and users."""
            return f"### Custom Module Status\\n- State: {self._state}\\n- Wavelength: {self['wavelength']}"

Citation
--------

If you use orochi.base in a scientific publication, please cite this package as:

    S. Tominaka, *Orochi: A Physics-Grounded Python Package for Pair Distribution Function Analysis of Crystalline and Low-Dimensional Materials*, ChemRxiv (2026). DOI: 10.26434/chemrxiv.15010802/v2
    https://doi.org/10.26434/chemrxiv.15010802/v2

Installation
------------

The preferred method is to install using ``pip``:

.. code-block:: bash

    pip install orochi.base

To confirm that the installation was successful, type:

.. code-block:: bash

    python -c "import orochi.base; print('Orochi Base imported successfully')"

If you prefer to install from source:

.. code-block:: bash

    git clone https://github.com/Tominaka-Laboratory/orochi.base.git
    cd orochi.base
    pip install -e .

Getting Started
---------------

You may consult our `online documentation <https://Tominaka-Laboratory.github.io/orochi.base>`_ for tutorials and API references.

Support and Contribute
----------------------

The orochi.base project welcomes your expertise and enthusiasm!

If you see a bug or want to request a feature, please `report it as an issue <https://github.com/Tominaka-Laboratory/orochi.base/issues>`_ and/or `submit a fix as a PR <https://github.com/Tominaka-Laboratory/orochi.base/pulls>`_.

Feel free to fork the project and contribute. To install orochi.base
in a development mode, with its sources being directly used by Python
rather than copied to a package directory, use the following in the root
directory ::

        pip install -e .

To ensure code quality and to prevent accidental commits into the default branch, please set up the use of our pre-commit
hooks.

Improvements and fixes are always appreciated.

Before contributing, please read our `Code of Conduct <https://github.com/Tominaka-Laboratory/orochi.base/blob/main/CODE_OF_CONDUCT.rst>`_.



License
-------

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. See the `LICENSE.rst` file for details.

This copyleft license guarantees that Orochi remains freely accessible, open, and transparent to the entire scientific community, and that all derivative works must likewise remain open source.

Citation
--------

If you use this package in academic research, please cite:

.. code-block:: bibtex

    @article{tominaka2026orochi,
      title   = {Orochi: A Physics-Grounded Python Package for Pair Distribution Function Analysis of Crystalline and Low-Dimensional Materials},
      author  = {Tominaka, Satoshi},
      journal = {ChemRxiv},
      year    = {2026},
      doi     = {10.26434/chemrxiv.15010802/v2},
      url     = {https://doi.org/10.26434/chemrxiv.15010802/v2}
    }

Contact
-------

For more information on orochi.base please visit the project `web-page <https://Tominaka-Laboratory.github.io/>`_ or email Dr. Satoshi Tominaka at tominaka.satoshi@nims.go.jp.
