"""Recover JSON syntax errors that models make inside human-readable strings.

The report contract stays strict JSON. Some providers emit the final answer as a
JSON object whose ``message`` (or claim ``label``) contains unescaped English
double quotes or raw newlines; the object is otherwise complete. Rejecting it
forces another model request and, in the observed live incident, the repair
request itself failed at the gateway.

This parser only repairs *syntax*: unescaped quotes/control characters inside
string values, optional Markdown code fences and prose around the object. Every
schema, evidence-reference, numeric and B2 business check still runs on the
parsed result exactly as before.
"""
import json
import re

_NUMBER = re.compile(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?')
_ESCAPES = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}


class _Parser:
    def __init__(self, text):
        self.text = text
        self.step = 0

    def parse(self):
        # Tolerant mode accepts trailing prose/``` after the first complete value.
        return self.value()

    def _skip(self, step):
        while step < len(self.text) and self.text[step] in ' \t\r\n':
            step += 1
        return step

    def _expect(self, char):
        self.step = self._skip(self.step)
        if self.step >= len(self.text) or self.text[self.step] != char:
            raise ValueError('expected ' + char)
        self.step += 1

    def value(self):
        self.step = self._skip(self.step)
        if self.step >= len(self.text):
            raise ValueError('unexpected end')
        char = self.text[self.step]
        if char == '{':
            return self.object()
        if char == '[':
            return self.array()
        if char == '"':
            return self.string(',}]')
        for literal, value in (('true', True), ('false', False), ('null', None)):
            if self.text.startswith(literal, self.step):
                self.step += len(literal)
                return value
        match = _NUMBER.match(self.text, self.step)
        if not match:
            raise ValueError('invalid value')
        self.step = match.end()
        raw = match.group()
        return float(raw) if any(marker in raw for marker in '.eE') else int(raw)

    def object(self):
        self._expect('{')
        result = {}
        self.step = self._skip(self.step)
        if self.step < len(self.text) and self.text[self.step] == '}':
            self.step += 1
            return result
        while True:
            key = self.string(':')
            self._expect(':')
            result[key] = self.value()
            self.step = self._skip(self.step)
            if self.step >= len(self.text):
                raise ValueError('unterminated object')
            char = self.text[self.step]
            self.step += 1
            if char == '}':
                return result
            if char != ',':
                raise ValueError('expected , or }')

    def array(self):
        self._expect('[')
        result = []
        self.step = self._skip(self.step)
        if self.step < len(self.text) and self.text[self.step] == ']':
            self.step += 1
            return result
        while True:
            result.append(self.value())
            self.step = self._skip(self.step)
            if self.step >= len(self.text):
                raise ValueError('unterminated array')
            char = self.text[self.step]
            self.step += 1
            if char == ']':
                return result
            if char != ',':
                raise ValueError('expected , or ]')

    def string(self, terminators):
        self.step = self._skip(self.step)
        if self.step >= len(self.text) or self.text[self.step] != '"':
            raise ValueError('expected string')
        self.step += 1
        chars = []
        while self.step < len(self.text):
            char = self.text[self.step]
            if char == '\\':
                self.step += 1
                if self.step >= len(self.text):
                    raise ValueError('unterminated escape')
                code = self.text[self.step]
                if code == 'u':
                    digits = self.text[self.step + 1:self.step + 5]
                    if len(digits) == 4 and all(digit in '0123456789abcdefABCDEF' for digit in digits):
                        unit = int(digits, 16)
                        self.step += 5
                        # Combine UTF-16 surrogate pairs exactly like json.loads does.
                        if 0xD800 <= unit <= 0xDBFF and self.text.startswith('\\u', self.step):
                            low = self.text[self.step + 2:self.step + 6]
                            if len(low) == 4 and all(digit in '0123456789abcdefABCDEF' for digit in low):
                                low_unit = int(low, 16)
                                if 0xDC00 <= low_unit <= 0xDFFF:
                                    chars.append(chr(0x10000 + ((unit - 0xD800) << 10) + (low_unit - 0xDC00)))
                                    self.step += 6
                                    continue
                        chars.append(chr(unit))
                    else:
                        chars.append('\\u')
                        self.step += 1
                elif code in _ESCAPES:
                    chars.append(_ESCAPES[code])
                    self.step += 1
                else:
                    # Unknown escape: keep the literal characters, never crash.
                    chars.append('\\' + code)
                    self.step += 1
                continue
            if char == '"':
                following = self._skip(self.step + 1)
                if following >= len(self.text) or self.text[following] in terminators:
                    self.step += 1
                    return ''.join(chars)
                # Unescaped quote inside the value: treat it as content.
                chars.append('"')
                self.step += 1
                continue
            chars.append(char)
            self.step += 1
        raise ValueError('unterminated string')


def loads_tolerant(text):
    """Parse the first complete JSON value, tolerating prose/fences and bad quotes."""
    if not isinstance(text, str):
        raise ValueError('text is required')
    start = text.find('{')
    if start < 0:
        raise ValueError('no JSON object present')
    return _Parser(text[start:]).parse()


def parse_decision(text):
    """Strict contract first; fall back to syntax-only recovery before pydantic."""
    from .contracts import Decision
    from pydantic import ValidationError

    try:
        return Decision.model_validate_json(text)
    except ValueError as strict_error:
        try:
            return Decision.model_validate(loads_tolerant(text))
        except (ValueError, TypeError):
            raise strict_error from None
