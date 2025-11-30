# utils/markdown_formatter.py
# Функция для конвертации Markdown в HTML

import re

def markdown_to_html(md):
    # Экранирование специальных символов
    md = re.sub(r'&', '&amp;', md)
    md = re.sub(r'<', '&lt;', md)
    md = re.sub(r'>', '&gt;', md)

    # Ссылки [text](url)
    md = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', md)

    # Жирный **text**
    md = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', md)

    # Курсив *text*
    md = re.sub(r'\*(.*?)\*', r'<i>\1</i>', md)

    # Обработка строк
    lines = md.split('\n')
    html_lines = []
    in_list = False
    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<p></p>')
            continue
        if line.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<h1>' + line[2:].strip() + '</h1>')
        elif line.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<h2>' + line[3:].strip() + '</h2>')
        elif line.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<h3>' + line[4:].strip() + '</h3>')
        elif line.startswith('- ') or line.startswith('* '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append('<li>' + line[2:].strip() + '</li>')
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<p>' + line + '</p>')
    if in_list:
        html_lines.append('</ul>')
    return ''.join(html_lines)