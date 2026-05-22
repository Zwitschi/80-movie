from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for


def commands_page():
    from . import admin_bot

    return render_template(
        'commands.html',
        commands_snapshot=admin_bot.build_bot_commands_snapshot(),
        save_success=request.args.get('saved'),
        error=request.args.get('error'),
    )


def commands_api():
    from . import admin_bot

    return jsonify({'data': admin_bot.build_bot_commands_snapshot()})


def poll_all_sources_api():
    from . import admin_bot

    scope_error = admin_bot.require_operator_scope('syndication.write')
    if scope_error is not None:
        return scope_error

    try:
        result = admin_bot._run_manual_syndication_poll_all()
    except admin_bot.ConfigError as exc:
        return jsonify({'error': {'code': 'invalid_syndication_config', 'message': str(exc)}}), 409
    except Exception as exc:
        return jsonify({'error': {'code': 'command_failed', 'message': str(exc)}}), 500

    return jsonify({'data': result})


def poll_all_sources_page_action():
    from . import admin_bot

    if not admin_bot._operator_can('syndication.write'):
        return admin_bot._page_commands_scope_error()

    try:
        admin_bot._run_manual_syndication_poll_all()
    except admin_bot.ConfigError:
        return admin_bot._page_commands_error()
    except Exception:
        return redirect(url_for('bot.commands_page', error='command-failed'))

    return redirect(url_for('bot.commands_page', saved='poll-all'))