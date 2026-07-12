import src.parsers.rss.channels.generic as g


def test_parse_generic_title_summary_and_media_content_image():
    entry = {
        'title': 'Bolo de cenoura fácil',
        'summary': '<p>Uma <b>receita</b> simples &amp; rápida</p>',
        'media_content': [{'url': 'https://x.com/img.jpg'}],
    }
    msg, img = g.parse_generic(entry)
    assert 'Bolo de cenoura fácil' in msg and 'receita' in msg
    assert '<' not in msg and '&amp;' not in msg and '&' in msg  # entities decoded, tags stripped
    assert img == 'https://x.com/img.jpg'


def test_first_image_from_enclosure_img_tag_and_content():
    assert g._first_image({'enclosures': [{'href': 'https://x/e.png', 'type': 'image/png'}]}) == 'https://x/e.png'
    assert g._first_image({'summary': 'blah <img src="https://x/in.jpg" /> more'}) == 'https://x/in.jpg'
    assert g._first_image({'content': [{'value': "<img src='https://x/c.webp'>"}]}) == 'https://x/c.webp'
    assert g._first_image({'summary': 'no image here'}) == ''


def test_is_valid_generic_requires_title_and_image():
    assert g.is_valid_generic_entry({'title': 't', 'media_thumbnail': [{'url': 'https://x/i.jpg'}]}) is True
    assert g.is_valid_generic_entry({'title': 't'}) is False                       # no image
    assert g.is_valid_generic_entry({'media_content': [{'url': 'https://x/i.jpg'}]}) is False  # no title


def test_strip_html_handles_cdata_and_entities():
    assert g._strip_html('<![CDATA[<p>a &amp; b</p>]]>') == 'a & b'
    assert g._strip_html('') == ''


def test_parse_generic_no_summary_uses_title_only():
    msg, img = g.parse_generic({'title': 'Só título', 'media_content': [{'url': 'https://x/i.jpg'}]})
    assert msg == 'Só título'
