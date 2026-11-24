from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


MODES = ("Словоформы", "Леммы")
LANGUAGES = {"en": "Английский", "ru": "Русский", "be": "Белорусский"}
HEADINGS = (
    "Задание 1. Закон Ципфа",
    "Задание 2. Эмпирический закон Ципфа",
    "Задание 3. Расчёт коэффициента D Жуйана",
)


def plots(out, data):
    for name in ("zipf", "length"):
        figure, axes = plt.subplots(1, 2, figsize=(7.5, 2.9), layout="constrained")
        for ax, mode, (ranks, counts, words, zipf, length) in zip(axes, MODES, data):
            ax.set_title(mode)
            ax.set_ylabel("Абсолютная частота")
            ax.grid(alpha=0.22)
            if name == "zipf":
                ax.set(xscale="log", yscale="log", xlabel="Ранг")
                ax.scatter(ranks, counts, s=8, alpha=0.65, label="Наблюдения")
                ax.plot(ranks, [zipf["c"] / rank for rank in ranks], color="#a33925",
                        label="c / ранг")
            else:
                ax.set(xlabel="Длина, букв", yscale="log")
                if words:
                    _, letters, frequencies = zip(*words)
                    ax.scatter(letters, frequencies, s=19, alpha=0.7, label="Служебные слова")
                    x = list(range(min(letters), max(letters) + 1))
                    ax.plot(x, [length["fit"]["c"] / value for value in x], "o-",
                            markersize=2, color="#a33925", label="k / длина")
                else:
                    ax.text(0.5, 0.5, "Список совпадений пуст", ha="center",
                            transform=ax.transAxes)
            if ax.get_legend_handles_labels()[0]:
                ax.legend(loc="upper right", fontsize=8)
        figure.savefig(out / f"{name}.png", dpi=200)
        plt.close(figure)


def number(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}".replace(".", ",")


def setup_document(author_name):
    doc = Document()
    doc.core_properties.author = author_name
    doc.core_properties.title = "Расчётно-графическая работа №2"
    doc.core_properties.comments = ""
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin, section.right_margin = Cm(3), Cm(1)
    section.different_first_page_header_footer = True
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "Times New Roman", Pt(14)
    style.paragraph_format.line_spacing = Pt(18)
    style.paragraph_format.space_after = Pt(6)
    for name in ("Title", "Heading 1"):
        style = doc.styles[name]
        style.font.name, style.font.size = "Times New Roman", Pt(16)
        style.font.bold, style.font.color.rgb = True, RGBColor(0, 0, 0)
        fonts = style.element.rPr.rFonts
        for theme in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            fonts.attrib.pop(qn(f"w:{theme}"), None)
        for border in style.element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        style.paragraph_format.line_spacing = Pt(18)
        style.paragraph_format.space_after = Pt(36)
    doc.styles["Heading 1"].paragraph_format.page_break_before = True

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    value = OxmlElement("w:fldSimple")
    value.set(qn("w:instr"), "PAGE")
    footer._p.append(value)
    return doc


def caption(doc, text, centered):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.keep_with_next = not centered
    run = paragraph.add_run(text)
    run.bold, run.font.size = True, Pt(12)


def figure(doc, path, label, width=16.5):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.keep_with_next = True
    paragraph.add_run().add_picture(str(path), width=Cm(width))
    caption(doc, label, centered=True)


def table(doc, title, headings, rows, widths):
    caption(doc, title, centered=False)
    result = doc.add_table(rows=1, cols=len(headings))
    result.autofit = False
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = OxmlElement(f"w:{edge}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), "4")
        border.set(qn("w:color"), "D9D9D9")
        borders.append(border)
    result._tbl.tblPr.append(borders)
    for column, width in zip(result.columns, widths):
        column.width = Cm(width)
    result.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for index, values in enumerate([headings, *rows]):
        row = result.rows[0] if index == 0 else result.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for cell, value, width in zip(row.cells, values, widths):
            cell.width = Cm(width)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(str(value))
            run.font.size = Pt(12)
            run.bold = index == 0
            if index == 0:
                shading = OxmlElement("w:shd")
                shading.set(qn("w:fill"), "EDEDED")
                cell._tc.get_or_add_tcPr().append(shading)


def cover(doc, author_info):
    for line in ("Белорусский государственный университет",
                 "Факультет прикладной математики и информатики",
                 "Кафедра информационных систем управления"):
        paragraph = doc.add_paragraph(line)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title = doc.add_paragraph("Расчётно-графическая работа №2", "Title")
    title.paragraph_format.space_before = Pt(122)
    title.paragraph_format.space_after = Pt(12)
    subtitle = doc.add_paragraph("Статистические исследования частотных словарей")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name, course, group = author_info
    author = doc.add_paragraph(f"Выполнил\nстудент {course} курса {group} группы\n{name}")
    author.paragraph_format.left_indent = Cm(8.3)
    author.paragraph_format.space_before = Pt(73)
    city = doc.add_paragraph("Минск, 2026")
    city.alignment = WD_ALIGN_PARAGRAPH.CENTER
    city.paragraph_format.space_before = Pt(116)


def contents(doc, headings):
    doc.add_heading("СОДЕРЖАНИЕ", 1)
    for page, heading in enumerate(headings, 3):
        paragraph = doc.add_paragraph(f"{heading}\t{page}")
        paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(17), WD_TAB_ALIGNMENT.RIGHT,
                                                         WD_TAB_LEADER.DOTS)


def cover_and_contents(doc, summary, author_info):
    cover(doc, author_info)
    contents(doc, HEADINGS)
    language = LANGUAGES[summary["language"]].lower()
    tokens = f"{summary['tokens']:_}".replace("_", " ")
    doc.add_paragraph(f"Язык корпуса — {language}. Число словоупотреблений — {tokens}. "
                      f"Число исходных файлов — {len(summary['files'])}.")
    if summary["tokens"] < 5_000_000:
        doc.add_paragraph("Объём этого прогона меньше 5 000 000 словоупотреблений, "
                          "предусмотренных работой №1 для корпуса одного языка.")
    doc.add_paragraph("Источник — переданные в программу TXT-файлы. Список файлов и их "
                      "контрольные суммы записаны в summary.json. Файл условий РГР №2 "
                      "задаёт три статистических исследования.")


def zipf_section(doc, out, variants):
    doc.add_heading(HEADINGS[0].upper(), 1)
    doc.add_paragraph("Постановка. Проверить соотношение f × r = c для словоформ и лемм.")
    doc.add_paragraph("Решение. Ранг присваивался по убыванию частоты. При равной "
                      "частоте слова упорядочивались лексикографически. Коэффициент c "
                      "оценивался медианой f × r. Наблюдаемые частоты и модель c/r "
                      "показаны на рисунке 1. Сводные показатели приведены в таблице 1.")
    figure(doc, out / "zipf.png", "Рисунок 1 — Частота и ранг в логарифмических шкалах")
    rows = []
    for mode, entry in zip(MODES, variants):
        fit = entry["zipf"]
        rows.append([mode, entry["unique"], number(fit["c"], 1),
                     f"{number(fit['q1'], 1)}–{number(fit['q3'], 1)}", number(fit["log_slope"])])
    table(doc, "Таблица 1 — Показатели закона Ципфа",
          ("Словарь", "Единиц", "c", "Q1–Q3 f × r", "Наклон"), rows, (3.5, 2.4, 2.8, 5.1, 3.2))
    for mode, entry in zip(MODES, variants):
        fit = entry["zipf"]
        if entry["unique"] == 1:
            result = "для проверки зависимости нужна выборка из нескольких рангов."
        elif fit["min_product"] == fit["max_product"]:
            result = "наблюдаемые произведения f × r равны."
        else:
            result = (f"f × r меняется от {fit['min_product']} до {fit['max_product']}. "
                      "Точное равенство не выполняется.")
        doc.add_paragraph(f"{mode} — {result}")
    doc.add_paragraph("Для точной модели наклон в логарифмических шкалах равен −1. "
                      "Q1–Q3 охватывают середину распределения произведений.")


def length_section(doc, out, variants):
    doc.add_heading(HEADINGS[1].upper(), 1)
    doc.add_paragraph("Постановка. Проверить, выполняется ли обратная пропорциональность длины "
                      "и частоты для служебных слов.")
    doc.add_paragraph("Решение. Из словаря отобраны слова из фиксированного списка. Для лемм "
                      "список преобразован тем же лемматизатором. Длина измеряется в буквах. "
                      "На рисунке 2 нанесена модель k/L, где k — медиана произведения f × L. "
                      "В таблице 2 указаны пределы произведения и корреляция Спирмена ρ.")
    figure(doc, out / "length.png", "Рисунок 2 — Частота и длина служебных слов")
    rows = []
    for mode, entry in zip(MODES, variants):
        length = entry["length"]
        fit = length["fit"]
        spread = "—" if fit is None else f"{fit['min_product']}–{fit['max_product']}"
        rows.append([mode, length["words"], spread, number(length["spearman"], 3)])
    table(doc, "Таблица 2 — Связь длины и частоты",
          ("Словарь", "Слов", "Диапазон f × L", "ρ"), rows, (4.5, 2.8, 5.2, 4.5))
    for mode, entry in zip(MODES, variants):
        length = entry["length"]
        rho = length["spearman"]
        if rho is None:
            result = "корреляция не определена из-за недостатка вариации или совпадений."
        else:
            direction = "отрицательная" if rho < 0 else "положительная" if rho > 0 else "нулевая"
            exact = length["fit"]["min_product"] == length["fit"]["max_product"]
            proportionality = "f × L совпадает у всех слов." if exact else "f × L меняется по словам."
            result = f"ранговая связь {direction}, {proportionality}"
        doc.add_paragraph(f"{mode} — {result}")


def dispersion_section(doc, summary, variants):
    doc.add_heading(HEADINGS[2].upper(), 1)
    doc.add_paragraph("Постановка. Рассчитать равномерность распределения каждого слова "
                      "и леммы по сегментам корпуса.")
    sizes = summary["segment_sizes"]
    span = str(sizes[0]) if sizes[0] == sizes[-1] else f"{sizes[-1]}–{sizes[0]}"
    doc.add_paragraph(f"Решение. Число сегментов — {len(sizes)}. Размер каждого — {span} слов. "
                      "Для слова вычислялись относительные частоты в каждом сегменте, "
                      "их среднее μ и среднеквадратичное отклонение σ. "
                      "D = 100 × (1 − σ / (μ × √(n − 1))). "
                      "В n включены все сегменты, в том числе с нулевой частотой. "
                      "D = 100 при равномерном распределении и D ≈ 0 при появлении "
                      "только в одном сегменте.")
    doc.add_paragraph("В таблицах 3 и 4 приведены по пять первых позиций словарей. "
                      "Столбец IPM показывает частоту на миллион словоупотреблений во всём корпусе. "
                      "Полные таблицы сохранены в dispersion-forms.csv и dispersion-lemmas.csv.")
    for index, (mode, entry) in enumerate(zip(MODES, variants), 3):
        rows = [(word, number(ipm), rank, number(d)) for word, ipm, rank, d in entry["top_dispersion"]]
        table(doc, f"Таблица {index} — {mode} по убыванию частоты",
              ("Слово", "IPM", "Ранг", "D"), rows, (5.2, 4.0, 3.5, 4.3))


def write_report(out: Path, summary, author_info):
    doc = setup_document(author_info[0])
    variants = [summary["variants"][mode] for mode in ("forms", "lemmas")]
    cover_and_contents(doc, summary, author_info)
    zipf_section(doc, out, variants)
    length_section(doc, out, variants)
    dispersion_section(doc, summary, variants)
    doc.save(out / "report.docx")
