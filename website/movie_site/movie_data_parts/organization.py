from .people import get_person_data


def build_production_company_data():
    return {
        'production_company': {
            'name': 'Open Mic Odyssey Productions',
            'url': 'https://openmicodyssey.com',
            'same_as': [
                'https://openmicodyssey.com',
                'https://www.youtube.com/@openmicodyssey',
                'https://www.instagram.com/openmicodyssey',
                'https://www.tiktok.com/@openmicodyssey',
                'https://www.patreon.com/openmicodyssey',
            ],
            'people': [
                get_person_data(
                    'Corey Pellizzi',
                    job_title='Director, Producer',
                ),
                get_person_data(
                    'Georg Sinn',
                    job_title='Producer',
                    url='https://allucanget.biz',
                ),
            ],
        }
    }
