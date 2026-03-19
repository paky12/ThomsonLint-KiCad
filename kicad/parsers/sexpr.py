"""S-expression parser for KiCad files (.kicad_sch, .kicad_pcb)."""


def _tokenize(text: str) -> list[str]:
    """Split S-expression text into tokens: '(', ')', quoted strings, atoms."""
    tokens = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch in ' \t\n\r':
            i += 1
        elif ch == '(':
            tokens.append('(')
            i += 1
        elif ch == ')':
            tokens.append(')')
            i += 1
        elif ch == '"':
            j = i + 1
            while j < length:
                if text[j] == '\\':
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    j += 1
            tokens.append(text[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < length and text[j] not in ' \t\n\r()':
                j += 1
            tokens.append(text[i:j])
            i = j
    return tokens


def _parse_number(token: str):
    """Try to convert a token to int or float. Return the token as-is if not numeric."""
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return token


def _parse_tokens(tokens: list[str], pos: int) -> tuple[list, int]:
    """Recursively parse tokens starting at pos. Returns (parsed_list, new_pos)."""
    result = []
    while pos < len(tokens):
        token = tokens[pos]
        if token == '(':
            child, pos = _parse_tokens(tokens, pos + 1)
            result.append(child)
        elif token == ')':
            return result, pos + 1
        else:
            result.append(_parse_number(token))
            pos += 1
    return result, pos


def parse_sexpr(text: str) -> list:
    """Parse an S-expression string into nested Python lists."""
    tokens = _tokenize(text)
    if not tokens:
        return []
    if tokens[0] == '(':
        result, _ = _parse_tokens(tokens, 1)
        return result
    result, _ = _parse_tokens(tokens, 0)
    return result[0] if len(result) == 1 else result


def parse_sexpr_file(file_path: str) -> list:
    """Parse an S-expression file into nested Python lists."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return parse_sexpr(f.read())
