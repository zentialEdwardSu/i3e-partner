from cli.cli_plugin_base import CLIPluginBase


class HelloPlugin(CLIPluginBase):
    name = "hello"
    description = """
        Say hello:D
        and
        do nothing
        just hello"""

    @staticmethod
    def add_arguments(parser):
        parser.add_argument("--path", type=str, help="Specify a path")
        parser.add_argument("--option", type=str, help="Specify an option")
        parser.add_argument("names", nargs="*", help="Names to greet")

    def __init__(self, logger=None):
        super().__init__(logger)
        self.logger = logger

    def run(self, args):
        if self.logger:
            self.logger.info("HelloPlugin started")
        if args.path:
            print(f"Path argument received: {args.path}")
        if args.option:
            print(f"Option argument received: {args.option}")
        if args.names:
            print(f"Hello, {' '.join(args.names)}!")
        else:
            print("Hello from CLIPlugin!")
