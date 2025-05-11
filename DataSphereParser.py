# antlr4 -Dlanguage=Python3 DML.g4 -o DataSphereParser

import json
import re
import sys
from dataclasses import dataclass
from typing import List, Union, Dict, Any

# Token types and their corresponding regex patterns
TOKEN_SPECIFICATION = [
    ('AT_KEYWORD', r'@\w+'),  # @keyword
    ('COLON', r':'),  # :
    ('COMMA', r','),  # ,
    ('DOT', r'\.'),  # .
    ('LPAREN', r'\('),  # (
    ('RPAREN', r'\)'),  # )
    ('LBRACE', r'\{'),  # {
    ('RBRACE', r'\}'),  # }
    ('LBRACKET', r'\['),  # [
    ('RBRACKET', r'\]'),  # ]
    ('STRING', r'"(?:\\.|[^"\\])*"'),  # "string"
    ('NUMBER', r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'),  # number
    ('OPERATOR', r'[+\-*/%]|==|!=|<=|>=|<|>'),  # operators
    ('TRUE', r'\btrue\b'),  # true
    ('FALSE', r'\bfalse\b'),  # false
    ('NULL', r'\bnull\b'),  # null
    ('IDENTIFIER', r'[A-Za-z_][A-Za-z0-9_]*'),  # identifiers
    ('WS', r'\s+'),  # whitespace (includes newlines)
    ('COMMENT', r'//.*?$|/\*.*?\*/'),  # comments
]

# Compile the combined regex pattern for tokenization
TOKEN_REGEX = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_SPECIFICATION)
TOKEN_PATTERN = re.compile(TOKEN_REGEX, re.DOTALL | re.MULTILINE)

@dataclass
class Token:
    """Class representing a single token."""
    type: str
    value: str
    position: int

    def __repr__(self):
        return f'Token({self.type}, {self.value}, pos={self.position})'

class Lexer:
    """Lexer for tokenizing DML input text."""

    def __init__(self, input_text: str):
        self.input_text = input_text

    def tokenize(self) -> List[Token]:
        """Tokenize the input text into a list of tokens."""
        tokens = []
        for match in TOKEN_PATTERN.finditer(self.input_text):
            token_type = match.lastgroup
            token_value = match.group()
            token_pos = match.start()
            if token_type in ('WS', 'COMMENT'):
                continue  # Ignore whitespace and comments
            tokens.append(Token(token_type, token_value, token_pos))
        return tokens

class Parser:
    """Parser for DML tokens."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> Any:
        """Parse the token list and return the resulting DML structure."""
        if self.pos >= len(self.tokens):
            raise SyntaxError("No tokens to parse")
        token = self.current_token()
        if token.type == 'LBRACE':
            # Parse a JSON object
            return self.parse_object()
        else:
            # Parse top-level key-value pairs
            dml_sections = {}
            while self.pos < len(self.tokens):
                token = self.current_token()
                if token.type in ('AT_KEYWORD', 'IDENTIFIER'):
                    key = token.value
                    self.consume_token()
                    if self.current_token().type == 'COLON':
                        self.consume_token('COLON')
                        value = self.parse_value()
                        dml_sections[key] = value
                    else:
                        raise SyntaxError(
                            f"Expected ':' after key '{key}', but got {self.current_token().type} at position {self.current_token().position}")
                else:
                    raise SyntaxError(f"Unexpected token {token.type} at position {token.position}")
            return dml_sections

    def parse_value(self) -> Any:
        """Parse a value."""
        token = self.current_token()
        if token.type == 'LBRACE':
            return self.parse_object()
        elif token.type == 'LBRACKET':
            return self.parse_array()
        elif token.type == 'STRING':
            return self.parse_string()
        elif token.type == 'NUMBER':
            return self.parse_number()
        elif token.type in ('TRUE', 'FALSE', 'NULL'):
            return self.parse_constant()
        else:
            return self.parse_expression()

    def parse_object(self) -> Dict[str, Any]:
        """Parse an object."""
        obj = {}
        self.consume_token('LBRACE')
        while True:
            token = self.current_token()
            if token.type == 'RBRACE':
                break
            key = self.parse_key()
            self.consume_token('COLON')
            value = self.parse_value()
            obj[key] = value
            token = self.current_token()
            if token.type == 'COMMA':
                self.consume_token('COMMA')
            elif token.type == 'RBRACE':
                break
            else:
                raise SyntaxError(f"Expected ',' or '}}', but got {token.type} at position {token.position}")
        self.consume_token('RBRACE')
        return obj

    def parse_array(self) -> List[Any]:
        """Parse an array."""
        array = []
        self.consume_token('LBRACKET')
        while True:
            token = self.current_token()
            if token.type == 'RBRACKET':
                break
            value = self.parse_value()
            array.append(value)
            token = self.current_token()
            if token.type == 'COMMA':
                self.consume_token('COMMA')
            elif token.type == 'RBRACKET':
                break
            else:
                raise SyntaxError(f"Expected ',' or ']', but got {token.type} at position {token.position}")
        self.consume_token('RBRACKET')
        return array

    def parse_key(self) -> str:
        """Parse a key in an object."""
        token = self.current_token()
        if token.type in ('STRING', 'IDENTIFIER', 'AT_KEYWORD'):
            key = token.value
            self.pos += 1
            return key
        else:
            raise SyntaxError(f"Unexpected token {token.type} in key at position {token.position}")

    def parse_string(self) -> str:
        """Parse a string."""
        token = self.consume_token('STRING')
        string_content = token.value[1:-1]
        return self._decode_string(string_content)

    def parse_number(self) -> Union[int, float]:
        """Parse a number."""
        token = self.consume_token('NUMBER')
        value = token.value
        if '.' in value or 'e' in value or 'E' in value:
            return float(value)
        else:
            return int(value)

    def parse_constant(self) -> Any:
        """Parse constants true, false, null."""
        token = self.current_token()
        if token.type == 'TRUE':
            self.consume_token('TRUE')
            return True
        elif token.type == 'FALSE':
            self.consume_token('FALSE')
            return False
        elif token.type == 'NULL':
            self.consume_token('NULL')
            return None

    def parse_expression(self) -> str:
        """Parse an expression."""
        tokens = []
        while self.pos < len(self.tokens):
            token = self.current_token()
            if token.type in ('COMMA', 'RBRACE', 'RBRACKET'):
                break
            tokens.append(token.value)
            self.pos += 1
        return ''.join(tokens)

    @staticmethod
    def _decode_string(s: str) -> str:
        """Decode escape sequences in a string."""
        return bytes(s, "utf-8").decode("unicode_escape")

    def current_token(self) -> Token:
        """Return the current token, skipping whitespace."""
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == 'WS':
            self.pos += 1
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        else:
            raise SyntaxError("Unexpected end of input")

    def consume_token(self, expected_type: str = None) -> Token:
        """Consume and return the current token, checking its type if specified."""
        token = self.current_token()
        if expected_type and token.type != expected_type:
            raise SyntaxError(f"Expected {expected_type}, but got {token.type} at position {token.position}")
        self.pos += 1
        return token

def parse_dml(dml_string: str) -> Any:
    """Parse a DML string into a Python object."""
    lexer = Lexer(dml_string)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()

def parse_dml_file(file_path: str) -> Any:
    """Parse DML content from a file into a Python object."""
    with open(file_path, 'r', encoding='utf-8') as file:
        dml_string = file.read()
    return parse_dml(dml_string)

def main():
    """Main function to handle file input from the command line."""
    if len(sys.argv) != 2:
        print("Usage: python DML_Parser.py <path_to_dml_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        parsed_dml = parse_dml_file(file_path)
        print("Parsed DML:")
        print(json.dumps(parsed_dml, indent=4))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
