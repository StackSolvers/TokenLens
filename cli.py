import json

from tokenlens_core import (
    cli_arg_parser,
    collect_all_usage,
    human_summary,
    install_workspace_rules,
    load_config,
)


def main(argv=None):
    parser = cli_arg_parser()
    args = parser.parse_args(argv)

    if args.install_rules:
        touched = install_workspace_rules()
        if args.compact:
            print(f"TokenLens rules={'installed' if touched else 'unchanged'}")
        else:
            if touched:
                print("Installed TokenLens guidance:")
                for path in touched:
                    print(f"- {path}")
            else:
                print("TokenLens guidance already present or skipped.")
        return

    config = load_config(args.config)
    data = collect_all_usage(config, custom_antigravity_dir=args.path)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=None if args.compact else 2))
        return

    print(human_summary(data, compact=args.compact))


if __name__ == "__main__":
    main()
