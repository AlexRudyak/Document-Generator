"""Programming languages selectable for a ``code`` block.

Single source of truth: ``schemas.BlockSchema`` validates against these keys, the
editor's language dropdown is rendered from them (see the ``/`` route), and
``code_service`` resolves each key to a Pygments lexer. Keys are Pygments lexer
aliases; ``text`` means "no highlighting".
"""

from collections import OrderedDict

DEFAULT_CODE_LANGUAGE = 'text'

CODE_LANGUAGES = OrderedDict([
    ('text', 'טקסט רגיל'),
    ('python', 'Python'),
    ('javascript', 'JavaScript'),
    ('typescript', 'TypeScript'),
    ('java', 'Java'),
    ('csharp', 'C#'),
    ('cpp', 'C++'),
    ('c', 'C'),
    ('go', 'Go'),
    ('rust', 'Rust'),
    ('php', 'PHP'),
    ('ruby', 'Ruby'),
    ('kotlin', 'Kotlin'),
    ('swift', 'Swift'),
    ('sql', 'SQL'),
    ('html', 'HTML'),
    ('xml', 'XML'),
    ('css', 'CSS'),
    ('json', 'JSON'),
    ('yaml', 'YAML'),
    ('bash', 'Bash'),
    ('powershell', 'PowerShell'),
])
