from .people import get_person_data


def build_contributor_data():
    return {
        'contributors': {
            'directors': [
                {
                    'name': 'Open Mic Odyssey Team',
                    'job_title': 'Director',
                    'url': 'https://openmicodyssey.com',
                    'same_as': ['https://openmicodyssey.com'],
                    'credit_note': 'Shapes the documentary point of view and guides the on-the-road narrative structure.',
                }
            ],
            'producers': [
                {
                    'name': 'Open Mic Odyssey Team',
                    'job_title': 'Producer',
                    'url': 'https://openmicodyssey.com',
                    'same_as': ['https://openmicodyssey.com'],
                    'credit_note': 'Coordinates production, release planning, and how the film reaches audiences.',
                },
                {
                    **get_person_data(
                        'Georg Sinn',
                        job_title='Producer',
                        credit_note='Infrastructure, logistics, IT, development, finance.',
                        url='https://allucanget.biz',
                    ),
                }
            ],
            'actors': [
                {
                    **get_person_data(
                        'Bobby Ludlam',
                        job_title='Self',
                        credit_note='One of the three best friends at the heart of the documentary, a comedian chasing stage time and a bigger creative dream.',
                    ),
                },
                {
                    **get_person_data(
                        'Corey Pellizzi',
                        job_title='Self',
                        credit_note='Directing, filming, and drawn to places of his childhood, creativity and freedom.',
                    ),
                },
                {
                    **get_person_data(
                        'Georg Sinn',
                        job_title='Self',
                        credit_note='From far away, driving across America and keeping the crew rolling toward the next place to film, perform, and connect with the comedy world.',
                    ),
                }
            ],
        }
    }
