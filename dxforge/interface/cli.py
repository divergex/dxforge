import argparse


def main():
    # Create the top-level parser
    parser = argparse.ArgumentParser(
        description="My CLI Program",
        epilog="For more information, visit https://example.com/docs"
    )
    subparsers = parser.add_subparsers(
        title='Commands',
        description='Available commands',
        help='Description of available commands',
        dest='command'
    )

    # Command 1
    parser_command1 = subparsers.add_parser(
        'command1',
        help='Execute command 1',
        description='This command performs action 1 with the provided arguments.'
    )
    parser_command1.add_argument(
        'arg1',
        type=str,
        help='Argument 1 for command 1'
    )
    # parser_command1.set_defaults(func=command1.run)

    # Command 2
    parser_command2 = subparsers.add_parser(
        'command2',
        help='Execute command 2',
        description='This command performs action 2 with the provided arguments.'
    )
    parser_command2.add_argument(
        'arg1',
        type=str,
        help='Argument 1 for command 2'
    )
    # parser_command2.set_defaults(func=command2.run)

    # Parse arguments and call the appropriate command function
    args = parser.parse_args()
    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
