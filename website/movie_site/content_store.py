import json
from pathlib import Path

from jsonschema import ValidationError, validate


DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# Central registry for editable content files used by the site/admin.
CONTENT_FILES = {
    'content.json',
    'events.json',
    'faq.json',
    'gallery.json',
    'media_assets.json',
    'movies.json',
    'offers.json',
    'organizations.json',
    'people.json',
    'reviews.json',
    'social.json',

    'connect.json',
}

CONTENT_SCHEMAS = {
    'content.json': {
        'type': 'object',
        'required': ['pages'],
        'properties': {'pages': {'type': 'object'}},
    },
    'events.json': {
        'type': 'object',
        'required': ['events'],
        'properties': {'events': {'type': 'array'}},
    },
    'faq.json': {
        'type': 'object',
        'required': ['faq'],
        'properties': {'faq': {'type': 'array'}},
    },
    'gallery.json': {
        'type': 'object',
        'required': ['gallery'],
        'properties': {'gallery': {'type': 'array'}},
    },
    'media_assets.json': {
        'type': 'object',
        'required': ['media'],
        'properties': {'media': {'type': 'object'}},
    },
    'movies.json': {
        'type': 'object',
        'required': ['movie'],
        'properties': {'movie': {'type': 'object'}},
    },
    'offers.json': {
        'type': 'object',
        'required': ['offers'],
        'properties': {'offers': {'type': 'array'}},
    },
    'organizations.json': {
        'type': 'object',
        'required': ['organizations'],
        'properties': {'organizations': {'type': 'object'}},
    },
    'people.json': {
        'type': 'object',
        'required': ['people', 'contributors', 'credits_people'],
        'properties': {
            'people': {'type': 'object'},
            'contributors': {'type': 'object'},
            'credits_people': {'type': 'array'},
        },
    },
    'reviews.json': {
        'type': 'object',
        'required': ['reviews', 'aggregate_rating'],
        'properties': {
            'reviews': {'type': 'array'},
            'aggregate_rating': {'type': 'object'},
        },
    },
    'social.json': {
        'type': 'object',
        'required': ['social'],
        'properties': {'social': {'type': 'array'}},
    },
    'connect.json': {
        'type': 'object',
        'required': ['connect'],
        'properties': {'connect': {'type': 'object'}},
    },
}


class ContentReadError(RuntimeError):
    pass


class ContentWriteError(RuntimeError):
    pass


class JsonContentReader:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir

    def read(self, filename: str):
        if filename not in CONTENT_FILES:
            raise ContentReadError(f'Unsupported content file: {filename}')

        file_path = self.data_dir / filename
        if not file_path.exists():
            raise ContentReadError(f'Content file not found: {file_path}')

        try:
            with file_path.open('r', encoding='utf-8') as file:
                return json.load(file)
        except json.JSONDecodeError as exc:
            raise ContentReadError(
                f'Invalid JSON in content file {filename}: {exc}'
            ) from exc

    def read_all(self) -> dict:
        return {filename: self.read(filename) for filename in sorted(CONTENT_FILES)}


class JsonContentWriter:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir

    def _validate_filename(self, filename: str) -> None:
        if filename not in CONTENT_FILES:
            raise ContentWriteError(f'Unsupported content file: {filename}')

    def validate_payload(self, filename: str, payload) -> None:
        self._validate_filename(filename)
        schema = CONTENT_SCHEMAS.get(filename)
        if schema is None:
            raise ContentWriteError(f'No schema registered for: {filename}')

        try:
            validate(instance=payload, schema=schema)
        except ValidationError as exc:
            raise ContentWriteError(
                f'Schema validation failed for {filename}: {exc.message}'
            ) from exc

    def write(self, filename: str, payload) -> Path:
        self.validate_payload(filename, payload)
        file_path = self.data_dir / filename
        self.data_dir.mkdir(parents=True, exist_ok=True)

        try:
            text = json.dumps(payload, indent=2) + '\n'
            file_path.write_text(text, encoding='utf-8')
        except OSError as exc:
            raise ContentWriteError(
                f'Failed writing content file {filename}: {exc}'
            ) from exc

        return file_path


def get_content_reader() -> JsonContentReader:
    return JsonContentReader()


def get_content_writer() -> JsonContentWriter:
    return JsonContentWriter()
