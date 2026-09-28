from app import knowledge_search

questions = [
    'What foods help maintain normal blood sugar levels?',
    'What is a normal heart rate?',
    'What are normal sleep hours for adults?',
    'What is normal hemoglobin level?'
]

for q in questions:
    result = knowledge_search(q)
    print('QUERY:', q)
    print('ANSWER:', result['answer'])
    print('SOURCES:', len(result.get('sources', [])))
    print('---')
