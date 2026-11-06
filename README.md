# OpenAnimEasy

Бесплатный open-source набор инструментов для анимации в Blender. Повторяет
рабочие сценарии платного аддона [AnimEasy](https://animeasy.pro/) — тайминг,
кривые, спейсинг, позинг, библиотека поз и анимаций. Весь код написан с нуля,
без копирования исходников и ассетов AnimEasy.

- Лицензия: GPL-3.0-or-later (см. `LICENSE`)
- Версия: 0.1.0
- Blender: заявлен 4.4+, протестирован на 5.2.3 LTS
- Зависимостей нет: только `bpy` и стандартная библиотека Python

## Установка

### Из zip

1. `Edit > Preferences > Add-ons > Install...`
2. Выберите `OpenAnimEasy-0.1.0.zip` (внутри архива папка `open_anim_easy/`).
3. Включите галочку **Animation: OpenAnimEasy**.

### Вручную

Скопируйте папку `open_anim_easy` в каталог аддонов Blender:

- Windows: `%APPDATA%\Blender Foundation\Blender\<версия>\scripts\addons\`
- Linux: `~/.config/blender/<версия>/scripts/addons/`
- macOS: `~/Library/Application Support/Blender/<версия>/scripts/addons/`

## Где находится

- Меню **OpenAnimEasy** в заголовке Dope Sheet, Graph Editor, NLA Editor и 3D Viewport.
- Боковая панель **AnimEasy** (`N`) в Graph Editor, Dope Sheet и 3D Viewport.
- Настройки аддона: `Edit > Preferences > Add-ons > OpenAnimEasy` — можно скрыть
  секции панели, изменить шаг гизмо, число кадров призраков и шаг запекания.

Горячих клавиш аддон не назначает: всё вызывается из меню и панелей.

## Возможности

### Тайминг

- Переключение Timeline / Graph Editor.
- **Fast Frame Range** — протяжка мышью по таймлайну задаёт диапазон сцены.
- **Frame View**: показать всё, только анимированные кривые, только выбранные,
  установить/снять preview range.
- Выбор ключей слева/справа от текущего кадра.
- **Snap Keys**: к текущему кадру, по первому или последнему выбранному ключу.
- Сдвиг выбранных ключей на N кадров.
- **Inbetween**: равномерно расставить промежуточные кадры, добавить или убрать
  пустой кадр.
- **Add Key Type**: Keyframe, Breakdown, Moving Hold, Extreme, Jitter.
- **Delete Keys**: текущий, выбранные, все.
- **Clean Animation**, **Crop Animation**.
- **Share Key Times** — перенести тайминг ключей с ведущего объекта/кости на
  остальные выбранные.
- **Time Offset** — сдвиг анимации по времени.

### Кривые

- Интерполяция: Constant, Linear, Bezier, Sine, Quad, Cubic, Expo, Back, Bounce,
  Elastic.
- Типы рукояток: Auto, Auto Clamped, Vector, Free, Aligned.
- Значения ключей: обнулить, поставить текущее значение, negate, invert,
  invert over 2D cursor, invert over current value, mirror values, mirror over
  timeline cursor.
- Увеличение/уменьшение значений на настраиваемую величину.
- Copy / Paste / Paste Flipped (зеркалирование по именам костей `.L`/`.R`).
- **Clean Up**: лишние ключи, запечённые ключи, статические каналы, Euler filter.
- **Bake**: анимация объекта или выбранных костей, выбранные кривые, запекание
  под тайминг-паттерн.
- **Ghost Curve** — призрачные копии объекта на соседних кадрах.
- **Motion Paths**: показать, обновить, очистить (объекты и кости).

### Спейсинг

- **Breakdowner** — модальный инструмент вставки промежуточного ключа.
- **Blend**: к соседу, к значению по умолчанию, среднее, ease in/out, smooth,
  push, pull.
- Настройка силы воздействия (factor).

### Позинг

- Выбор противоположных, родительских и дочерних костей.
- **Pose Clipboard**: copy, paste, paste flipped, сохранение в библиотеку.
- **Reset Transforms**: всё, location, rotation, scale.
- Размер гизмо.
- Циклическое переключение orientation и pivot point.
- **Pivot Offset** — 3D-курсор в активную кость/объект и pivot = cursor,
  повторное нажатие возвращает прежний pivot.
- **Silhouette Toggle** — плоский силуэтный режим во всех 3D-вьюпортах.

### Сцена, риг и библиотека

- **Markers**: добавить, удалить текущий, выбранные, все.
- **Child Of**: создать, включить/выключить, запечь, удалить constraint.
- **Space Conversion**: local → world и world → local (с запеканием).
- **Библиотека поз и анимаций** в JSON:
  - сохранить текущую позу или анимацию активного объекта;
  - применить запись из списка;
  - удалить запись.
- Каталог библиотеки:
  `bpy.utils.user_resource("CONFIG")/OpenAnimEasy/{poses,animations}`
  (на Windows это `%APPDATA%\Blender Foundation\Blender\<версия>\config\OpenAnimEasy`).
  Файлы переносимы между машинами и версиями Blender.

## Ограничения и отличия от AnimEasy

- Редактируемые 3D motion paths не реализованы — используются встроенные
  motion paths Blender.
- Нет IK/FK switcher.
- «Global offset» реализован как сдвиг по времени, а не как отдельный
  глобальный контроллер.
- Space conversion для костей частичный: корректно работает для объектов и
  базовых случаев, сложные иерархии с constraint'ами могут требовать ручной
  проверки.
- Нет готовых пресетов, туториалов и облачной библиотеки платного аддона.

## Разработка и тесты

Структура пакета:

```
open_anim_easy/
  __init__.py   регистрация
  core.py       работа с layered actions, ключами, View2D
  timeline.py   тайминг, маркеры, интерполяция
  curves.py     кривые, спейсинг, bake, motion paths
  pose.py       позинг, выбор, pivot, silhouette
  rig.py        Child Of, space conversion
  library.py    JSON-библиотека
  ui.py         меню, панели, настройки
tests/
  smoke.py          базовые операции (26 проверок)
  curves_rig.py     кривые, риг, спейсинг (32 проверки)
  bake_library.py   bake костей и объектов, библиотека, pivot (15 проверок)
```

Запуск тестов headless (пути подставьте свои):

```powershell
& "C:\Program Files\Blender Foundation\Blender\blender.exe" -b --factory-startup `
  --python tests\smoke.py
```

Тесты используют временный `BLENDER_USER_CONFIG`, чтобы не засорять основную
конфигурацию:

```powershell
$env:BLENDER_USER_CONFIG = "C:\Temp\oae-config"
```

## Лицензия

GPL-3.0-or-later. Полный текст — в файле `LICENSE`.
