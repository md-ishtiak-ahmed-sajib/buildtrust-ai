"""Bound structural work before parsing untrusted JSON."""
import json


def check_shape(content):
    content = content.encode("utf-8") if isinstance(content, str) else content
    depth, structures, quoted, escaped = 0, 0, False, False
    for char in content:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
            continue
        if char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            structures += 1
            if depth > 64:
                raise ValueError("JSON nesting is limited to 64 levels")
        elif char in (93, 125):
            depth -= 1
        elif char in (44, 58):
            structures += 1
        if structures > 100_000:
            raise ValueError("JSON structure exceeds the processing bound")


def loads(content):
    check_shape(content)
    return json.loads(content)
