from pathlib import Path

import pytest

from website.movie_site.content_store import (
    CONTENT_FILES,
    ContentReadError,
    ContentWriteError,
    JsonContentReader,
    JsonContentWriter,
)


def test_content_reader_can_read_known_file():
    reader = JsonContentReader()
    data = reader.read('movies.json')
    assert 'movie' in data


def test_content_reader_rejects_unknown_file():
    reader = JsonContentReader()
    with pytest.raises(ContentReadError, match='Unsupported content file'):
        reader.read('unknown.json')


def test_content_reader_read_all_includes_registry_files():
    reader = JsonContentReader()
    all_data = reader.read_all()
    assert set(all_data.keys()) == set(sorted(CONTENT_FILES))


def test_content_reader_raises_on_missing_file(tmp_path: Path):
    reader = JsonContentReader(data_dir=tmp_path)
    with pytest.raises(ContentReadError, match='Content file not found'):
        reader.read('movies.json')


def test_content_writer_writes_valid_payload_with_formatting(tmp_path: Path):
    writer = JsonContentWriter(data_dir=tmp_path)
    payload = {'movie': {'title': 'Demo'}}

    output_path = writer.write('movies.json', payload)

    assert output_path.exists()
    text = output_path.read_text(encoding='utf-8')
    assert text.endswith('\n')
    assert '  "movie"' in text


def test_content_writer_rejects_unknown_file(tmp_path: Path):
    writer = JsonContentWriter(data_dir=tmp_path)
    with pytest.raises(ContentWriteError, match='Unsupported content file'):
        writer.write('unknown.json', {'a': 1})


def test_content_writer_rejects_invalid_schema_payload(tmp_path: Path):
    writer = JsonContentWriter(data_dir=tmp_path)
    with pytest.raises(ContentWriteError, match='Schema validation failed'):
        writer.write('movies.json', {'not_movie': {}})


def test_content_writer_round_trip_with_reader(tmp_path: Path):
    source_reader = JsonContentReader()
    payload = source_reader.read('faq.json')

    writer = JsonContentWriter(data_dir=tmp_path)
    writer.write('faq.json', payload)

    temp_reader = JsonContentReader(data_dir=tmp_path)
    assert temp_reader.read('faq.json') == payload
