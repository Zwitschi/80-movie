from __future__ import annotations

import logging

from flask import jsonify, redirect, render_template, request, url_for

logger = logging.getLogger(__name__)


def syndication_page():
    from . import admin_bot

    return render_template(
        'syndication.html',
        syndication=admin_bot.build_syndication_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def syndication_api():
    from . import admin_bot

    return jsonify({'data': admin_bot.build_syndication_snapshot()})


def syndication_sources_api():
    from . import admin_bot

    snapshot = admin_bot.build_syndication_snapshot()
    return jsonify({'data': snapshot['sources'], 'meta': {'status': snapshot['status']}})


def syndication_channels_api():
    from . import admin_bot

    snapshot = admin_bot.build_syndication_snapshot()
    return jsonify({'data': snapshot['channel_bindings'], 'meta': {'status': snapshot['status']}})


def retry_syndication_source_api(source_key: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state, meta = admin_bot._run_manual_syndication_retry(
            source_key)
        logger.info(
            "Syndication retry triggered via API: source=%s", source_key)
    except admin_bot.ConfigError as exc:
        logger.warning("Syndication retry config error: %s", exc)
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        logger.warning("Syndication retry source not found: %s", source_key)
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404
    except Exception as exc:
        logger.error("Syndication retry failed: %s", exc, exc_info=True)
        return jsonify({'error': {'code': 'syndication_retry_failed', 'message': str(exc)}}), 500

    return jsonify({'data': source_state, 'meta': meta})


def retry_syndication_source_page_action(source_key: str):
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_syndication_scope_error()

    try:
        admin_bot._run_manual_syndication_retry(source_key)
        logger.info(
            "Syndication retry triggered via page: source=%s", source_key)
    except admin_bot.ConfigError:
        return admin_bot._page_syndication_config_error()
    except KeyError:
        return redirect(url_for('bot.syndication_page', error='source-not-found'))
    except Exception:
        return redirect(url_for('bot.syndication_page', error='retry-failed'))

    return redirect(url_for('bot.syndication_page', saved='retry'))


def reset_syndication_checkpoint_api(source_key: str):
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        source_state = admin_bot._reset_syndication_checkpoint(source_key)
        logger.info(
            "Syndication checkpoint reset via API: source=%s", source_key)
    except admin_bot.ConfigError as exc:
        logger.warning("Syndication checkpoint reset config error: %s", exc)
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except KeyError:
        logger.warning(
            "Syndication checkpoint reset source not found: %s", source_key)
        return jsonify({'error': {'code': 'syndication_source_not_found', 'message': 'Configured syndication source was not found.'}}), 404

    return jsonify({'data': source_state})


def reset_syndication_checkpoint_page_action(source_key: str):
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_syndication_scope_error()

    try:
        admin_bot._reset_syndication_checkpoint(source_key)
        logger.info(
            "Syndication checkpoint reset via page: source=%s", source_key)
        return admin_bot._page_syndication_config_error()
    except KeyError:
        return redirect(url_for('bot.syndication_page', error='source-not-found'))

    return redirect(url_for('bot.syndication_page', saved='checkpoint-reset'))
