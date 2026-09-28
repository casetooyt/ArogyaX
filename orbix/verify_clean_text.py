from app import clean_markdown_text

samples = [
    '**Important** and *test*',
    '### Heading\n- one\n- two',
    'This **looks** clean.'
]

for sample in samples:
    print(clean_markdown_text(sample))
