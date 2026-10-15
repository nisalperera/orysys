from scripts.check_env import check_lines


def test_detects_unparsable_lines_without_values():
    text = "A=ok\nB=has space here\nC=\"unclosed\nsk-or-v1-abcdef\nD=\"fine\" # c\n# comment\nE='x' y\n"
    issues, values = check_lines(text)
    by_line = {n: msg for n, _, msg in issues}
    assert set(by_line) == {2, 3, 4, 7}
    assert "not quoted" in by_line[2] and "never closed" in by_line[3] and "KEY=VALUE" in by_line[4]
    assert values["D"] == '"fine" # c'
