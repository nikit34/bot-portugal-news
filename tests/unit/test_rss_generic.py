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


def test_upgrade_strips_wordpress_size_suffix():
    # WP thumbnail → full-size original (drop the -WxH before the extension).
    assert g._upgrade_image_url('https://s.com/wp/feijoada-150x150.jpg') == 'https://s.com/wp/feijoada.jpg'
    assert g._upgrade_image_url('https://s.com/wp/Dadinho-120x100.JPG') == 'https://s.com/wp/Dadinho.JPG'
    # No size suffix / plain URL is left untouched (must not corrupt normal feeds).
    assert g._upgrade_image_url('https://s.com/wp/bolo.jpg') == 'https://s.com/wp/bolo.jpg'
    assert g._upgrade_image_url('https://x.com/img.jpg') == 'https://x.com/img.jpg'
    assert g._upgrade_image_url('') == ''


def test_upgrade_rewrites_blogger_crop_to_full():
    # Blogger /s72-c/ (72px) → /s1600/ full; only rewritten for googleusercontent hosts.
    small = 'https://blogger.googleusercontent.com/img/b/R29v/AVvXsEg/s72-c/frango.jpg'
    assert g._upgrade_image_url(small) == 'https://blogger.googleusercontent.com/img/b/R29v/AVvXsEg/s1600/frango.jpg'
    assert g._upgrade_image_url(
        'https://blogger.googleusercontent.com/img/b/R29v/AVvXsEg/s320/x.jpg'
    ) == 'https://blogger.googleusercontent.com/img/b/R29v/AVvXsEg/s1600/x.jpg'


def test_first_image_applies_upgrade():
    # End-to-end: extractor returns the upgraded (full-size) URL.
    assert g._first_image(
        {'media_thumbnail': [{'url': 'https://s.com/wp/receita-150x150.jpg'}]}
    ) == 'https://s.com/wp/receita.jpg'
