"""
Rubik's Cube Solves Analytics — Streamlit app.
Запуск: streamlit run app.py
"""
import pickle

import numpy as np
import pandas as pd
import streamlit as st

import charts
from data_loader import load_data, format_time
from stats import (
    compute_event_summary_fast as compute_event_summary,
    detect_pbs,
    session_stats,
    streak_stats,
    lucky_solves,
    rolling_average,
    best_ao,
)
from wca_rankings import (
    get_ranks_for_event,
    find_rank_for_time,
    get_top_times,
    get_countries_list,
    kinchrank_score,
    download_wca_data,
    EVENT_MAPPING,
    EVENT_DISPLAY,
)


# ═══════════════════════════════════════════════════════════
# Настройки страницы
# ═══════════════════════════════════════════════════════════
st.set_page_config(
    page_title='Rubik Solves Analytics',
    page_icon='🧊',
    layout='wide',
)

st.title('🧊 Rubik\'s Cube Solves Analytics')
st.caption('Загрузи txt файл из своего таймера и получи полную статистику')


# ═══════════════════════════════════════════════════════════
# Кэшируемые helper-функции
# ═══════════════════════════════════════════════════════════
@st.cache_data(show_spinner='Считаю сводку по ивентам...', max_entries=8)
def build_overview_table(df_hash: str, df_serialized: bytes) -> pd.DataFrame:
    """Строит сводную таблицу по всем ивентам (кэшируется)."""
    df_f = pickle.loads(df_serialized)
    rows = []
    for event in sorted(df_f['Event'].unique()):
        df_ev = df_f[df_f['Event'] == event]
        s = compute_event_summary(df_ev)
        rows.append({
            'Event': event,
            'Solves': s['total_solves'],
            'Best': format_time(s['best_single']),
            'Mean': format_time(s['mean']),
            'Median': format_time(s['median']),
            'Best ao5': format_time(s['best_ao5']),
            'Best ao12': format_time(s['best_ao12']),
            'Best ao100': format_time(s['best_ao100']),
            'Current ao100': format_time(s['current_ao100']),
            'Total time (h)': f'{s["total_time_hours"]:.1f}',
        })
    return pd.DataFrame(rows)


def df_cache_key(df: pd.DataFrame) -> str:
    """Быстрый ключ для кэша по содержимому df."""
    return f'{len(df)}_{df["DateTime"].min()}_{df["DateTime"].max()}'


# ═══════════════════════════════════════════════════════════
# Загрузка файла
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.header('📁 Данные')
    uploaded = st.file_uploader('Загрузи txt файл', type=['txt', 'csv'])
    st.markdown('---')

if uploaded is None:
    st.info('👈 Загрузи файл в боковой панели, чтобы начать')
    st.markdown(
        """
        ### Что умеет приложение
        - 📊 Общая статистика по всем ивентам
        - 🎯 Детальный анализ каждого ивента (PB, progression, гистограммы)
        - 📅 Heatmap активности + распределение по часам/дням недели
        - ⏱️ Анализ сессий (warm-up/fatigue effect)
        - ⚖️ Сравнение ивентов между собой
        - 🔬 Продвинутая аналитика (прогноз улучшения, корреляции)
        - 🌍 Сравнение с мировыми результатами WCA
        """
    )
    st.stop()

# Парсинг
content = uploaded.read().decode('utf-8', errors='ignore')
content_hash = f'{len(content)}_{uploaded.name}'
df = load_data(content, _hash=content_hash)


# ═══════════════════════════════════════════════════════════
# Сайдбар: фильтры
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.header('🔍 Фильтры')

    st.caption(f'Всего сборок: **{len(df):,}**')
    date_min = df['DateTime'].min().date()
    date_max = df['DateTime'].max().date()

    date_range = st.date_input(
        'Период',
        (date_min, date_max),
        min_value=date_min,
        max_value=date_max,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        d_from, d_to = date_range
    else:
        d_from, d_to = date_min, date_max

    exclude_dnf = st.checkbox('Исключить DNF из графиков', value=False)

    st.markdown('---')
    st.caption(
        'Файл: `' + uploaded.name + '`  \n'
        f'Размер: **{len(content) / 1024 / 1024:.1f} МБ**'
    )


mask = (df['DateTime'].dt.date >= d_from) & (df['DateTime'].dt.date <= d_to)
df_f = df[mask].copy()

if len(df_f) == 0:
    st.warning('В выбранном периоде нет сборок.')
    st.stop()


# ═══════════════════════════════════════════════════════════
# Вкладки
# ═══════════════════════════════════════════════════════════
tab_overview, tab_event, tab_activity, tab_sessions, tab_compare, tab_advanced, tab_wca = st.tabs([
    '📊 Overview',
    '🎯 Event Deep-Dive',
    '📅 Activity',
    '⏱️ Sessions',
    '⚖️ Compare Events',
    '🔬 Advanced',
    '🌍 WCA Ranks',
])


# ═══════════════════════════════════════════════════════════
# OVERVIEW
# ═══════════════════════════════════════════════════════════
with tab_overview:
    st.subheader('Общая статистика')

    valid = df_f['EffectiveTime'].dropna()
    total_time = float(valid.sum())
    days_active = df_f['Date'].nunique()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('Всего сборок', f'{len(df_f):,}')
    col2.metric('Ивентов', df_f['Event'].nunique())
    col3.metric('Активных дней', days_active)
    col4.metric('Время в сборках', f'{total_time / 3600:.1f} ч')
    col5.metric(
        'DNF',
        f'{int(df_f["IsDNF"].sum())} ({df_f["IsDNF"].mean() * 100:.1f}%)',
    )

    st.markdown('### Сводка по ивентам')

    overview_df = build_overview_table(
        df_cache_key(df_f),
        pickle.dumps(df_f),
    )
    st.dataframe(overview_df, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(charts.solves_count_pie(df_f), use_container_width=True)
    with col2:
        st.plotly_chart(charts.time_allocation_pie(df_f), use_container_width=True)

    st.plotly_chart(charts.monthly_solves_chart(df_f), use_container_width=True)


# ═══════════════════════════════════════════════════════════
# EVENT DEEP DIVE
# ═══════════════════════════════════════════════════════════
with tab_event:
    events_sorted = sorted(
        df_f['Event'].unique(),
        key=lambda e: -len(df_f[df_f['Event'] == e]),
    )
    event = st.selectbox('Выбери ивент', events_sorted)
    df_ev = df_f[df_f['Event'] == event].reset_index(drop=True)
    if exclude_dnf:
        df_ev = df_ev[~df_ev['IsDNF']].reset_index(drop=True)

    if len(df_ev) < 2:
        st.warning('Слишком мало данных для этого ивента.')
    else:
        s = compute_event_summary(df_ev)

        st.subheader(f'📈 {event}')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('Сборок', s['total_solves'])
        col2.metric('Best single', format_time(s['best_single']))
        col3.metric('Mean', format_time(s['mean']))
        col4.metric(
            'StdDev',
            f'{s["std"]:.2f}s' if not pd.isna(s['std']) else '—',
        )

        st.markdown('### Personal Bests')
        pb_cols = st.columns(6)
        pb_cols[0].metric('Best ao5', format_time(s['best_ao5']))
        pb_cols[1].metric('Best ao12', format_time(s['best_ao12']))
        pb_cols[2].metric('Best ao50', format_time(s['best_ao50']))
        pb_cols[3].metric('Best ao100', format_time(s['best_ao100']))
        pb_cols[4].metric('Current ao12', format_time(s['current_ao12']))
        pb_cols[5].metric('Current ao100', format_time(s['current_ao100']))

        # Графики
        st.plotly_chart(
            charts.progression_chart(df_ev, f'{event} — Progression'),
            use_container_width=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(charts.pb_timeline(df_ev), use_container_width=True)
        with col2:
            st.plotly_chart(charts.histogram_chart(df_ev), use_container_width=True)

        st.plotly_chart(charts.violin_by_month(df_ev), use_container_width=True)

        # Стрики
        st.markdown('### 🔥 Стрики (sub-X подряд)')
        valid_times = df_ev['EffectiveTime'].dropna()
        if len(valid_times):
            median = float(valid_times.median())
            raw_thresholds = [median * k for k in [0.5, 0.75, 0.9, 1.0]]
            thresholds = sorted({round(t, 1) for t in raw_thresholds if t > 0})
            streak_cols = st.columns(len(thresholds))
            for i, th in enumerate(thresholds):
                st_data = streak_stats(df_ev, th)
                streak_cols[i].metric(
                    f'sub-{th}',
                    f'{st_data["max_streak"]}',
                    help=f'current streak: {st_data["current_streak"]}',
                )

        # Lucky solves
        lucky = lucky_solves(df_ev)
        if len(lucky):
            with st.expander(f'🍀 Lucky solves (&lt; mean − 2σ) — {len(lucky)} шт'):
                display = lucky[['DateTime', 'EffectiveTime', 'Scramble']].copy()
                display['EffectiveTime'] = display['EffectiveTime'].apply(format_time)
                st.dataframe(
                    display.head(100),
                    use_container_width=True,
                    hide_index=True,
                )


# ═══════════════════════════════════════════════════════════
# ACTIVITY
# ═══════════════════════════════════════════════════════════
with tab_activity:
    st.subheader('📅 Когда ты собираешь')

    st.plotly_chart(charts.activity_heatmap(df_f), use_container_width=True)
    st.plotly_chart(charts.hour_weekday_heatmap(df_f), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('**По часам дня**')
        hourly = df_f.groupby('Hour').size().reset_index(name='count')
        st.bar_chart(hourly.set_index('Hour'))
    with col2:
        st.markdown('**По дням недели**')
        order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                 'Friday', 'Saturday', 'Sunday']
        weekly = (
            df_f.groupby('Weekday').size()
            .reindex(order).reset_index(name='count')
        )
        st.bar_chart(weekly.set_index('Weekday'))


# ═══════════════════════════════════════════════════════════
# SESSIONS
# ═══════════════════════════════════════════════════════════
with tab_sessions:
    st.subheader('⏱️ Анализ сессий')
    st.caption('Сессия = серия сборок одного ивента без перерыва >30 минут')

    event = st.selectbox(
        'Ивент',
        sorted(df_f['Event'].unique()),
        key='session_event',
    )
    df_ev = df_f[df_f['Event'] == event]
    if exclude_dnf:
        df_ev = df_ev[~df_ev['IsDNF']]

    if len(df_ev) < 5:
        st.warning('Слишком мало данных.')
    else:
        sess = session_stats(df_ev)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric('Всего сессий', len(sess))
        col2.metric('Сборок/сессию (avg)', f'{sess["count"].mean():.1f}')
        col3.metric(
            'Медианная длительность',
            f'{sess["duration_min"].median():.0f} мин',
        )
        col4.metric('Макс. сборок в сессии', int(sess['count'].max()))

        st.plotly_chart(
            charts.session_position_chart(df_ev),
            use_container_width=True,
        )

        st.markdown('### Последние сессии')
        recent = sess.sort_values('start', ascending=False).head(20).copy()
        recent['start'] = recent['start'].dt.strftime('%Y-%m-%d %H:%M')
        recent['mean'] = recent['mean'].apply(format_time)
        recent['best'] = recent['best'].apply(format_time)
        recent['worst'] = recent['worst'].apply(format_time)
        recent['duration_min'] = recent['duration_min'].round(0).astype(int)
        st.dataframe(
            recent[['start', 'count', 'duration_min', 'best', 'mean', 'worst']],
            use_container_width=True,
            hide_index=True,
        )


# ═══════════════════════════════════════════════════════════
# COMPARE EVENTS
# ═══════════════════════════════════════════════════════════
with tab_compare:
    st.subheader('⚖️ Сравнение ивентов')

    st.plotly_chart(charts.boxplot_events(df_f), use_container_width=True)

    st.markdown('### Progression: несколько ивентов на одной шкале (normalized)')
    selected = st.multiselect(
        'Выбери ивенты',
        sorted(df_f['Event'].unique()),
        default=sorted(df_f['Event'].unique())[:3],
    )

    if selected:
        import plotly.graph_objects as go

        fig = go.Figure()
        for ev in selected:
            df_e = (
                df_f[df_f['Event'] == ev]
                .sort_values('DateTime')
                .reset_index(drop=True)
            )
            if len(df_e) < 12:
                continue
            ao12 = rolling_average(df_e['EffectiveTime'], 12)
            if ao12.notna().any():
                first_valid = ao12.dropna().iloc[0]
                if first_valid and first_valid > 0:
                    normalized = ao12 / first_valid * 100
                    fig.add_trace(go.Scattergl(
                        x=df_e['DateTime'],
                        y=normalized,
                        mode='lines',
                        name=ev,
                    ))
        fig.update_layout(
            title='Relative progression (first ao12 = 100%)',
            xaxis_title='Date',
            yaxis_title='% of initial ao12',
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# ADVANCED
# ═══════════════════════════════════════════════════════════
with tab_advanced:
    st.subheader('🔬 Продвинутая аналитика')

    event = st.selectbox(
        'Ивент',
        sorted(df_f['Event'].unique()),
        key='adv_event',
    )
    df_ev = df_f[df_f['Event'] == event].reset_index(drop=True)
    if exclude_dnf:
        df_ev = df_ev[~df_ev['IsDNF']].reset_index(drop=True)

    if len(df_ev) < 50:
        st.warning('Для продвинутой аналитики нужно >50 сборок.')
    else:
        st.plotly_chart(
            charts.rolling_std_chart(df_ev),
            use_container_width=True,
        )

        # Прогноз
        st.markdown('### 🔮 Прогноз улучшения')
        valid = df_ev[df_ev['EffectiveTime'].notna()].copy()
        valid['DayNum'] = (
            (valid['DateTime'] - valid['DateTime'].min()).dt.days
        )

        if len(valid) >= 50 and valid['DayNum'].nunique() > 5:
            log_times = np.log(valid['EffectiveTime'].values.astype(float))
            days = valid['DayNum'].values.astype(float)

            try:
                slope, intercept = np.polyfit(days, log_times, 1)
            except Exception:
                slope, intercept = 0.0, log_times.mean()

            current = float(np.exp(intercept + slope * days[-1]))
            improvement_per_month = float(
                np.exp(intercept + slope * (days[-1] + 30)) - current
            )

            col1, col2 = st.columns(2)
            col1.metric('Текущий тренд', format_time(current))
            col2.metric('Δ за месяц', f'{improvement_per_month:+.2f}s')

            current_mean = float(valid['EffectiveTime'].tail(100).mean())
            target = st.number_input(
                'Целевое время (сек)',
                value=round(current_mean * 0.8, 1),
                step=0.5,
            )
            if slope < 0 and target < current:
                days_to_target = (
                    (np.log(target) - intercept) / slope - days[-1]
                )
                if days_to_target > 0:
                    st.success(
                        f'⏰ По текущему тренду: достигнешь цели через '
                        f'~**{int(days_to_target)}** дней'
                    )
                else:
                    st.info('🎉 Уже достигнуто')
            else:
                st.info('Тренд не показывает улучшения (или цель уже достигнута)')
        else:
            st.caption('Недостаточно разброса данных для прогноза.')

        # Scramble length
        st.markdown('### 🔀 Длина скрамбла vs время')
        scramble_df = df_ev.copy()
        scramble_df['ScrambleLen'] = (
            scramble_df['Scramble'].fillna('').str.split().str.len()
        )
        scramble_df = scramble_df.dropna(subset=['EffectiveTime'])
        scramble_df = scramble_df[scramble_df['ScrambleLen'] > 0]

        if scramble_df['ScrambleLen'].nunique() > 3:
            import plotly.express as px

            # Даунсемпл чтобы plotly не лагал
            sample = scramble_df
            if len(sample) > 5000:
                sample = sample.sample(5000, random_state=42)

            fig = px.scatter(
                sample,
                x='ScrambleLen',
                y='EffectiveTime',
                trendline='ols',
                title='Scramble length vs solve time',
                opacity=0.5,
            )
            st.plotly_chart(fig, use_container_width=True)
            corr = (
                scramble_df[['ScrambleLen', 'EffectiveTime']].corr().iloc[0, 1]
            )
            st.caption(f'Корреляция Пирсона: **{corr:.3f}**')
        else:
            st.info('Длина скрамбла почти не варьируется для этого ивента.')


# ═══════════════════════════════════════════════════════════
# WCA RANKS
# ═══════════════════════════════════════════════════════════
with tab_wca:
    st.subheader('🌍 Сравнение с мировыми результатами WCA')
    st.caption(
        'Данные: [WCA official export](https://www.worldcubeassociation.org/export/results). '
        'Архив ~340 МБ скачивается один раз в неделю.'
    )

    if not st.checkbox('📥 Активировать WCA-сравнение (загрузит данные)', value=False):
        st.info(
            'Первая загрузка займёт 1-3 минуты. '
            'Потом всё будет работать мгновенно из локального кэша.'
        )
        st.stop()

    # Настройки
    with st.expander('⚙️ Настройки'):
        try:
            countries = get_countries_list()
            default_idx = 0
            if 'Poland' in countries:
                default_idx = countries.index('Poland') + 1
            country = st.selectbox(
                'Твоя страна (для национального ранга)',
                ['— не выбрано —'] + countries,
                index=default_idx,
            )
            if country == '— не выбрано —':
                country = None
        except Exception as e:
            st.error(f'Не удалось загрузить список стран: {e}')
            country = None

        rank_basis = st.radio(
            'Сравнивать по:',
            ['Best ao5 (WCA average)', 'Best single'],
            horizontal=True,
        )
        is_average = rank_basis.startswith('Best ao5')

    st.markdown('---')
    st.markdown('### 📋 Твои результаты в мировом контексте')

    summary_rows = []
    kinch_scores = {}

    for event_key, wca_id in EVENT_MAPPING.items():
        puzzle, category = event_key.split('|')
        df_ev = df_f[
            (df_f['Puzzle'] == puzzle) & (df_f['Category'] == category)
        ]
        if len(df_ev) == 0:
            continue

        if is_average:
            my_time = best_ao(df_ev['EffectiveTime'], 5)
        else:
            valid = df_ev['EffectiveTime'].dropna()
            my_time = float(valid.min()) if len(valid) else None

        if my_time is None or pd.isna(my_time):
            continue

        try:
            ranks = get_ranks_for_event(
                wca_id, 'average' if is_average else 'single',
            )
            rank_info = find_rank_for_time(ranks, my_time, country)
            wr = float(ranks['time_seconds'].min())
            kinch = kinchrank_score(my_time, wr)
            kinch_scores[EVENT_DISPLAY.get(wca_id, wca_id)] = kinch

            row = {
                'Event': EVENT_DISPLAY.get(wca_id, wca_id),
                'Your time': f'{my_time:.2f}s',
                'World Record': f'{wr:.2f}s',
                '% of WR': f'{kinch:.1f}%',
                'World rank':
                    f'#{rank_info["world_rank"]:,} / {rank_info["total_world"]:,}',
                'Percentile': (
                    f'top {100 - rank_info["percentile_world"]:.1f}%'
                    if rank_info['percentile_world'] is not None else '—'
                ),
            }
            if country and rank_info.get('country_rank'):
                row[f'{country} rank'] = (
                    f'#{rank_info["country_rank"]} / '
                    f'{rank_info["total_country"]}'
                )
            summary_rows.append(row)
        except Exception as e:
            st.warning(f'Не удалось загрузить ранги для {event_key}: {e}')

    if summary_rows:
        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=True,
            hide_index=True,
        )

        if len(kinch_scores) >= 3:
            st.plotly_chart(
                charts.kinchrank_radar(kinch_scores),
                use_container_width=True,
            )

        # Детально
        st.markdown('---')
        st.markdown('### 🔍 Детально по ивенту')

        available_events = []
        for event_key, wca_id in EVENT_MAPPING.items():
            puzzle, category = event_key.split('|')
            df_ev = df_f[
                (df_f['Puzzle'] == puzzle) & (df_f['Category'] == category)
            ]
            if len(df_ev) > 0:
                available_events.append(EVENT_DISPLAY.get(wca_id, wca_id))

        if available_events:
            selected_display = st.selectbox('Выбери ивент', available_events)

            event_key = None
            wca_id = None
            for k, v in EVENT_MAPPING.items():
                if EVENT_DISPLAY.get(v, v) == selected_display:
                    event_key = k
                    wca_id = v
                    break

            if event_key and wca_id:
                puzzle, category = event_key.split('|')
                df_ev = df_f[
                    (df_f['Puzzle'] == puzzle) & (df_f['Category'] == category)
                ]

                if is_average:
                    my_time = best_ao(df_ev['EffectiveTime'], 5)
                else:
                    my_time = float(df_ev['EffectiveTime'].dropna().min())

                ranks = get_ranks_for_event(
                    wca_id, 'average' if is_average else 'single',
                )
                rank_info = find_rank_for_time(ranks, my_time, country)
                wr = float(ranks['time_seconds'].min())

                col1, col2, col3, col4 = st.columns(4)
                col1.metric('Твоё время', f'{my_time:.2f}s')
                col2.metric(
                    'Мировой ранг',
                    f'#{rank_info["world_rank"]:,}',
                    help=f'из {rank_info["total_world"]:,} участников WCA',
                )
                col3.metric(
                    'Percentile',
                    f'top {100 - rank_info["percentile_world"]:.1f}%',
                )
                col4.metric('% от WR', f'{kinchrank_score(my_time, wr):.1f}%')

                if country and rank_info.get('country_rank'):
                    st.info(
                        f"🏳️ В стране **{country}**: "
                        f"#{rank_info['country_rank']} из "
                        f"{rank_info['total_country']} "
                        f"(top {100 - rank_info['percentile_country']:.1f}%)"
                    )

                st.plotly_chart(
                    charts.wca_comparison_chart(ranks, my_time, selected_display),
                    use_container_width=True,
                )

                st.markdown(f'**🏆 Топ-10 {selected_display} в мире:**')
                top = get_top_times(ranks, 10).copy()
                top['time_seconds'] = top['time_seconds'].apply(
                    lambda t: f'{t:.2f}s'
                )
                top.columns = ['Rank', 'Name', 'Country', 'Time']
                st.dataframe(top, use_container_width=True, hide_index=True)
    else:
        st.warning('Нет данных для сравнения с WCA.')

    st.markdown('---')
    if st.button('🔄 Обновить кэш WCA (принудительно)'):
        download_wca_data.clear()
        download_wca_data(force=True)
        st.success('Кэш обновлён!')
        st.rerun()