"""
Загрузка и работа с WCA rankings (v2).
Источник: https://www.worldcubeassociation.org/export/results
API: https://www.worldcubeassociation.org/api/v0/export/public
"""
import io
import zipfile
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st


WCA_API_URL = 'https://www.worldcubeassociation.org/api/v0/export/public'
CACHE_DIR = Path('.wca_cache')
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL_DAYS = 7

# Имена файлов в архиве v2 — snake_case
FILES = {
    'single': 'WCA_export_ranks_single.tsv',
    'average': 'WCA_export_ranks_average.tsv',
    'persons': 'WCA_export_persons.tsv',
}

# Маппинг наших ключей (Puzzle|Category) к WCA event_id
EVENT_MAPPING = {
    '222|Normal': '222',
    '333|Normal': '333',
    '333|oh': '333oh',
    '333|bld': '333bf',
    '333|fm': '333fm',
    '333|ft': '333ft',
    '444|Normal': '444',
    '444|bld': '444bf',
    '555|Normal': '555',
    '555|bld': '555bf',
    '666|Normal': '666',
    '777|Normal': '777',
    'pyra|Normal': 'pyram',
    'mega|Normal': 'minx',
    'sq1|Normal': 'sq1',
    'clock|Normal': 'clock',
    'skewb|Normal': 'skewb',
    'fto|Normal': 'fto',
}

EVENT_DISPLAY = {
    '222': '2x2x2', '333': '3x3x3', '333oh': '3x3 OH',
    '333bf': '3x3 BLD', '333fm': '3x3 FMC', '333ft': '3x3 With Feet',
    '444': '4x4x4', '444bf': '4x4 BLD',
    '555': '5x5x5', '555bf': '5x5 BLD',
    '666': '6x6x6', '777': '7x7x7',
    'pyram': 'Pyraminx', 'minx': 'Megaminx',
    'sq1': 'Square-1', 'clock': 'Clock', 'skewb': 'Skewb', 'fto': 'FTO',
}


def _cache_path(name: str) -> Path:
    return CACHE_DIR / name


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(days=CACHE_TTL_DAYS)


def _get_export_info() -> dict:
    """
    Получает актуальный URL через API:
    {"export_date": "...", "sql_url": "...", "tsv_url": "..."}
    """
    response = requests.get(WCA_API_URL, timeout=30)
    response.raise_for_status()
    return response.json()


@st.cache_data(show_spinner=False)
def download_wca_data(force: bool = False) -> dict:
    """
    Скачивает (при необходимости) и читает нужные TSV из WCA export v2.
    Возвращает dict с DataFrames.
    """
    all_cached = all(_is_cache_fresh(_cache_path(f)) for f in FILES.values())

    if not all_cached or force:
        with st.spinner('🌐 Получаю актуальный URL от WCA API...'):
            info = _get_export_info()
            tsv_url = info['tsv_url']
            export_date = info.get('export_date', 'unknown')

        with st.spinner(f'📥 Скачиваю WCA export (v2, ~340 МБ). Дата: {export_date}'):
            # Стримим, чтобы не держать всё в памяти одновременно
            response = requests.get(tsv_url, timeout=600, stream=True)
            response.raise_for_status()

            # Собираем zip в память постепенно
            buffer = io.BytesIO()
            total = int(response.headers.get('Content-Length', 0))
            progress = st.progress(0.0)
            downloaded = 0
            chunk_size = 1024 * 256  # 256 КБ
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    buffer.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        progress.progress(min(downloaded / total, 1.0))
            progress.empty()

            buffer.seek(0)
            with zipfile.ZipFile(buffer) as z:
                # Найдём нужные файлы (они могут быть во вложенной папке)
                archive_names = z.namelist()
                for key, fname in FILES.items():
                    # Ищем имя в архиве, которое заканчивается на нужное
                    matches = [n for n in archive_names if n.endswith(fname)]
                    if not matches:
                        raise FileNotFoundError(
                            f'Файл {fname} не найден в архиве. '
                            f'Доступные: {archive_names[:20]}'
                        )
                    with z.open(matches[0]) as src:
                        data = src.read()
                    _cache_path(fname).write_bytes(data)

    # Читаем локальные файлы
    result = {}
    for key, fname in FILES.items():
        df = pd.read_csv(
            _cache_path(fname), sep='\t', low_memory=False,
            na_values=[''], keep_default_na=True,
        )
        result[key] = df

    return result


@st.cache_data(show_spinner=False)
def get_ranks_for_event(event_id: str, rank_type: str = 'average') -> pd.DataFrame:
    """
    Возвращает ранги для заданного ивента.
    rank_type: 'single' или 'average'.

    Колонки в v2: person_id, event_id, best, world_rank, continent_rank, country_rank.
    `best` — в сотых секунды (centiseconds). Для FMC это количество ходов.
    """
    data = download_wca_data()
    df = data[rank_type]
    df_event = df[df['event_id'] == event_id].copy()

    # Для FMC (333fm) значения — число ходов, а не время
    # Averages для FMC хранятся как 100×moves (по README). Для singles — просто ходы.
    if event_id == '333fm':
        if rank_type == 'average':
            df_event['time_seconds'] = df_event['best'] / 100.0  # ходы (как число)
        else:
            df_event['time_seconds'] = df_event['best'].astype(float)
    else:
        df_event['time_seconds'] = df_event['best'] / 100.0

    # Подтягиваем страну и имя
    persons = data['persons'][['wca_id', 'name', 'country_id']].rename(
        columns={'wca_id': 'person_id'}
    )
    # В persons может быть несколько записей на одного человека (sub_id при смене страны)
    # Берём уникальные по wca_id
    persons = persons.drop_duplicates(subset=['person_id'], keep='last')

    df_event = df_event.merge(persons, on='person_id', how='left')

    return df_event[['person_id', 'name', 'country_id', 'time_seconds',
                      'world_rank', 'continent_rank', 'country_rank']]


def find_rank_for_time(ranks_df: pd.DataFrame, my_time: float,
                        country: str | None = None) -> dict:
    if pd.isna(my_time) or ranks_df.empty:
        return {'world_rank': None, 'country_rank': None,
                'total_world': len(ranks_df), 'total_country': 0,
                'percentile_world': None, 'percentile_country': None}

    faster_world = (ranks_df['time_seconds'] < my_time).sum()
    world_rank = faster_world + 1
    total_world = len(ranks_df)
    percentile_world = (1 - faster_world / total_world) * 100 if total_world else None

    result = {
        'world_rank': int(world_rank),
        'total_world': int(total_world),
        'percentile_world': percentile_world,
    }

    if country:
        country_df = ranks_df[ranks_df['country_id'] == country]
        if len(country_df):
            faster_country = (country_df['time_seconds'] < my_time).sum()
            result['country_rank'] = int(faster_country + 1)
            result['total_country'] = len(country_df)
            result['percentile_country'] = (1 - faster_country / len(country_df)) * 100
        else:
            result['country_rank'] = None
            result['total_country'] = 0
            result['percentile_country'] = None
    else:
        result['country_rank'] = None
        result['total_country'] = 0
        result['percentile_country'] = None

    return result


def get_top_times(ranks_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return ranks_df.nsmallest(n, 'time_seconds')[
        ['world_rank', 'name', 'country_id', 'time_seconds']
    ].reset_index(drop=True)


def get_countries_list() -> list[str]:
    data = download_wca_data()
    countries = sorted(data['persons']['country_id'].dropna().unique())
    return countries


def kinchrank_score(my_time: float, wr_time: float) -> float:
    if pd.isna(my_time) or my_time == 0 or pd.isna(wr_time):
        return 0.0
    return min(100.0, (wr_time / my_time) * 100)