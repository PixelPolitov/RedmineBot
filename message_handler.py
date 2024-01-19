#!/usr/bin/env python
import html


def message_handler(data: dict) -> str:
    issue_id = data['data']['issue']['id']
    project_name = data['data']['issue']['project']['name']
    subject = data['data']['issue']['subject']
    changes = data['data']['issue']['changes']

    message_parts = []
    attachment_id = []
    attachment_names = []

    message_parts.append(f"[{project_name} - #{issue_id}] {subject}")

    for change in changes:
        user_name = change['user']['name']

        details_text = []
        for detail in change.get('details', []):
            if detail['property'] == 'attachment':
                attachment_id.append(detail['name'])
                attachment_names.append(detail['new_value'])
            else:
                handler = DETAIL_HANDLERS.get(detail['name'])
                if handler:
                    details_text.append(handler(detail))

        if details_text:
            message_parts.append("\n".join(details_text))

        # Проверка на наличие комментария
        if 'notes' in change:
            notes = html.unescape(change['notes'])
            message_parts.append(
                f"<strong>{user_name} писал(а)</strong>:\n---\n{notes}")

    return "\n\n".join(message_parts), attachment_id, attachment_names


def handle_status(detail) -> str:
    return f"<strong>Статус:</strong> {detail['new_value']}"


def handle_assigne(detail) -> str:
    return f"<strong>Назначена:</strong> {detail['new_value']}"


DETAIL_HANDLERS = {
    'status_id': handle_status,
    'assigned_to_id': handle_assigne
}
