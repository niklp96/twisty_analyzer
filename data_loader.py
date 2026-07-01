import pandas as pd
import numpy as np
import hashlib
from io import StringIO
import streamlit as st


PUZZLE_NAMES = {
    '222': '2x2x2', '333': '3x3x3', '444': '4x4x4',
    '555': '5x5x5', '666': '6x6x6', '777': '7x7x7',
    'pyra': 'Pyraminx', 'mega': 'Megaminx',
    'sq1': 'Square-1', 'clock': 'Clock', 'skewb': 'Skewb',
    'fto': 'FTO (Face-Turning Octahedron)',
}


def _content_hash(content: str) -> str:
    """Быстрый хэш для ключа кэша."""
    return hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()


def _preprocess_multiline(body: str) -> str:
    """
    Склеивает многострочные поля в кавычках (скрамблы мегаминкса) в одну строку,
    заменяя внутренние переводы на пробел. Это быстрее, чем csv.reader.
    """
    out = []
    in_quotes = False
    for ch in body:
        if ch == '"':
            in_quotes = not in_quotes
            out.append(ch)
        elif ch == '\n' and in_quotes:
            out.append(' ')  # заменяем перевод строки на пробел внутри поля
        else:
            out.append(ch)
    return ''.join(out)

def _parse_cstimer_time(time_str: str) -> tuple[float, int]:
    """
    Парсит время из cstimer формата.
    Возвращает (seconds, penalty). penalty: 0=OK, 1=+2, 2=DNF.
    Форматы: '4:24.28', '59.71', 'DNF(1:23.45)', '1:23.45+', 'DNF'
    """
    s = str(time_str).strip()
    penalty = 0

    if not s or s.upper() == 'DNF':
        return np.nan, 2

    # DNF в форме DNF(время)
    if s.upper().startswith('DNF'):
        penalty = 2
        inner = s[3:].strip('()').strip()
        s = inner if inner else ''
        if not s:
            return np.nan, 2

    # +2 в форме '1:23.45+' или '83.45+'
    if s.endswith('+'):
        penalty = 1 if penalty == 0 else penalty
        s = s[:-1].strip()

    # Разбор m:ss.xx или ss.xx
    try:
        if ':' in s:
            parts = s.split(':')
            if len(parts) == 2:
                m, sec = parts
                total = int(m) * 60 + float(sec)
            elif len(parts) == 3:  # h:mm:ss
                h, m, sec = parts
                total = int(h) * 3600 + int(m) * 60 + float(sec)
            else:
                return np.nan, penalty
        else:
            total = float(s)
    except (ValueError, TypeError):
        return np.nan, penalty

    return total, penalty


def _is_cstimer_format(header_line: str) -> bool:
    """Определяет формат cstimer session export по заголовку."""
    h = header_line.lower()
    # cstimer export: No.;Time;Comment;Scramble;Date;...
    return h.startswith('no.') and ';' in header_line and 'time' in h


@st.cache_data(show_spinner='Парсим cstimer файл...', max_entries=3)
def load_cstimer_data(file_content: str, event_name: str = '3x3x3',
                      _hash: str = '') -> pd.DataFrame:
    """
    Парсинг cstimer session export.
    event_name задаётся пользователем, т.к. cstimer не хранит тип головоломки.
    """
    first_newline = file_content.index('\n')
    header_line = file_content[:first_newline].strip()
    body = file_content[first_newline + 1:]

    body_clean = _preprocess_multiline(body)

    headers = [h.strip() for h in header_line.split(';')]

    df = pd.read_csv(
        StringIO(body_clean),
        sep=';',
        quotechar='"',
        names=headers,
        dtype=str,
        engine='c',
        on_bad_lines='skip',
        na_filter=False,
        header=0,
    )

    # Парсим время + пенальти
    parsed = df['Time'].apply(_parse_cstimer_time)
    df['Time'] = parsed.apply(lambda x: x[0]).astype('float32')
    df['Penalty'] = parsed.apply(lambda x: x[1]).astype('int8')

    # Дата
    df['DateTime'] = pd.to_datetime(df['Date'], errors='coerce')
    # Если дат нет — синтезируем последовательные (по индексу)
    if df['DateTime'].isna().all():
        df['DateTime'] = pd.date_range(
            '2020-01-01', periods=len(df), freq='min'
        )
    else:
        # заполняем пропущенные даты вперёд
        df['DateTime'] = df['DateTime'].ffill().bfill()

    df = df.dropna(subset=['Time']).reset_index(drop=True)

    # Скрамбл / коммент
    if 'Scramble' not in df.columns:
        df['Scramble'] = ''
    if 'Comment' not in df.columns:
        df['Comment'] = ''
    df['Scramble'] = df['Scramble'].fillna('')

    # Производные колонки
    df['Date'] = df['DateTime'].dt.date
    df['Hour'] = df['DateTime'].dt.hour.astype('int8')
    df['Weekday'] = df['DateTime'].dt.day_name()
    df['Month'] = df['DateTime'].dt.to_period('M').astype(str)
    df['Year'] = df['DateTime'].dt.year.astype('int16')

    # DNF / +2
    df['IsDNF'] = df['Penalty'] == 2
    eff = df['Time'].astype('float32').copy()
    eff[df['IsDNF']] = np.nan
    eff[df['Penalty'] == 1] += 2.0
    df['EffectiveTime'] = eff

    # Event — задаётся пользователем (cstimer не хранит тип)
    df['Event'] = event_name
    # Обратный маппинг display name → код
    reverse = {v: k for k, v in PUZZLE_NAMES.items()}
    puzzle_code = reverse.get(event_name, event_name)
    df['Puzzle'] = puzzle_code
    df['Category'] = 'Normal'
    df['EventKey'] = f'{puzzle_code}|Normal'

    # Сортировка
    df = df.sort_values('DateTime', kind='mergesort').reset_index(drop=True)

    # Сессии
    dt_diff = df['DateTime'].diff().dt.total_seconds()
    df['NewSession'] = dt_diff.isna() | (dt_diff > 1800)
    df['SessionId'] = df['NewSession'].cumsum().astype('int32')
    df['SessionPosition'] = (
        df.groupby('SessionId', sort=False).cumcount() + 1
    ).astype('int32')
    df.drop(columns=['NewSession'], inplace=True)

    return df


@st.cache_data(show_spinner='Парсим файл...', max_entries=3)
def load_data(file_content: str, _hash: str = '') -> pd.DataFrame:
    """
    Быстрый парсинг txt со сборками.
    _hash нужен только для инвалидации кэша; сам параметр не используется.
    """
    first_newline = file_content.index('\n')
    header_line = file_content[:first_newline].strip()
    body = file_content[first_newline + 1:]

    headers = [h.strip() for h in header_line.split(',')]

    # Склеиваем многострочные поля — гораздо быстрее чем csv.reader
    body_clean = _preprocess_multiline(body)

    # Используем pandas напрямую — он на C, быстрее чем csv модуль
    df = pd.read_csv(
        StringIO(body_clean),
        sep=';',
        quotechar='"',
        names=headers,
        dtype=str,
        engine='c',
        on_bad_lines='skip',
        na_filter=False,
    )

    # Типизация (векторизованно)
    df['Time(millis)'] = pd.to_numeric(df['Time(millis)'], errors='coerce')
    df['Date(millis)'] = pd.to_numeric(df['Date(millis)'], errors='coerce')
    df['Penalty'] = pd.to_numeric(df['Penalty'], errors='coerce').fillna(0).astype('int8')

    df = df.dropna(subset=['Time(millis)', 'Date(millis)']).reset_index(drop=True)

    # Производные колонки — всё векторизованно
    df['Time'] = (df['Time(millis)'] / 1000.0).astype('float32')
    df['DateTime'] = pd.to_datetime(df['Date(millis)'], unit='ms')
    df['Date'] = df['DateTime'].dt.date
    df['Hour'] = df['DateTime'].dt.hour.astype('int8')
    df['Weekday'] = df['DateTime'].dt.day_name()
    df['Month'] = df['DateTime'].dt.to_period('M').astype(str)
    df['Year'] = df['DateTime'].dt.year.astype('int16')

    # DNF / +2 — векторизованно
    df['IsDNF'] = df['Penalty'] == 2
    eff = df['Time'].astype('float32').copy()
    eff[df['IsDNF']] = np.nan
    eff[df['Penalty'] == 1] += 2.0
    df['EffectiveTime'] = eff

    # Event name — через map вместо apply (в разы быстрее)
    puzzle_map = df['Puzzle'].map(PUZZLE_NAMES).fillna(df['Puzzle'])
    category_clean = df['Category'].fillna('').astype(str)
    is_normal = category_clean.str.lower().isin(['normal', ''])
    df['Event'] = np.where(
        is_normal,
        puzzle_map,
        puzzle_map + ' (' + category_clean + ')'
    )
    df['EventKey'] = df['Puzzle'].astype(str) + '|' + category_clean

    # Сортировка
    df = df.sort_values('DateTime', kind='mergesort').reset_index(drop=True)

    # Сессии — через группировку
    dt_diff = df.groupby('EventKey', sort=False)['DateTime'].diff().dt.total_seconds()
    df['NewSession'] = dt_diff.isna() | (dt_diff > 1800)
    df['SessionId'] = df.groupby('EventKey', sort=False)['NewSession'].cumsum().astype('int32')
    df['SessionPosition'] = (
        df.groupby(['EventKey', 'SessionId'], sort=False).cumcount() + 1
    ).astype('int32')

    # Чистим тяжёлые колонки, если не нужны
    df.drop(columns=['NewSession'], inplace=True)

    return df


def format_time(seconds: float) -> str:
    if pd.isna(seconds):
        return 'DNF'
    if seconds >= 60:
        m = int(seconds // 60)
        s = seconds - m * 60
        return f'{m}:{s:05.2f}'
    return f'{seconds:.2f}'