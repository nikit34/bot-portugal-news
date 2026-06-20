import os

from PIL import Image

import src.producers.cards as cards


class _Ent:
    def __init__(self, text, label):
        self.text = text
        self.label_ = label


class _Doc:
    def __init__(self, ents=()):
        self.ents = list(ents)


def _img(path, size=(1200, 800)):
    Image.new('RGB', size, (30, 90, 50)).save(path)
    return str(path)


def test_eligible_requires_money_and_entity():
    doc = _Doc([_Ent('Sporting', 'ORG')])
    assert cards.is_transfer_card_eligible('Sporting paga 80 milhões por Gyokeres', doc)
    assert cards.is_transfer_card_eligible('Transferência fechada por €80M', doc)


def test_not_eligible_without_money():
    doc = _Doc([_Ent('Benfica', 'ORG')])
    assert not cards.is_transfer_card_eligible('Benfica vence o Porto por 2-1', doc)


def test_not_eligible_without_entity():
    assert not cards.is_transfer_card_eligible('Negócio de 80 milhões fechado', _Doc([]))


def test_render_card_produces_4x5_jpeg(tmp_path):
    src = _img(tmp_path / 'src.png')
    out = cards.render_card(src, 'Sporting vende Gyokeres por 80 milhões')
    assert out and os.path.isfile(out)
    assert out.endswith('.card.jpg')
    with Image.open(out) as img:
        assert img.size == (cards.CARD_W, cards.CARD_H)
        assert img.format == 'JPEG'


def test_render_card_none_on_unreadable(tmp_path):
    bad = tmp_path / 'bad.jpg'
    bad.write_bytes(b'not-an-image')
    assert cards.render_card(str(bad), 'headline') is None


def test_build_card_disabled_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(cards, 'CARDS_ENABLED', False)
    src = _img(tmp_path / 'src.png')
    assert cards.build_card_image(src, 'Sporting paga 80 milhões', _Doc([_Ent('Sporting', 'ORG')])) is None


def test_build_card_renders_for_eligible(tmp_path, monkeypatch):
    monkeypatch.setattr(cards, 'CARDS_ENABLED', True)
    src = _img(tmp_path / 'src.png')
    out = cards.build_card_image('%s' % src, 'Sporting paga 80 milhões por Gyokeres',
                                 _Doc([_Ent('Sporting', 'ORG')]))
    assert out and os.path.isfile(out)
    with Image.open(out) as img:
        assert img.size == (cards.CARD_W, cards.CARD_H)


def test_build_card_none_when_not_transfer(tmp_path, monkeypatch):
    monkeypatch.setattr(cards, 'CARDS_ENABLED', True)
    src = _img(tmp_path / 'src.png')
    assert cards.build_card_image(src, 'Benfica vence o Porto', _Doc([_Ent('Benfica', 'ORG')])) is None
