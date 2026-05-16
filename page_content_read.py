import json
import os

JSON_DIR = 'website\\data'


def load_json_file(filename):
    filepath = os.path.join(JSON_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as file:
        return json.load(file)


def escape_value(value):
    if isinstance(value, str) and value.startswith('http'):
        return f'<{value}>'
    if isinstance(value, str) and '@' in value:
        return f'<{value}>'
    return value


def markdown_list(items, indent=0, level=1):
    md = ''
    for item in items:
        if isinstance(item, dict):
            label = item.get('label', '')
            title = item.get('title', label)
            name = item.get('name', title)
            md += f'\n{"#" * level} {escape_value(name)}\n\n'
            md += markdown_dict(item, indent + 2, level + 1)
        elif isinstance(item, list):
            md += markdown_list(item, indent + 2, level + 1)
        else:
            md += f'- {escape_value(item)}\n'
        md += '\n\n'
    return md


def markdown_dict(data, indent=0, level=1):
    md = ''
    for key, value in data.items():
        if key == 'keywords':
            continue
        if isinstance(value, dict):
            md += f'\n{"#" * level} {escape_value(key)}\n\n'
            md += markdown_dict(value, indent + 2, level + 1)
        elif isinstance(value, list):
            md += f'\n{"#" * level} {escape_value(key)}\n\n'
            md += markdown_list(value, indent + 2, level + 1)
        else:
            md += f'- **{escape_value(key)}:** {escape_value(value)}\n'
        md += '\n\n'
    return md


def main():
    json_dir = 'website\\data'

    markdown_content = "# Movie Data\n\n"
    for filename in os.listdir(json_dir):
        if not filename.endswith('.json'):
            continue

        if not filename in ['connect.json', 'content.json', 'media_assets.json']:
            continue

        data = load_json_file(filename)

        markdown_content += markdown_dict(data, indent=0, level=2) + '\n\n'
        # replace \n\n\n with \n\n until there are no more occurrences
        while '\n\n\n' in markdown_content:
            markdown_content = markdown_content.replace('\n\n\n', '\n\n')

    with open('movie_data.md', 'w', encoding='utf-8') as md_file:
        md_file.write(markdown_content)


if __name__ == '__main__':
    main()
