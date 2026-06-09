import json

from tokenlens_core import (
    cli_arg_parser,
    collect_all_usage,
    compact_summary_payload,
    human_summary,
    install_antigravity_mcp,
    install_json_mcp,
    install_workspace_rules,
    load_config,
    mcp_json_snippet,
    mcp_toml_snippet,
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

    if args.print_mcp_snippet:
        if args.print_mcp_snippet == "toml":
            print(mcp_toml_snippet(server_name=args.mcp_server_name, default_agent=args.mcp_agent))
        else:
            print(mcp_json_snippet(server_name=args.mcp_server_name, default_agent=args.mcp_agent))
        return

    if args.install_mcp_json:
        if not args.mcp_config:
            parser.error("--install-mcp-json requires --mcp-config")
        result = install_json_mcp(
            config_path=args.mcp_config,
            server_name=args.mcp_server_name,
            default_agent=args.mcp_agent,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
        elif args.compact:
            print(f"TokenLens MCP={'updated' if result.get('changed') else 'unchanged'}")
        else:
            print(f"TokenLens MCP {'updated' if result.get('changed') else 'already configured'}: {result.get('config_path')}")
        return

    if args.install_antigravity_mcp:
        default_agent = args.mcp_agent if args.mcp_agent != "current" else "antigravity"
        result = install_antigravity_mcp(
            config_path=args.mcp_config,
            server_name=args.mcp_server_name,
            default_agent=default_agent,
        )
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
