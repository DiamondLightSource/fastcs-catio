from importlib.metadata import version  # noqa

__version__ = version("CATio")
del version

__all__ = ["__version__"]
