import json

import app as app_module
from app import app


def test_conversations_api_requires_login():
    client = app.test_client()
    response = client.get('/api/conversations')
    assert response.status_code == 401


def test_conversations_api_returns_user_threads_after_login():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 'demo-user'

    response = client.get('/api/conversations')
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload.get('conversations', []), list)


def test_doctors_api_filters_by_city_and_area():
    client = app.test_client()

    response = client.get('/api/doctors?q=Patia')
    assert response.status_code == 200
    payload = response.get_json()
    doctors = payload.get('doctors', [])
    assert doctors
    assert any('Patia' in doctor.get('area', '') or 'Patia' in doctor.get('address', '') for doctor in doctors)
    assert all('Patia' in doctor.get('area', '') or 'Patia' in doctor.get('address', '') or 'Bhubaneswar' in doctor.get('area', '') for doctor in doctors)

    response = client.get('/api/doctors?q=Bhubaneswar&specialty=general physician')
    assert response.status_code == 200
    payload = response.get_json()
    doctors = payload.get('doctors', [])
    assert doctors
    assert all('General Physician' == doctor.get('specialty') for doctor in doctors)
    assert any('Dr. Ananya Sharma' == doctor.get('name') for doctor in doctors)


def test_doctors_api_requires_area_before_returning_directory():
    client = app.test_client()

    response = client.get('/api/doctors')
    assert response.status_code == 400
    assert response.get_json().get('doctors') == []

    response = client.get('/api/doctors?q=   ')
    assert response.status_code == 400
    assert response.get_json().get('doctors') == []

    response = client.get('/api/doctors?q=Puri')
    assert response.status_code == 200
    assert response.get_json().get('doctors')


def test_tollfree_api_returns_health_guidance():
    client = app.test_client()

    response = client.post('/api/tollfree', json={
        'language': 'en',
        'problem': 'I have fever and weakness'
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload.get('success') is True
    assert 'fever' in payload.get('message', '').lower() or 'temperature' in payload.get('message', '').lower()
    assert payload.get('emergency') is False

    response = client.post('/api/tollfree', json={
        'language': 'en',
        'problem': 'I have chest pain and trouble breathing'
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload.get('success') is True
    assert payload.get('emergency') is True
    assert '112' in payload.get('message', '') or 'hospital' in payload.get('message', '').lower()


def test_tollfree_api_handles_odia_symptoms():
    client = app.test_client()

    response = client.post('/api/tollfree', json={
        'language': 'odia',
        'problem': 'ମୁଁ ଛାତିରେ ବେଦନା ଏବଂ ସ୍ୱାସ ନେବାରେ କଷ୍ଟ ହେଉଛି',
        'caller_number': '+919999999999'
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload.get('success') is True
    assert payload.get('emergency') is True
    assert '112' in payload.get('message', '') or 'hospital' in payload.get('message', '').lower()


def test_medicine_verification_api_returns_verified_status_for_authorized_medicine():
    client = app.test_client()

    response = client.post('/api/medicine/verify', json={
        'medicine': 'Paracetamol 500 mg',
        'identifier': 'PARA-500-ALPHA-2026-1234',
        'batch': 'ALPHA-2026',
        'manufacturer': 'GovMed Pharma'
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload.get('status') == 'verified'
    assert payload.get('verified') is True
    assert 'verified' in payload.get('message', '').lower()


def test_medicine_availability_api_returns_facility_statuses():
    client = app.test_client()

    response = client.get('/api/medicine/availability?medicine=Paracetamol+500+mg')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload.get('medicine') == 'Paracetamol 500 mg'
    assert any(item.get('facility') == 'PHC' for item in payload.get('facilities', []))
    assert any(item.get('facility') == 'Sub-centre' for item in payload.get('facilities', []))


def test_family_profiles_keep_records_and_vaccinations_owner_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'FAMILY_DATA_FILE', str(tmp_path / 'family_data.json'))
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 'family-owner-one'
        sess['username'] = 'Primary'

    initial = client.get('/api/family').get_json()
    assert [member['id'] for member in initial['members']] == ['self']

    response = client.post('/api/family/members', json={
        'name': 'Asha Kumari',
        'age': 8,
        'gender': 'female',
        'relation': 'child',
    })
    assert response.status_code == 201
    child = response.get_json()['member']

    symptom_response = client.post('/api/symptom', json={'symptom': 'fever'})
    assert symptom_response.status_code == 200
    client.post('/api/family/active', json={'member_id': 'self'})
    client.post('/api/checkin', json={'mood': 'Good', 'energy': 'Moderate'})
    client.post('/api/symptom', json={'symptom': 'fever'})
    client.post('/api/medicines', json={
        'name': 'Primary medicine', 'dose': '1 tablet', 'time': '08:00',
    })

    vaccine_response = client.post('/api/family/vaccinations', json={
        'member_id': child['id'],
        'name': 'Booster dose',
        'due_date': '2099-01-01',
    })
    assert vaccine_response.status_code == 201
    family = client.get('/api/family').get_json()
    assert family['records'][child['id']][0]['type'] == 'symptom'
    assert family['records']['self'][0]['type'] == 'symptom'
    assert family['records']['self'][1]['type'] == 'checkin'
    assert family['vaccinations'][0]['member_id'] == child['id']
    assert family['alerts'][0]['member_count'] == 2

    client.post('/api/family/active', json={'member_id': child['id']})
    report_response = client.post('/api/report/ocr', json={'text': 'Hemoglobin 11.0 g/dL'})
    assert report_response.status_code == 200
    client.post('/api/conversations', json={
        'title': 'Child symptom chat',
        'messages': [{'role': 'user', 'text': 'Fever since yesterday'}],
    })
    client.post('/api/family/active', json={'member_id': 'self'})
    assert client.get('/api/conversations').get_json()['conversations'] == []
    client.post('/api/family/active', json={'member_id': child['id']})
    assert len(client.get('/api/conversations').get_json()['conversations']) == 1
    assert client.get('/api/medicines').get_json()['medicines'] == []
    client.post('/api/medicines', json={
        'name': 'Child medicine', 'dose': '5 ml', 'time': '09:00',
    })
    client.post('/api/offline/sync', json={
        'checkins': [{'mood': 'Okay', 'energy': 'Low', 'notes': 'Offline check-in'}],
        'medicines': [{'name': 'Offline child medicine', 'dose': '2 ml', 'time': '12:00'}],
    })
    child_medicines = client.get('/api/medicines').get_json()['medicines']
    assert {medicine['name'] for medicine in child_medicines} == {'Child medicine', 'Offline child medicine'}
    child_history = client.get('/api/family').get_json()['records'][child['id']]
    assert any(record['type'] == 'checkin' for record in child_history)
    assert any(record['type'] == 'report' for record in child_history)
    client.post('/api/family/active', json={'member_id': 'self'})
    assert client.get('/api/medicines').get_json()['medicines'][0]['name'] == 'Primary medicine'

    other_client = app.test_client()
    with other_client.session_transaction() as sess:
        sess['user_id'] = 'family-owner-two'
        sess['username'] = 'Other'
    other_family = other_client.get('/api/family').get_json()
    assert [member['id'] for member in other_family['members']] == ['self']
    assert other_family['records'] == {}
    assert other_client.post('/api/family/active', json={'member_id': child['id']}).status_code == 404


def test_save_consultation_requires_login_and_uses_active_family_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'FAMILY_DATA_FILE', str(tmp_path / 'family_data.json'))
    client = app.test_client()
    assert client.post('/api/save-consultation', json={}).status_code == 401

    with client.session_transaction() as sess:
        sess['user_id'] = 'consult-owner'
        sess['username'] = 'Primary'
        sess['primary_profile'] = {'first_name': 'Primary', 'last_name': 'Member'}

    member_response = client.post('/api/family/members', json={
        'name': 'Asha', 'age': 32, 'gender': 'female', 'relation': 'spouse',
    })
    member = member_response.get_json()['member']
    doctor = next(item for item in app_module.get_doctor_directory() if item['name'] == 'Dr. Meera Das')
    doctor_id = 'dr-meera-das'
    response = client.post('/api/save-consultation', json={
        'doctor_id': doctor_id,
        'doctor_name': doctor['name'],
        'duration_seconds': 82,
        'call_type': 'video',
    })

    assert response.status_code == 201
    record = response.get_json()['consultation']
    assert record['member_id'] == member['id']
    assert record['doctor_id'] == doctor_id
    assert record['duration_seconds'] == 82
    assert record['call_type'] == 'video'
    assert record['summary'].endswith('01:22')

    invalid_response = client.post('/api/save-consultation', json={
        'doctor_id': doctor_id, 'doctor_name': doctor['name'], 'duration_seconds': 20, 'call_type': 'video-sdk',
    })
    assert invalid_response.status_code == 400

    unknown_doctor_response = client.post('/api/save-consultation', json={
        'doctor_id': 'unknown-doctor', 'doctor_name': 'Dr. Unknown',
        'duration_seconds': 20, 'call_type': 'video',
    })
    assert unknown_doctor_response.status_code == 400


def test_consult_doctor_directory_has_at_least_20_doctors_and_multiple_specialties():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 'consult-directory-owner'
        sess['username'] = 'Primary'

    response = client.get('/api/consult-doctors')
    assert response.status_code == 200
    payload = response.get_json()
    doctors = payload['doctors']
    assert len(doctors) >= 20
    assert len(payload['specialties']) >= 8
    assert len({doctor['id'] for doctor in doctors}) == len(doctors)
    assert all(doctor.get('name') and doctor.get('specialty') and doctor.get('facility') for doctor in doctors)


def test_consult_page_renders_for_signed_in_user_without_video_sdk():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 'consult-page-owner'
        sess['username'] = 'Primary'
        sess['primary_profile'] = {'first_name': 'Primary', 'last_name': 'Member'}

    response = client.get('/page/consult')

    assert response.status_code == 200
    assert b'Consult a Doctor' in response.data
    assert b'/static/js/consult.js' in response.data
    assert b'/static/css/consult.css' in response.data
    assert b'twilio' not in response.data.lower()
