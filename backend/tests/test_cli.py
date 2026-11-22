import pytest

from claude_lens.cli import build_parser, main

COMMANDS = ["scan", "migrate-sqlite", "status", "set-password"]


def test_help_lists_all_subcommands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in COMMANDS:
        assert name in out


@pytest.mark.parametrize("name", COMMANDS)
def test_stub_subcommands_print_not_implemented(name, capsys):
    assert main([name]) == 1
    assert "not implemented" in capsys.readouterr().out


def test_command_is_required():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([])
    assert exc.value.code == 2
