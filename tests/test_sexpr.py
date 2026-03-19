from kicad.parsers.sexpr import parse_sexpr


def test_simple_list():
    result = parse_sexpr("(hello world)")
    assert result == ["hello", "world"]


def test_nested():
    result = parse_sexpr("(a (b c) d)")
    assert result == ["a", ["b", "c"], "d"]


def test_integer():
    result = parse_sexpr("(version 20240108)")
    assert result == ["version", 20240108]


def test_float():
    result = parse_sexpr("(thickness 1.6)")
    assert result == ["thickness", 1.6]


def test_negative_number():
    result = parse_sexpr("(at -0.48 0)")
    assert result == ["at", -0.48, 0]


def test_quoted_string():
    result = parse_sexpr('(name "F.Cu")')
    assert result == ["name", "F.Cu"]


def test_quoted_string_with_spaces():
    result = parse_sexpr('(description "A long description here")')
    assert result == ["description", "A long description here"]


def test_quoted_string_with_escaped_quote():
    result = parse_sexpr(r'(value "2.2\u03BCF")')
    assert result == ["value", r"2.2\u03BCF"]


def test_empty_quoted_string():
    result = parse_sexpr('(value "")')
    assert result == ["value", ""]


def test_deeply_nested():
    result = parse_sexpr("(a (b (c (d e))))")
    assert result == ["a", ["b", ["c", ["d", "e"]]]]


def test_multiple_top_level_children():
    result = parse_sexpr("(kicad_pcb (version 1) (general (thickness 1.6)) (layer 0 F.Cu signal))")
    assert result == ["kicad_pcb", ["version", 1], ["general", ["thickness", 1.6]], ["layer", 0, "F.Cu", "signal"]]


def test_empty_list():
    result = parse_sexpr("()")
    assert result == []


def test_multiline():
    text = """(kicad_sch
  (version 20231120)
  (generator "eeschema")
)"""
    result = parse_sexpr(text)
    assert result == ["kicad_sch", ["version", 20231120], ["generator", "eeschema"]]


def test_parse_file(tmp_path):
    """Test parsing from a file path."""
    from kicad.parsers.sexpr import parse_sexpr_file
    f = tmp_path / "test.kicad_sch"
    f.write_text('(kicad_sch (version 20231120))')
    result = parse_sexpr_file(str(f))
    assert result == ["kicad_sch", ["version", 20231120]]
