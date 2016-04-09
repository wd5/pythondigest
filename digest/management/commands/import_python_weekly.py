# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from urllib.error import URLError
from urllib.request import urlopen

import lxml.html as html
from bs4 import BeautifulSoup
from bs4.element import Tag
from django.core.management.base import BaseCommand
from lxml import etree

from digest.management.commands import apply_parsing_rules, apply_video_rules, save_item
from digest.models import ParsingRules, Section, ITEM_STATUS_CHOICES, Resource


def _get_content(url: str) -> str:
    try:
        result = urlopen(url, timeout=10).read()
    except URLError:
        return ''
    else:
        return result


def _get_blocks(url) -> list:
    result = []
    content = _get_content(url)
    if content:
        try:
            page = html.parse(content)
            result = page.getroot().find_class('bodyTable')[0].xpath('//span[@style="font-size:14px"]')
        except OSError:
            page = BeautifulSoup(content, 'lxml')
            result = page.findAll('table', {'class': 'bodyTable'})[0].findAll('span', {'style': "font-size:14px"})
    return result


def _get_block_item(block) -> dict:
    resource = Resource.objects.get(title='PythonWeekly')
    if isinstance(block, Tag):
        link = block.findAll('a')[0]
        url = link['href']
        title = link.string
        try:
            text = str(block.nextSibling.nextSibling).replace('<br/>', '').strip()
        except AttributeError:
            return {}
    else:
        link = block.cssselect('a')[0]
        url = link.attrib['href']
        title = link.text
        _text = block.getnext()
        if _text is None:
            return {}
        text = etree.tostring(block.getnext()).decode('utf-8').replace('<br/>', '').strip()

    return {
        'title': title,
        'link': url,
        'raw_content': text,
        'http_code': 200,
        'content': text,
        'description': text,
        'resource': resource,
        'language': 'en',
    }


def _apply_rules_wrap(**kwargs):
    rules = kwargs

    def _apply_rules(item: dict) -> dict:
        item.update(
            apply_parsing_rules(item, **rules)
            if kwargs.get('query_rules') else {})
        return apply_video_rules(item.copy())

    return _apply_rules


def main(url):
    data = {
        'query_rules': ParsingRules.objects.filter(is_activated=True).all(),
        'query_sections': Section.objects.all(),
        'query_statuses': [x[0] for x in ITEM_STATUS_CHOICES],
    }
    _apply_rules = _apply_rules_wrap(**data)

    list(map(save_item, map(_apply_rules, map(_get_block_item, _get_blocks(url)))))


# Написать тест с использованием ссылки
# http://us2.campaign-archive.com/?u=e2e180baf855ac797ef407fc7&id=d4b2a101de
# http://us2.campaign-archive.com/?u=e2e180baf855ac797ef407fc7&id=0a5d4ce3e5
# http://us2.campaign-archive.com/?u=e2e180baf855ac797ef407fc7&id=a68acae6d6

class Command(BaseCommand):
    args = 'no arguments!'
    help = u''

    def add_arguments(self, parser):
        parser.add_argument('url', type=str)

    def handle(self, *args, **options):
        if 'url' in options:
            main(options['url'])
        else:
            print('Not found folder path')
