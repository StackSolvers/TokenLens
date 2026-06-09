import json

from tokenlens_core import (
    cli_arg_parser,
    collect_all_usage,
    compact_summary_payload,
    human_summary,
    install_antigravity_mcp,
    install_workspace_rules,
    load_config,
)


def main(argv=None):
    parser = cli_arg_parser()
    args = parser.parse_args(argv)

    if args.install_rules:
        touched = install_workspace_rules(workspace_dir=args.workspace)
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

    if args.install_antigravity_mcp:
        result = install_antigravity_mcp(config_path=args.mcp_config)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
        elif args.compact:
            print(f"TokenLens MCP={'updated' if result.get('changed') else 'unchanged'}")
        else:
            print(f"TokenLens MCP {'updated' if result.get('changed') else 'already configured'}: {result.get('config_path')}")
        return

    config = load_config(args.config)
    data = collect_all_usage(
        config,
        custom_antigravity_dir=args.path,
        only_agents=None if args.agent == "all" else args.agent,
    )

    if args.json:
        payload = compact_summary_payload(data) if args.compact else data
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
        return

    print(human_summary(data, compact=args.compact or not args.verbose))


if __name__ == "__main__":
    main()
