
import re
import uuid
import os.path
import sqlite3

from flask import url_for
from scss import Scss

from googletranslate.googletranslate import main as gtranslate

from . import Config, get_db
from .dbdict_query import DBDict
from .mdict_query2 import IndexBuilder2


regex_style = re.compile(r'<style.+?</style>', re.DOTALL | re.IGNORECASE)
regex_ln = re.compile(r'<(p|br|tr)[^>]*?>', re.IGNORECASE)
regex_tag = re.compile(r'<[^>]+?>')


def ecdict_query_word(word, item=None):
    db = get_db('ecdict')
    if not db:
        return []
    sql = 'SELECT * FROM ecdict where WORD = ?'
    cursor = db.execute(sql, (word, ))
    trans = []
    EXCHANGE = {
        'p': '过去式',
        'd': '过去分词',
        'i': '现在分词',
        '3': '第三人称单数',
        'r': '形容词比较级',
        't': '形容词最高级',
        's': '名词复数形式',
        '0': '词根',
        '1': '词根变换',
    }
    for row in cursor:
        exchanges = []
        for e in row['exchange'].split('/'):
            t, w = e.split(':')
            exchanges.append('%s: %s' % (EXCHANGE[t], w))
        t = '%(word)s [%(phonetic)s]<br />XXX<br /><ul><li>%(definition)s</li><li>%(translation)s</li></ul>' % row
        t = t.replace('\\n', '<br />')
        t = t.replace('XXX', ' '.join(exchanges))
        trans.append(t)
    return trans


def ecdict_random_word(tag):
    word = ['hello']
    db = get_db('ecdict')
    if not db:
        return word[0]
    sql = 'SELECT word FROM ecdict WHERE word IN (SELECT word FROM ecdict WHERE ecdict.tag like ? ORDER BY RANDOM() LIMIT 1)'
    cursor = db.execute(sql, ('%%%s%%' % tag, ))
    row = cursor.fetchone()
    return row['word']


def query_word_meta(word):
    TAGs = {
        'zk': '中考',
        'gk': '高考',
        'ky': '考研',
        'cet4': 'CET-4',
        'cet6': 'CET-6',
        'gre': 'GRE',
        'toefl': 'TOEFL',
        'ielts': 'IELTS',
    }
    db = get_db('ecdict')
    if not db:
        key = {'error': 'Could not found "ecdict.db"'}
    else:
        sql = 'SELECT * FROM ecdict where WORD = ?'
        cursor = db.execute(sql, (word, ))
        key = dict(next(cursor))
    word_meta = []
    if key.get('oxford'):
        word_meta.append('<a href="https://www.oxfordlearnersdictionaries.com/us/wordlist/english/oxford3000/" target="_blank">'
                         '<img src="%s" style="height:16px" title="Oxford 3000"/>'
                         '</a>' % url_for('.static', filename='Ox3000_Rect1_mod_web.png')
                         )
    if key.get('collins'):
        # star = '⭐'
        star = '<i class="text-warning fas fa-star"></i>'
        n = int(key['collins'])
        word_meta.append('<span title="Collins %s star">%s</span>' % (n, star * n))
    if key.get('tag'):
        tags = ['<span class="badge badge-pill badge-primary">%s</span>' % TAGs.get(t, t) for t in key['tag'].split(' ')]
        word_meta.extend(tags)
    if key.get('bnc'):
        word_meta.append('<a href="http://www.natcorp.ox.ac.uk/" target="_blank">'
                         '<span class="badge badge-pill badge-info" title="BNC: %s">BNC: %s</span>'
                         '</a>' % (key['bnc'], key['bnc']))
    if key.get('frq'):
        word_meta.append('<a href="https://www.english-corpora.org/coca/" target="_blank">'
                         '<span class="badge badge-pill badge-info" title="COCA: %s">COCA: %s</span>'
                         '</a>' % (key['frq'], key['frq']))
    if key.get('error'):
        word_meta.append('<span class="badge badge-pill badge-danger">%s</span>' % (key['error']))
    return ' '.join(word_meta)


def init_mdict(mdict_dir):
    mdicts = {}
    db_names = {}
    for root, dirs, files in os.walk(mdict_dir, followlinks=True):
        for fname in files:
            if fname.endswith('.db') \
                    and not fname.endswith('.mdx.db') \
                    and not fname.endswith('.mdd.db'):
                db_file = os.path.join(root, fname)
                d = DBDict(db_file)
                if not d.is_ok():
                    continue
                # mdict db
                name = os.path.splitext(fname)[0]
                print('Initialize DICT DB "%s"...' % name)
                print('\tfind %s:mdx' % fname)
                if d.is_mdd():
                    print('\tfind %s:mdd' % fname)
                logo = 'logo.ico'
                for ext in ['ico', '.jpg', '.png']:
                    if os.path.exists(os.path.join(root, name + ext)):
                        logo = name + ext
                        break
                dict_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, db_file)).upper()
                print('\tuuid: %s' % dict_uuid)
                db_names[dict_uuid] = db_file
                mdicts[dict_uuid] = {
                    'title': d.title(),
                    'uuid': dict_uuid,
                    'logo': logo,
                    'about': d.about(),
                    'root_path': root,
                    'query': d,
                    'cache': {},
                    'type': 'mdict_db',
                    'error': '',
                }
            elif fname.endswith('.mdx'):
                name = os.path.splitext(fname)[0]
                logo = 'logo.ico'
                for ext in ['ico', '.jpg', '.png']:
                    if os.path.exists(os.path.join(root, name + ext)):
                        logo = name + ext
                        break
                mdx_file = os.path.join(root, fname)
                dict_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, mdx_file)).upper()
                print('Initialize MDICT "%s" {%s}...' % (name, dict_uuid))

                idx = IndexBuilder2(mdx_file)
                if not idx._title or idx._title == 'Title (No HTML code allowed)':
                    title = name
                else:
                    title = idx._title
                    title = regex_tag.sub(' ', title)

                abouts = []
                abouts.append('<ul>')
                abouts.append('<li>%s</li>' % os.path.basename(idx._mdx_file))
                print('\t+ %s' % os.path.basename(idx._mdx_file))
                for mdd in idx._mdd_files:
                    abouts.append('<li>%s</li>' % os.path.basename(mdd))
                    print('\t+ %s' % os.path.basename(mdd))
                abouts.append('</ul><hr />')
                if idx._description == '<font size=5 color=red>Paste the description of this product in HTML source code format here</font>':
                    text = ''
                else:
                    text = fix_html(idx._description)
                about_html = os.path.join(root, 'about_%s.html' % name)
                if not os.path.exists(about_html):
                    with open(about_html, 'wt') as f:
                        f.write(text)
                if False:
                    text = regex_style.sub('', text)
                    text = regex_ln.sub('\n', text)
                    text = regex_tag.sub(' ', text)
                    text = [t for t in [t.strip() for t in text.split('\n')] if t]
                    abouts.append('<p>' + '<br />\n'.join(text) + '</p>')
                else:
                    abouts.append(text)
                about = '\n'.join(abouts)
                mdicts[dict_uuid] = {
                    'title': title,
                    'uuid': dict_uuid,
                    'logo': logo,
                    'about': about,
                    'root_path': root,
                    'query': idx,
                    'cache': {},
                    'type': 'mdict',
                    'error': '',
                }
    # ecdict
    title = 'ECDICT'
    dict_uuid = 'ecdict'
    mdicts['ecdict'] = {
        'title': title,
        'uuid': dict_uuid,
        'logo': 'logo.ico',
        'about': 'ECDICT - Free English to Chinese Dictionary Database<br />https://github.com/skywind3000/ECDICT',
        'root_path': '',
        'query': ecdict_query_word,
        'cache': {},
        'type': 'app',
        'error': '',
    }
    db_names[dict_uuid] = os.path.join(mdict_dir, 'ecdict.db')
    if not os.path.exists(db_names[dict_uuid]):
        print('Do not find ECDICT "%s"' % db_names[dict_uuid])
    else:
        print('Add "%s"...' % title)
    # for google translate online
    title = 'Google 翻译'
    dict_uuid = str(uuid.uuid3(uuid.NAMESPACE_URL, title)).upper()
    mdicts[dict_uuid] = {
        'title': title,
        'uuid': dict_uuid,
        'logo': 'google_translate.ico',
        'about': 'google-translate-for-goldendict<br />https://github.com/xinebf/google-translate-for-goldendict',
        'root_path': 'translate.google.cn',
        'query': google_translate,
        'cache': {},
        'type': 'app',
        'error': '',
    }
    db_names[dict_uuid] = None
    print('Add "%s"...' % title)
    print('--- MDict is Ready ---')
    return mdicts, db_names


def google_translate(word, item=None):
    """
    python -m googletranslate.googletranslate -s "translate.google.cn" -r plain zh-CN "word"
    """
    class Args:
        target: str = 'zh-CN'
        query: str = ''
        host: str = 'translate.google.com'
        proxy: str = ''
        alternative: str = 'en'
        type: str = 'plain'
        synonyms: bool = False
        definitions: bool = True
        examples: bool = False
        tkk: str = ''
    Args.host = item['root_path'] if item else 'translate.google.cn'
    Args.query = word
    trans = []
    trans_group = []
    result = gtranslate(Args)
    for line in result.split('\n'):
        if not line:
            continue
        elif line == '=========':
            trans_group.append('<div>%s</div>' % '<br />'.join(trans))
            trans = []
            continue
        elif line.startswith('^_^:'):
            line = '<span>%s</span>' % line
        elif line.startswith('0_0:'):
            line = '<span>%s</span>' % line
        else:
            line = '%s' % line
        trans.append(line)
    if trans:
        trans_group.append('<div>%s</div>' % '<br />'.join(trans))
    return trans_group


regex_body = re.compile(r'(#\S+ .mdict)\s+?(body)\s*?({)')
regex_fontface = re.compile(r'(@font-face *{.+?})', re.DOTALL)


def fix_css(prefix_id, css_data):
    # remove fontface with scss bug
    fontface = []
    for m in regex_fontface.findall(css_data):
        fontface.append(m)
    data = regex_fontface.sub('', css_data)

    # with compressed
    css = Scss(scss_opts={'style': True})
    # check origin data
    css.compile(data)

    data = css.compile('#%s .mdict { %s }' % (prefix_id, data))

    data = regex_body.sub(r'\2 \1 \3', data)
    # add fontface
    data = '\n'.join(fontface) + data
    return data


regex_opened_tag = re.compile(r'<([a-z]+)(?: .*?)?>', re.DOTALL | re.IGNORECASE)
regex_closed_tag = re.compile(r'</([a-z]+)>', re.IGNORECASE)


def fix_html(html_data):
    opened_tags = regex_opened_tag.findall(html_data)
    closed_tags = regex_closed_tag.findall(html_data)
    opened_tags = [tag.lower() for tag in opened_tags]
    closed_tags = [tag.lower() for tag in closed_tags]
    # remove single tag
    for tag in ['img', 'link', 'input', 'br', 'hr', 'p', 'meta']:
        while tag in opened_tags:
            opened_tags.remove(tag)
        while tag in closed_tags:
            closed_tags.remove(tag)
    if len(opened_tags) == len(closed_tags):
        return html_data
    for tag in opened_tags[::-1]:
        if tag in closed_tags:
            closed_tags.remove(tag)
        else:
            html_data += '</%s>' % tag
    for tag in closed_tags:
        html_data = '<%s>' % tag + html_data
    return html_data