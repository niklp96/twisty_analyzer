# 🧊 Rubik's Cube Solves Analytics

Streamlit-дашборд для анализа твоих сборок кубика Рубика с подробной статистикой, красивыми графиками и сравнением с мировыми результатами WCA.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Возможности

- 📊 **Overview** — общая статистика: total solves, активные дни, время в сборках, сводная таблица по всем ивентам
- 🎯 **Event Deep-Dive** — детальный анализ отдельного ивента:
  - Personal Bests (ao5, ao12, ao50, ao100)
  - Progression chart со скользящими средними
  - PB timeline — когда ты бил рекорды
  - Гистограмма и violin-plot распределения времён
  - Стрики (sub-X сборок подряд)
  - Lucky solves (результаты быстрее mean − 2σ)
- 📅 **Activity** — когда ты собираешь:
  - GitHub-style календарный heatmap
  - Распределение по часам и дням недели
- ⏱️ **Sessions** — анализ сессий:
  - Автоопределение сессий (перерыв >30 мин = новая сессия)
  - Warm-up / fatigue effect
  - Таблица последних сессий
- ⚖️ **Compare Events** — сравнение ивентов:
  - Boxplot всех ивентов
  - Нормализованный прогресс (первый ao12 = 100%)
- 🔬 **Advanced**:
  - Rolling Coefficient of Variation (стабильность со временем)
  - Прогноз достижения целевого времени (log-linear regression)
  - Корреляция длины скрамбла и времени сборки
- 🌍 **WCA Ranks** — сравнение с мировыми результатами:
  - Автозагрузка актуальных данных через [WCA API v2](https://www.worldcubeassociation.org/export/results)
  - Мировой и национальный ранг для каждого твоего ивента
  - Percentile (в каких топ-% ты находишься)
  - Kinchrank radar chart (% от WR по всем ивентам)
  - Гистограмма результатов всех участников WCA с отметкой "где ты"
  - Топ-10 мира по каждому ивенту

## 📦 Установка

### Требования

- Python 3.10 или новее
- ~2 ГБ свободного места на диске (для кэша WCA данных)

### Шаги

1. **Клонируй репозиторий** (или просто скачай все файлы в одну папку):

   ```bash
   git clone https://github.com/yourusername/rubik-stats.git
   cd rubik-stats
   ```

2. **Создай виртуальное окружение** (рекомендуется):

   ```bash
   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Установи зависимости:**

   ```bash
   pip install -r requirements.txt
   ```

### requirements.txt

```txt
streamlit>=1.28.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.17.0
requests>=2.31.0
statsmodels>=0.14.0
```

## 🚀 Запуск

```bash
streamlit run app.py
```

Приложение откроется в браузере по адресу [http://localhost:8501](http://localhost:8501).

## 📄 Формат входного файла

Приложение принимает txt-файл, экспортированный из таймеров типа **ChaoTimer**, **Prisma Puzzle Timer** и совместимых. Формат:

```
Puzzle,Category,Time(millis),Date(millis),Scramble,Penalty,Comment
"333";"Normal";"16050";"1504341094061";"U' L2 F2 D2 L2 U' ...";"0";""
"333";"Normal";"11590";"1504341133078";"D' L U R F' L' B' D' ...";"0";""
"pyra";"Normal";"7800";"1504341742128";"R' L B' R' B' R B' L' ...";"0";""
...
```

**Поддерживаемые ивенты:**

| Код в файле | Ивент |
|---|---|
| `222` | 2x2x2 |
| `333` | 3x3x3 |
| `333` + `oh` | 3x3 One-Handed |
| `333` + `bld` | 3x3 Blindfolded |
| `333` + `fm` | Fewest Moves |
| `333` + `ft` | 3x3 With Feet |
| `444` | 4x4x4 |
| `555` | 5x5x5 |
| `666` | 6x6x6 |
| `777` | 7x7x7 |
| `pyra` | Pyraminx |
| `mega` | Megaminx |
| `sq1` | Square-1 |
| `clock` | Clock |
| `skewb` | Skewb |

**Penalty:** `0` — OK, `1` — +2 секунды, `2` — DNF

## 🗂️ Структура проекта

```
rubik-stats/
├── app.py              # Главное Streamlit приложение (UI)
├── data_loader.py      # Парсинг txt файла в DataFrame
├── stats.py            # Вычисление статистик (ao5, ao12, PB, стрики, ...)
├── charts.py           # Plotly графики
├── wca_rankings.py     # Интеграция с WCA export API
├── requirements.txt    # Python зависимости
├── README.md           # Этот файл
├── .wca_cache/         # Локальный кэш данных WCA (создаётся автоматически)
└── times.txt           # Твои данные (не коммитится в git)
```

## 🎯 Быстрый старт

1. Запусти приложение: `streamlit run app.py`
2. В боковой панели нажми **"Browse files"** и загрузи свой txt файл.
3. Исследуй вкладки!

Если хочешь увидеть своё место в мировых рангах:

4. Перейди на вкладку **🌍 WCA Ranks**.
5. Поставь галочку **"📥 Активировать WCA-сравнение"**.
6. Дождись скачивания архива (1-3 минуты первый раз).
7. Выбери свою страну в настройках, чтобы увидеть национальный ранг.

## ⚙️ Настройки и фильтры

В боковой панели доступны:
- **Период** — фильтр по датам
- **Исключить DNF** — скрыть DNF на графиках

## 🧮 Как считаются метрики

### WCA-style average (ao5, ao12, ...)
Из окна N сборок удаляются лучшая и худшая, среднее считается по оставшимся.  
Если в окне **2+ DNF** — весь average = DNF.  
Если **1 DNF** — он считается как "худшая сборка" и отбрасывается.

### Сессии
Автоматически определяются по перерыву **>30 минут** между сборками одного ивента.

### Kinchrank (% от WR)
`(World_Record_time / Your_time) × 100`  
- **100%** — у тебя мировой рекорд 🏆
- **50%** — ты в 2 раза медленнее WR
- **25%** — в 4 раза медленнее

### Прогноз улучшения
Log-linear regression по всем валидным сборкам ивента:  
`log(time) = a × days + b`  
Экстраполяция показывает, когда при текущем темпе ты достигнешь целевого времени.

## 🌍 Данные WCA

- Источник: [WCA Public Export API v2](https://www.worldcubeassociation.org/api/v0/export/public)
- Архив: ~340 МБ (TSV формат)
- Обновление: еженедельно на сайте WCA; в приложении автоматически раз в 7 дней
- Кэш: `.wca_cache/` (локально, не требует повторной загрузки)
- Принудительное обновление: кнопка **🔄 Обновить кэш WCA** на вкладке WCA Ranks

## 💡 Производительность

Приложение оптимизировано для больших файлов:

| Размер файла | Сборок | Время загрузки |
|---|---|---|
| 1 МБ | ~5k | < 1 сек |
| 5 МБ | ~25k | ~1 сек |
| 17 МБ | ~100k | 2-3 сек |
| 50 МБ | ~300k | 5-8 сек |

Используется векторизация NumPy, WebGL-рендеринг (`Scattergl`) для больших графиков и кэширование через `@st.cache_data`.

## 🐛 Траблшутинг

### `KeyError: 'EffectiveTime'`
В txt файле нестандартный формат колонок. Проверь, что первая строка — это:
```
Puzzle,Category,Time(millis),Date(millis),Scramble,Penalty,Comment
```

### `ModuleNotFoundError: No module named 'statsmodels'`
Установи недостающий пакет:
```bash
pip install statsmodels
```

### WCA загрузка обрывается / timeout
- Проверь интернет (нужен стабильный канал на 340 МБ)
- Попробуй вручную скачать архив с [сайта WCA](https://www.worldcubeassociation.org/export/results) и положить в `.wca_cache/`
- Перезапусти приложение

### Приложение тормозит на больших файлах
- Сузь **период** в фильтрах боковой панели
- Для Advanced-аналитики выбирай один ивент за раз
- Закрой другие тяжёлые вкладки браузера

### Ошибка 410 от WCA API
WCA переходят на новые версии экспорта. Обнови `wca_rankings.py` до последней версии — код поддерживает **v2.0.2**.

## 🔧 Разработка

### Добавить новый ивент

В `data_loader.py` добавь в словарь `PUZZLE_NAMES`:
```python
PUZZLE_NAMES = {
    ...
    'new_puzzle': 'New Puzzle Display Name',
}
```

В `wca_rankings.py` добавь маппинг к WCA event_id:
```python
EVENT_MAPPING = {
    ...
    'new_puzzle|Normal': 'wca_event_id',
}
EVENT_DISPLAY = {
    ...
    'wca_event_id': 'Display Name',
}
```

### Добавить новый график

1. Создай функцию в `charts.py`:
   ```python
   def my_new_chart(df: pd.DataFrame) -> go.Figure:
       fig = go.Figure()
       # ...
       return fig
   ```

2. Используй в `app.py`:
   ```python
   st.plotly_chart(charts.my_new_chart(df_ev), use_container_width=True)
   ```

## 📜 Лицензия

MIT License — делай с кодом что хочешь.

## 🙏 Благодарности

- [WCA](https://www.worldcubeassociation.org) — за открытые данные о соревнованиях
- [Streamlit](https://streamlit.io) — за лучший фреймворк для быстрых дашбордов
- [Plotly](https://plotly.com) — за красивые интерактивные графики

## 📬 Обратная связь

Нашёл баг или хочешь фичу? Открой issue или PR в репозитории.

---

**Happy cubing! 🧊⚡**