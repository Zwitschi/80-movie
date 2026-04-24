from copy import deepcopy


PERSON_RECORDS = {
    'Bobby Ludlam': {
        'name': 'Bobby Ludlam',
        'url': 'https://www.bobbyludlam.com',
        'same_as': [
            'https://www.bobbyludlam.com',
            'https://www.instagram.com/bobbyludlam/',
        ],
    },
    'Corey Pellizzi': {
        'name': 'Corey Pellizzi',
        'url': 'https://instagram.com/owlmovement',
        'same_as': ['https://instagram.com/owlmovement'],
    },
    'Georg Sinn': {
        'name': 'Georg Sinn',
        'url': 'https://zwitschi.net',
        'same_as': [
            'https://zwitschi.net',
            'https://allucanget.biz',
            'https://www.instagram.com/allucanget',
        ],
    },
}


def get_person_data(name, **overrides):
    person = deepcopy(PERSON_RECORDS[name])
    for key, value in overrides.items():
        if value is None:
            continue
        person[key] = value

    if 'same_as' in overrides and overrides['same_as'] is not None:
        person['same_as'] = list(dict.fromkeys(overrides['same_as']))

    return person


def build_credits_people_data():
    return {
        'credits_people': [
            get_person_data(
                'Bobby Ludlam',
                roles=['Comedian', 'Security'],
                primary_url='https://www.bobbyludlam.com',
            ),
            get_person_data(
                'Corey Pellizzi',
                roles=['Comedian', 'Director', 'Producer', 'Security'],
                primary_url='https://instagram.com/owlmovement',
            ),
            get_person_data(
                'Georg Sinn',
                roles=['Manager', 'Driver', 'Traveler', 'Security'],
                primary_url='https://zwitschi.net',
            ),
        ],
    }
