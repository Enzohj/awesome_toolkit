import re


def normalize_text(text: object) -> str:
    """将任意连续空白压缩为单个空格，并移除首尾空白。"""
    if not isinstance(text, str):
        return ''
    normalized = re.sub(r'\s+', ' ', text).strip()
    return normalized


# 保留旧 API，两个名称始终共享同一实现。
normalize = normalize_text


def extract_hashtag(text, remove_duplicates=True):
    pattern = r'#([a-zA-Z\u4e00-\u9fff0-9][\w\u4e00-\u9fff\+\-]*)'
    tags = re.findall(pattern, text)
    if remove_duplicates:
        tags = list(dict.fromkeys(tags))
    return tags

def get_pure_text_hashtag(text):
    text = normalize(text)
    pattern = r'#([a-zA-Z\u4e00-\u9fff0-9][\w\u4e00-\u9fff\+\-]*)'
    tags = re.findall(pattern, text)
    pure_text = re.sub(pattern, '', text)
    pure_text = normalize(pure_text)
    if len(tags) == 0:
        return pure_text, ''
    return pure_text, '#'+' #'.join(tags)

def remove_emoji_and_hashtag(text):
    # Remove hashtags (including the # symbol)
    text = re.sub(r'#([a-zA-Z\u4e00-\u9fff0-9][\w\u4e00-\u9fff\+\-]*)', '', text)
    
    # Remove emojis using Unicode ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和图形
        "\U0001F680-\U0001F6FF"  # 交通和地图
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U0001F1E6-\U0001F1FF"  # 国旗区域指示符
        "\U000E0020-\U000E007F"  # emoji tag 序列
        "\u2600-\u26FF"          # 杂项符号
        "\u2700-\u27BF"          # 装饰符号
        "\u200D"                 # ZWJ 连字符
        "\u20E3"                 # 键帽组合符
        "\uFE0E-\uFE0F"          # 文本 / emoji 变体选择符
        "]+",
        flags=re.UNICODE
    )
    
    text = emoji_pattern.sub('', text)
    return text

if __name__ == '__main__':
    text = 'Hello, \n #World! 你好，      #世界！ 😊\t 123#2026'
    # print(text)
    # print(normalize(text))
    # print(extract_hashtag(text))
    # print(remove_emoji_and_hashtag(text))
    # print(normalize(remove_emoji_and_hashtag(text)))
    print(get_pure_text_hashtag(text))
