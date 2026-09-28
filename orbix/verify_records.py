import app as server

client = server.app.test_client()
with client.session_transaction() as session:
    session['user_id'] = 'd1e08a1d-3001-4001-a7c3-ed5f8f8c7b1a'

r = client.get('/api/records')
print('GET_STATUS', r.status_code)
print('GET_LEN', len(r.get_json().get('records', [])))

r2 = client.post(
    '/api/records',
    json={
        'name': 'Lipid Profile',
        'type': 'Lab report',
        'date': '18 Sep 2026',
        'status': 'Reviewed',
        'summary': 'Updated after scan',
    },
)
print('POST_STATUS', r2.status_code)
print('POST_SUCCESS', r2.get_json().get('success'))
print('POST_LEN', len(r2.get_json().get('records', [])))

page = client.get('/page/records')
print('PAGE_STATUS', page.status_code)
print('HAS_FORM', 'id="recordForm"' in page.get_data(as_text=True))
print('HAS_ADD_BUTTON', 'id="toggleRecordForm"' in page.get_data(as_text=True))
