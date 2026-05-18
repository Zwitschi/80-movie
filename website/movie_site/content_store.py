from . import content_store_db
from flask import current_app, has_app_context


class ContentReadError(RuntimeError):
    pass


class ContentWriteError(RuntimeError):
    pass


def get_content_reader():
    return content_store_db.get_content_reader()


def get_content_writer():
    return content_store_db.get_content_writer()
