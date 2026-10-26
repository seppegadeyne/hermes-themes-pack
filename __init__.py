"""Hermes theme pack: `/theme` slash command and `hermes theme` CLI. No load-time side effects."""
import shlex

from .installer import USAGE, ThemeError, configure_parser, dispatch, run


def handle_theme(raw_args: str) -> str:
    try:
        return dispatch(shlex.split(raw_args or ""))
    except (ThemeError, OSError, ValueError) as error:
        return f"Theme: {error}"


def register(ctx):
    ctx.register_command(
        "theme",
        handler=handle_theme,
        description="Switch the Hermes theme on every surface, or follow Omarchy",
        args_hint="[name|list|omarchy|follow on|off]",
    )
    # `hermes theme ...` is wired only with plugins.isolation: in_process; /theme works either way.
    ctx.register_cli_command(
        name="theme",
        help="Switch, install or remove pack themes; follow Omarchy",
        description=USAGE,
        setup_fn=configure_parser,
        handler_fn=run,
    )
