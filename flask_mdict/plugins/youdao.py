# https://github.com/UlionTse/translators/tree/master
import translators as ts


def translate(content, item):
    try:
        text = ts.translate_text(
            content,
            translator='youdao',
            from_language=item.get('from_lan', 'auto'),
            to_language=item.get('to_lan', 'zh'),
        )
        return [text]
    except Exception as err:
        return ['Translators error: %s' % (err)]


def init():
    title = '有道智云'
    dict_uuid = 'youdao_translate'
    about = 'https://ai.youdao.com/product-fanyi-text.s'
    enable = True
    config = {
        'title': title,
        'uuid': dict_uuid,
        'logo': 'youdao.png',
        'about': about,
        'root_path': '',
        'query': translate,
        'cache': {},
        'type': 'app',
        'error': '',
        'enable': enable,
    }
    return config


if __name__ == '__main__':
    content = "How do I access a previous row when iterating through a pandas dataframe? ... How would I access the previous row? I've tried row.shift(1)"
    print(translate(content))
