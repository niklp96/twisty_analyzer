import pandas as pd
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
import streamlit as st


def _wca_average_windows(windows: np.ndarray) -> np.ndarray:
    """
    Векторизованное вычисление WCA-average для множества окон.
    windows: 2D array (n_windows, window_size), может содержать NaN (DNF).
    Возвращает 1D array длины n_windows.
    """
    # DNF считаем как +inf для сортировки
    w = np.where(np.isnan(windows), np.inf, windows)
    dnf_count = np.isnan(windows).sum(axis=1)

    # Сортируем каждое окно
    w_sorted = np.sort(w, axis=1)
    # Удаляем лучшее и худшее
    trimmed = w_sorted[:, 1:-1]

    # Если среди trimmed есть inf (2+ DNF), то avg = NaN
    has_inf = np.isinf(trimmed).any(axis=1)
    avg = trimmed.mean(axis=1)
    avg[has_inf] = np.nan
    avg[dnf_count > 1] = np.nan

    return avg.astype('float32')


def _mean_of_n_windows(windows: np.ndarray) -> np.ndarray:
    """Простое среднее; любой NaN в окне = NaN."""
    any_nan = np.isnan(windows).any(axis=1)
    avg = windows.mean(axis=1)
    avg[any_nan] = np.nan
    return avg.astype('float32')


def rolling_average(series: pd.Series, n: int, wca_style: bool = True) -> pd.Series:
    """
    Быстрое скользящее среднее через sliding_window_view.
    На 100k элементов работает за ~10-50 мс вместо ~10 секунд.
    """
    values = series.values.astype('float32')
    length = len(values)

    if length < n:
        return pd.Series(np.full(length, np.nan, dtype='float32'), index=series.index)

    windows = sliding_window_view(values, window_shape=n)
    if wca_style and n >= 5:
        computed = _wca_average_windows(windows)
    else:
        computed = _mean_of_n_windows(windows)

    result = np.full(length, np.nan, dtype='float32')
    result[n - 1:] = computed
    return pd.Series(result, index=series.index)


def best_ao(series: pd.Series, n: int) -> float:
    ao = rolling_average(series, n)
    return float(ao.min()) if ao.notna().any() else np.nan


def current_ao(series: pd.Series, n: int) -> float:
    if len(series) < n:
        return np.nan
    # Считаем только последнее окно — без rolling_average
    window = series.values[-n:].astype('float32').reshape(1, -1)
    if n >= 5:
        return float(_wca_average_windows(window)[0])
    return float(_mean_of_n_windows(window)[0])


@st.cache_data(show_spinner=False, max_entries=32)
def compute_event_summary(df_hash: str, df_event_bytes: bytes) -> dict:
    """Кэшируемая сводка. Принимает pickled DataFrame для хешируемости."""
    import pickle
    df_event = pickle.loads(df_event_bytes)
    return _compute_event_summary_impl(df_event)


def _compute_event_summary_impl(df_event: pd.DataFrame) -> dict:
    times = df_event['EffectiveTime']
    total = len(df_event)
    dnf = int(df_event['IsDNF'].sum())
    plus2 = int((df_event['Penalty'] == 1).sum())
    valid = times.dropna()

    summary = {
        'total_solves': total,
        'dnf_count': dnf,
        'dnf_rate': dnf / total * 100 if total else 0,
        'plus2_count': plus2,
        'plus2_rate': plus2 / total * 100 if total else 0,
        'best_single': float(valid.min()) if len(valid) else np.nan,
        'worst_single': float(valid.max()) if len(valid) else np.nan,
        'mean': float(valid.mean()) if len(valid) else np.nan,
        'median': float(valid.median()) if len(valid) else np.nan,
        'std': float(valid.std()) if len(valid) >= 2 else np.nan,
        'total_time_hours': float(valid.sum()) / 3600 if len(valid) else 0,
        'first_solve': df_event['DateTime'].min(),
        'last_solve': df_event['DateTime'].max(),
    }

    for n in [3, 5, 12, 50, 100, 1000]:
        if total >= n:
            summary[f'best_ao{n}'] = best_ao(times, n)
            summary[f'current_ao{n}'] = current_ao(times, n)
        else:
            summary[f'best_ao{n}'] = np.nan
            summary[f'current_ao{n}'] = np.nan

    if len(valid):
        for threshold in [5, 10, 15, 20, 30, 60]:
            summary[f'sub_{threshold}'] = int((valid < threshold).sum())

    return summary


def compute_event_summary_fast(df_event: pd.DataFrame) -> dict:
    """Обёртка без кэша — используется напрямую."""
    return _compute_event_summary_impl(df_event)


def detect_pbs(df_event: pd.DataFrame) -> pd.DataFrame:
    """Векторизованный поиск PB через накопительный минимум."""
    result = df_event.copy()
    times = df_event['EffectiveTime'].values.astype('float32')

    # np.minimum.accumulate не обрабатывает NaN, заполним inf
    filled = np.where(np.isnan(times), np.inf, times)
    running_min = np.minimum.accumulate(filled)
    # PB = время меньше всех предыдущих минимумов
    prev_min = np.concatenate([[np.inf], running_min[:-1]])
    result['PB_Single'] = (filled < prev_min) & ~np.isnan(times)

    for n in [5, 12, 100]:
        if len(df_event) >= n:
            ao = rolling_average(df_event['EffectiveTime'], n).values
            filled_ao = np.where(np.isnan(ao), np.inf, ao)
            run_min = np.minimum.accumulate(filled_ao)
            prev = np.concatenate([[np.inf], run_min[:-1]])
            result[f'PB_ao{n}'] = (filled_ao < prev) & ~np.isnan(ao)
        else:
            result[f'PB_ao{n}'] = False

    return result


def session_stats(df_event: pd.DataFrame) -> pd.DataFrame:
    g = df_event.groupby('SessionId', sort=False)
    sessions = pd.DataFrame({
        'start': g['DateTime'].min(),
        'end': g['DateTime'].max(),
        'count': g.size(),
        'mean': g['EffectiveTime'].mean(),
        'best': g['EffectiveTime'].min(),
        'worst': g['EffectiveTime'].max(),
        'std': g['EffectiveTime'].std(),
    }).reset_index()
    sessions['duration_min'] = (sessions['end'] - sessions['start']).dt.total_seconds() / 60
    return sessions


def streak_stats(df_event: pd.DataFrame, threshold: float) -> dict:
    """Быстрый стрик через NumPy."""
    times = df_event['EffectiveTime'].values
    is_sub = (~np.isnan(times)) & (times < threshold)
    if not is_sub.any():
        return {'max_streak': 0, 'current_streak': 0, 'threshold': threshold}

    # Считаем длины подряд идущих True
    # Стандартный трюк: накопительная сумма, сброс на False
    reset = np.cumsum(~is_sub)
    # Сгруппировать по reset и посчитать True в группе
    groups = pd.Series(is_sub).groupby(reset).sum()
    max_streak = int(groups.max())

    # Current streak — с конца
    current = 0
    for v in is_sub[::-1]:
        if v:
            current += 1
        else:
            break

    return {'max_streak': max_streak, 'current_streak': current, 'threshold': threshold}


def lucky_solves(df_event: pd.DataFrame, sigma: float = 2.0) -> pd.DataFrame:
    valid = df_event[df_event['EffectiveTime'].notna()]
    if len(valid) < 10:
        return pd.DataFrame()
    mean = valid['EffectiveTime'].mean()
    std = valid['EffectiveTime'].std()
    threshold = mean - sigma * std
    return valid[valid['EffectiveTime'] < threshold]