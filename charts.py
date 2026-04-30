import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from stats import rolling_average, detect_pbs, session_stats

def _downsample_for_scatter(x, y, max_points: int = 5000):
    """Равномерно прореживает, если точек больше max_points."""
    n = len(x)
    if n <= max_points:
        return x, y
    step = n // max_points
    return x[::step], y[::step]

def progression_chart(df_event: pd.DataFrame, title: str = 'Progression') -> go.Figure:
    df = df_event.reset_index(drop=True)
    x = df['DateTime']
    y = df['EffectiveTime']
    fig = go.Figure()

    # Scatter с даунсемплингом
    x_ds, y_ds = _downsample_for_scatter(x.values, y.values, max_points=5000)
    fig.add_trace(go.Scattergl(  # WebGL = в разы быстрее рендер
        x=x_ds, y=y_ds,
        mode='markers', name='Single',
        marker=dict(size=3, color='lightblue', opacity=0.5),
        hovertemplate='%{y:.2f}s<br>%{x}<extra></extra>',
    ))

    # Линии ao — тоже можно даунсемплить, но они считаются быстро
    colors = {'ao5': '#1f77b4', 'ao12': '#ff7f0e',
               'ao100': '#2ca02c', 'ao1000': '#d62728'}
    for n, color in [(5, colors['ao5']), (12, colors['ao12']),
                      (100, colors['ao100']), (1000, colors['ao1000'])]:
        if len(df) >= n:
            ao = rolling_average(df['EffectiveTime'], n)
            # Даунсемплим для отрисовки
            x_line, y_line = _downsample_for_scatter(x.values, ao.values, max_points=10000)
            fig.add_trace(go.Scattergl(
                x=x_line, y=y_line, mode='lines',
                name=f'ao{n}',
                line=dict(color=color, width=2 if n <= 12 else 3),
            ))

    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Time (seconds)',
        hovermode='x unified',
        height=500,
    )
    return fig


def pb_timeline(df_event: pd.DataFrame) -> go.Figure:
    df = detect_pbs(df_event).reset_index(drop=True)
    fig = go.Figure()

    singles = df[df['PB_Single']]
    fig.add_trace(go.Scattergl(
        x=singles['DateTime'], y=singles['EffectiveTime'],
        mode='markers+lines', name='PB Single',
        marker=dict(size=10, color='gold', symbol='star'),
        line=dict(color='gold', dash='dot'),
    ))

    for n, color, symbol in [(5, '#1f77b4', 'circle'),
                              (12, '#ff7f0e', 'square'),
                              (100, '#2ca02c', 'diamond')]:
        col = f'PB_ao{n}'
        if col in df.columns and df[col].any():
            pbs = df[df[col]]
            ao = rolling_average(df['EffectiveTime'], n)
            fig.add_trace(go.Scattergl(
                x=pbs['DateTime'], y=ao.loc[pbs.index],
                mode='markers+lines', name=f'PB ao{n}',
                marker=dict(size=8, color=color, symbol=symbol),
                line=dict(color=color, dash='dash'),
            ))

    fig.update_layout(
        title='Personal Best Timeline',
        xaxis_title='Date',
        yaxis_title='Time (seconds)',
        height=450,
    )
    return fig


def histogram_chart(df_event: pd.DataFrame) -> go.Figure:
    valid = df_event['EffectiveTime'].dropna()
    fig = px.histogram(valid, nbins=50,
                       title='Distribution of Solve Times',
                       labels={'value': 'Time (seconds)'})
    fig.add_vline(x=valid.mean(), line_dash='dash', line_color='red',
                  annotation_text=f'Mean: {valid.mean():.2f}s')
    fig.add_vline(x=valid.median(), line_dash='dot', line_color='green',
                  annotation_text=f'Median: {valid.median():.2f}s')
    fig.update_layout(height=400, showlegend=False)
    return fig


def monthly_solves_chart(df: pd.DataFrame) -> go.Figure:
    monthly = df.groupby(['Month', 'Event']).size().reset_index(name='count')
    fig = px.bar(monthly, x='Month', y='count', color='Event',
                 title='Solves per Month',
                 labels={'count': 'Number of Solves'})
    fig.update_layout(height=400, xaxis_tickangle=-45)
    return fig


def activity_heatmap(df: pd.DataFrame) -> go.Figure:
    """GitHub-style календарный heatmap."""
    daily = df.groupby('Date').size().reset_index(name='count')
    daily['Date'] = pd.to_datetime(daily['Date'])
    daily['Weekday'] = daily['Date'].dt.day_name()
    daily['Week'] = daily['Date'].dt.isocalendar().week
    daily['Year'] = daily['Date'].dt.year
    daily['YearWeek'] = daily['Year'].astype(str) + '-W' + daily['Week'].astype(str).str.zfill(2)

    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot = daily.pivot_table(index='Weekday', columns='YearWeek', values='count', aggfunc='sum')
    pivot = pivot.reindex(weekday_order)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='Greens',
        hovertemplate='%{x}<br>%{y}: %{z} solves<extra></extra>',
    ))
    fig.update_layout(
        title='Activity Heatmap (solves per day)',
        height=300,
        xaxis_title='Week',
        yaxis_title='',
    )
    return fig


def hour_weekday_heatmap(df: pd.DataFrame) -> go.Figure:
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot = df.pivot_table(index='Weekday', columns='Hour', values='Time', aggfunc='count').fillna(0)
    pivot = pivot.reindex(weekday_order)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index,
        colorscale='Viridis',
        hovertemplate='%{y} %{x}:00<br>%{z} solves<extra></extra>',
    ))
    fig.update_layout(
        title='When do you solve? (weekday × hour)',
        height=350,
        xaxis_title='Hour of day',
    )
    return fig


def boxplot_events(df: pd.DataFrame) -> go.Figure:
    """Боксплоты всех ивентов на одном графике."""
    fig = px.box(df.dropna(subset=['EffectiveTime']),
                 x='Event', y='EffectiveTime',
                 title='Time distribution per event',
                 labels={'EffectiveTime': 'Time (seconds)'})
    fig.update_layout(height=450)
    return fig


def violin_by_month(df_event: pd.DataFrame) -> go.Figure:
    fig = px.violin(df_event.dropna(subset=['EffectiveTime']),
                    x='Month', y='EffectiveTime', box=True,
                    title='Time distribution per month')
    fig.update_layout(height=450, xaxis_tickangle=-45)
    return fig


def session_position_chart(df_event: pd.DataFrame) -> go.Figure:
    """Средние времена по позиции в сессии (warm-up / fatigue effect)."""
    df = df_event.dropna(subset=['EffectiveTime'])
    by_pos = df.groupby('SessionPosition')['EffectiveTime'].agg(['mean', 'count']).reset_index()
    by_pos = by_pos[by_pos['count'] >= 5]

    fig = go.Figure()
    fig.add_trace(go.Scattergl(
        x=by_pos['SessionPosition'], y=by_pos['mean'],
        mode='lines+markers', name='Mean time',
    ))
    fig.update_layout(
        title='Warm-up / Fatigue effect',
        xaxis_title='Position in session',
        yaxis_title='Mean time (s)',
        height=350,
    )
    return fig


def time_allocation_pie(df: pd.DataFrame) -> go.Figure:
    allocation = df.dropna(subset=['EffectiveTime']).groupby('Event')['EffectiveTime'].sum()
    fig = px.pie(values=allocation.values, names=allocation.index,
                 title='Time spent per event (total)')
    fig.update_layout(height=400)
    return fig


def solves_count_pie(df: pd.DataFrame) -> go.Figure:
    counts = df.groupby('Event').size()
    fig = px.pie(values=counts.values, names=counts.index,
                 title='Number of solves per event')
    fig.update_layout(height=400)
    return fig


def rolling_std_chart(df_event: pd.DataFrame, window: int = 50) -> go.Figure:
    df = df_event.reset_index(drop=True).copy()
    df['rolling_std'] = df['EffectiveTime'].rolling(window).std()
    df['rolling_mean'] = df['EffectiveTime'].rolling(window).mean()
    df['cv'] = df['rolling_std'] / df['rolling_mean'] * 100

    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=df['DateTime'], y=df['cv'],
                              mode='lines', name='CV (%)',
                              line=dict(color='purple')))
    fig.update_layout(
        title=f'Consistency over time (rolling CV, window={window})',
        xaxis_title='Date',
        yaxis_title='Coefficient of Variation (%)',
        height=350,
    )
    return fig

def wca_comparison_chart(ranks_df, my_time: float, event_name: str) -> go.Figure:
    """Распределение всех WCA результатов + где ты."""
    import plotly.graph_objects as go
    
    # Обрезаем выбросы для красоты (до 99 перцентиля)
    cutoff = ranks_df['time_seconds'].quantile(0.99)
    display_df = ranks_df[ranks_df['time_seconds'] <= cutoff]
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=display_df['time_seconds'],
        nbinsx=80,
        name='WCA competitors',
        marker_color='lightblue',
        opacity=0.7,
    ))
    
    if not pd.isna(my_time):
        fig.add_vline(
            x=my_time, line_width=3, line_dash='dash', line_color='red',
            annotation_text=f'YOU: {my_time:.2f}s',
            annotation_position='top',
        )
    
    wr = ranks_df['time_seconds'].min()
    fig.add_vline(
        x=wr, line_width=2, line_color='gold',
        annotation_text=f'WR: {wr:.2f}s',
        annotation_position='top left',
    )
    
    fig.update_layout(
        title=f'{event_name} — your position among WCA competitors',
        xaxis_title='Time (seconds)',
        yaxis_title='Number of competitors',
        height=400,
        bargap=0.02,
    )
    return fig


def kinchrank_radar(scores: dict) -> go.Figure:
    """Radar chart по всем ивентам: % от WR."""
    import plotly.graph_objects as go
    
    categories = list(scores.keys())
    values = list(scores.values())
    
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='% of WR',
        line_color='#1f77b4',
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100]),
        ),
        title='Kinchrank: your result as % of World Record',
        height=500,
    )
    return fig