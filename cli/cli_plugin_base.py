import argparse
import logging
import typing


class CLIPluginBase:
    """
    Base class for CLI plugins.

    Subclass this and implement the 'run' method and 'add_arguments' method.
    """

    name = None
    description = ""

    def __init__(self, logger: typing.Optional[logging.Logger] = None):
        """
        Initialize the plugin with an optional logger.
        Args:
            logger (logging.Logger): Logger instance for the plugin.
        """
        self.logger = logger

    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser):
        """
        Add custom argparse arguments for the plugin.
        Args:
            parser (argparse.ArgumentParser): The argument parser for the subcommand.
        """
        pass

    def run(self, args):
        raise NotImplementedError("Plugin must implement run(args)")
