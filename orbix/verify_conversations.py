from app import app

client = app.test_client()

resp = client.get('/api/conversations')
print('NO_LOGIN', resp.status_code, resp.get_json())

with client.session_transaction() as sess:
    sess['user_id'] = 'demo-user'

resp = client.get('/api/conversations')
print('WITH_LOGIN', resp.status_code, resp.get_json())

resp = client.post(
    '/api/conversations',
    json={
        'conversation_id': 'demo-chat-1',
        'title': 'Headache & Fatigue',
        'messages': [
            {'role': 'user', 'text': 'I have a headache', 'timestamp': '2026-09-18T00:00:00'},
            {'role': 'bot', 'text': 'Tell me more', 'timestamp': '2026-09-18T00:00:01'}
        ]
    }
)
print('POST', resp.status_code, resp.get_json())

resp = client.get('/api/conversations')
conversations = resp.get_json()['conversations']
print('LIST', resp.status_code, len(conversations), conversations[0]['title'])
