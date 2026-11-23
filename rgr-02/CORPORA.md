# Корпуса для РГР №2

Корпуса собраны из статей Википедии на английском, русском и белорусском языках. Объём измерен штатным токенизатором работы №1. Пробные английская и русская выборки находятся в Git и подходят для демонстрации. Полная выборка подготавливается один раз в `data/corpora/<язык>`.

| Язык | В Git, словоупотреблений | Полная выборка, словоупотреблений | Статей в полной выборке |
| --- | ---: | ---: | ---: |
| Английский `en` | 31 237 | 5 000 670 | 1 547 |
| Русский `ru` | 27 029 | 5 001 627 | 2 494 |
| Белорусский `be` | — | 5 001 066 | 15 790 |

## Подготовка полных текстов

Выполни из папки `rgr-02` в активном окружении Python 3.12:

```powershell
python -m pip install -r requirements-corpus.txt
python prepare_corpus.py en ru be
```

Скрипт читает строки Parquet по сети и останавливается после первой полной статьи, с которой набирается минимум 5 000 000 словоупотреблений на язык. Можно подготовить один язык отдельной командой, например `python prepare_corpus.py ru`. В локальной папке каждого языка появятся `wikipedia.txt` и `sources.csv`. Параметр `--words` позволяет выбрать другой минимальный объём. Для быстрого белорусского прогона можно выполнить `python prepare_corpus.py be --words 25000 --exclude-domain-pages --out data/demo` и передать в анализ `data/demo/be`.

## Запуск РГР

В PowerShell из `rgr-02`. Установи зависимости анализа командой `python -m pip install -r requirements.txt`, если ещё этого не делал.

```powershell
python main.py en .\data\corpora\en --out .\out\full-en
python main.py ru .\data\corpora\ru --out .\out\full-ru
python main.py be .\data\corpora\be --be-lexicon "$env:TEMP\UD_Belarusian-HSE-rgr2\be_hse-ud-train.conllu" --out .\out\full-be
```

Для пробного запуска укажи `.\corpora-sample\en` или `.\corpora-sample\ru` и другой каталог результатов, например `.\out\sample-ru`. Для заполнения титульного листа добавь `--author "Фамилия Имя Отчество" --course 3 --group 12`.

Для белорусской лемматизации используется CoNLL-U. Если файл ещё не скачан, выполни один раз:

```powershell
git clone --depth 1 --branch r2.17 https://github.com/UniversalDependencies/UD_Belarusian-HSE.git "$env:TEMP\UD_Belarusian-HSE-rgr2"
```

## Источник и воспроизводимость

Источник текстов — [Wikimedia Wikipedia](https://huggingface.co/datasets/wikimedia/wikipedia/tree/b04c8d1ceb2f5cd4588862100d08de323dccfbaa), срез `20231101`, ревизия `b04c8d1ceb2f5cd4588862100d08de323dccfbaa`. Тексты и авторство принадлежат участникам Википедии. Лицензия текстов — [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). URL статей и доступ к истории их авторства указаны в `sources.csv` каждого корпуса.

Тексты взяты из начала первого шарда каждого языка в исходном порядке. При сборке удалены внешние пробельные символы, переводы строк приведены к LF, статьи разделены пустой строкой. Целые статьи и порядок учитываются при расчёте сегментов. Корпуса относятся к энциклопедическому жанру, а выборка зависит от порядка статей в срезе. Объёмы и контрольные суммы файлов приведены в [corpora-metadata.json](corpora-metadata.json). Исходный английский текст `work-01` используется для отдельного исторического прогона из папки `example`.
