# Автоматична валідація TextGrid-анотацій мовленнєвого корпусу.
# Програма знаходить файли TextGrid у вказаній папці, перевіряє структуру, рівні,
# часові межі, коди емоцій та форматування тексту і створює звіт results/report.txt.
# Запуск: python validator.py [шлях до папки з даними]   (за замовчуванням data/sample)

# Імпорт необхідних бібліотек
import sys
import textgrid
import re
from pathlib import Path
from typing import List, Dict

class TextGridValidator:
    # Словник очікуваних назв рівнів у файлі TextGrid
    EXPECTED_TIERS = ['SPK-A-text', 'SPK-A-emo', 'SPK-B-text', 'SPK-B-emo', 'clap-sync']

    # Набір допустимих кодів емоцій (базові коди + інтенсивність 1-3)
    VALID_EMOTIONS = {
        'j1', 'j2', 'j3', 'sad1', 'sad2', 'sad3', 'an1', 'an2', 'an3', 'f1', 'f2', 'f3',
        'nsur1', 'nsur2', 'nsur3', 'psur1', 'psur2', 'psur3', 'dis1', 'dis2', 'dis3',
        'con1', 'con2', 'con3', 'ad1', 'ad2', 'ad3', 'o', 'n'
    }

    # Емоції, які обов'язково повинні мати цифру інтенсивності (1-3)
    EMOTIONS_WITH_INTENSITY = {'j', 'sad', 'an', 'f', 'nsur', 'psur', 'dis', 'con', 'ad'}

    # Емоції, які не можуть мати цифру інтенсивності
    EMOTIONS_WITHOUT_INTENSITY = {'o', 'n'}

    # Допустимі маркери, які можуть з'являтися всередині зірочок
    VALID_STAR_MARKS = {
        'у', 'р', 'р-укр', 'р-ак', 'англ', 'нім', 'фр', 'с', 'ін',
        'о', 'об', 'роз', 'пскл', 'пбкв', 'з', 'шеп', 'гарк', 'зклдн', 'клуб',
        'шт', 'см', 'сміх', 'плач', 'зітх', 'к', 'кд', 'вд', 'івд', 'пл', 'шм',
        'е', 'угу', 'позіх', 'хм', 'гкхм', 'пф', 'у-у', 'м', 'сьорб', 'св', 'ковт',
        'м-м', 'ммм', 'м-мм', 'ааа', 'мммм', 'ім', 'йой', 'виг', 'цьом', 'плю',
        'хлип', 'цок', 'чих', 'насп', 'відриг', 'гик', 'пос', 'крк', 'тч', 'спів',
        'шепіт', 'усвід', 'розч', 'сарк', 'хв', 'посл'
    }

    def __init__(self):
        self.errors = []

    def validate_file(self, filepath: Path) -> List[Dict]:
        # Скидаємо попередні помилки
        self.errors = []
        try:
            tg = textgrid.TextGrid.fromFile(str(filepath))
        except Exception as e:
            self.errors.append({'file': filepath.name, 'check': 'READ_ERROR', 'msg': str(e)})
            return self.errors

        #Перевірка кількості рівнів
        if len(tg.tiers) != 5:
            self.errors.append({'file': filepath.name, 'check': '9_TIER_COUNT',
                                'msg': f'Знайдено менше ніж 5 рівнів: {len(tg.tiers)}'})
            return self.errors

        #Перевірка назв рівнів
        for i, tier in enumerate(tg.tiers):
            if tier.name not in self.EXPECTED_TIERS:
                self.errors.append({'file': filepath.name, 'check': '4_TIER_NAME',
                                    'msg': f'Рівень {i}: "{tier.name}" - очікується {self.EXPECTED_TIERS}'})

        # Формуємо словник доступних рівнів для швидкого доступу
        tiers = {tier.name: tier for tier in tg.tiers if tier.name in self.EXPECTED_TIERS}
        if len(tiers) != 5:
            return self.errors

        for spk in ['SPK-A', 'SPK-B']:
            text_tier = tiers[f'{spk}-text']
            emo_tier = tiers[f'{spk}-emo']

            # Перевірка першого елемента на наявність *у*
            if len(text_tier) > 0:
                first_text = text_tier[0].mark.strip() if text_tier[0].mark else ''
                if first_text and not first_text.startswith('*у*'):
                    self.errors.append({'file': filepath.name, 'check': '13_FIRST_UTTERANCE_NO_U',
                                        'msg': f'{spk}: перший елемент не починається з *у*. Початок: "{first_text[:50]}"',
                                        'time': f'{text_tier[0].minTime:.3f}-{text_tier[0].maxTime:.3f}'})

            # Перевірка кожного інтервалу в парі (текст + емоція)
            for i, (t_int, e_int) in enumerate(zip(text_tier, emo_tier)):

                # Перевірка синхронізації часових меж
                if abs(t_int.minTime - e_int.minTime) > 0.001:
                    self.errors.append({'file': filepath.name, 'check': '3_BOUNDARY',
                                        'msg': f'{spk} інт.{i + 1}: початок не збігається ({t_int.minTime:.3f} vs {e_int.minTime:.3f})',
                                        'time': f'{t_int.minTime:.3f}-{t_int.maxTime:.3f}'})

                if abs(t_int.maxTime - e_int.maxTime) > 0.001:
                    self.errors.append({'file': filepath.name, 'check': '3_BOUNDARY',
                                        'msg': f'{spk} інт.{i + 1}: кінець не збігається ({t_int.maxTime:.3f} vs {e_int.maxTime:.3f})',
                                        'time': f'{t_int.minTime:.3f}-{t_int.maxTime:.3f}'})

                # Отримуємо вміст полів
                t_text = t_int.mark.strip() if t_int.mark else ''
                e_text = e_int.mark.strip() if e_int.mark else ''

                # Перевірка наявності тексту та емоції
                if t_text and not e_text:
                    self.errors.append({'file': filepath.name, 'check': '6_EMPTY_EMOTION',
                                        'msg': f'{spk} інт.{i + 1}: є текст "{t_text[:30]}", але емоція порожня',
                                        'time': f'{t_int.minTime:.3f}-{t_int.maxTime:.3f}'})

                if not t_text and e_text:
                    self.errors.append({'file': filepath.name, 'check': '6_ORPHAN_EMOTION',
                                        'msg': f'{spk} інт.{i + 1}: текст порожній, але є емоція "{e_text}"',
                                        'time': f'{t_int.minTime:.3f}-{t_int.maxTime:.3f}'})

                # Детальні перевірки вмісту
                if t_text:
                    self._check_text(t_text, spk, i + 1, t_int, filepath.name)
                if e_text:
                    self._check_emotion(e_text, spk, i + 1, e_int, filepath.name)

        # Перевірка мітки clap
        clap_tier = tiers.get('clap-sync')
        if clap_tier:
            claps = [i for i in clap_tier if i.mark and i.mark.strip()]
            if len(claps) == 0:
                self.errors.append({'file': filepath.name, 'check': '8_CLAP_MISSING', 'msg': 'Немає мітки clap'})
            elif len(claps) > 1:
                self.errors.append({'file': filepath.name, 'check': '8_CLAP_MULTIPLE',
                                    'msg': f'Знайдено {len(claps)} міток clap (дозволено 1)'})
            elif claps[0].mark.strip().lower() != 'clap':
                self.errors.append({'file': filepath.name, 'check': '8_CLAP_WRONG',
                                    'msg': f'Не знайдено мітку "clap", неправильний формат "{claps[0].mark}"'})

        # Перевірка на переплутані поля (текст у полі емоцій, емоція у полі тексту)
        for spk in ['SPK-A', 'SPK-B']:
            for interval in tiers[f'{spk}-emo']:
                mark = interval.mark.strip() if interval.mark else ''
                if mark and len(mark) > 4 and re.search(r'[а-яієїґ]', mark.lower()):
                    self.errors.append({'file': filepath.name, 'check': '10_TEXT_IN_EMO',
                                        'msg': f'{spk}: текст "{mark}" в рівні емоцій',
                                        'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})

            for interval in tiers[f'{spk}-text']:
                mark = interval.mark.strip() if interval.mark else ''
                if mark and mark in self.VALID_EMOTIONS:
                    self.errors.append({'file': filepath.name, 'check': '10_EMO_IN_TEXT',
                                        'msg': f'{spk}: емоція "{mark}" в тексті',
                                        'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})

        return self.errors

    def _check_text(self, text: str, spk: str, idx: int, interval, filename: str):
        # Перевірка пробілів
        if text.startswith(' '):
            self.errors.append({'file': filename, 'check': '11_LEADING_SPACE',
                                'msg': f'{spk} інт.{idx}: текст починається з пробілу: "{text[:30]}"',
                                'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})

        if text.endswith(' '):
            self.errors.append({'file': filename, 'check': '11_FINAL_SPACE',
                                'msg': f'{spk} інт.{idx}: текст містить пробіл в кінці: "...{text[-30:]}"',
                                'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})

        if '  ' in text:
            self.errors.append({'file': filename, 'check': '12_DOUBLE_SPACE',
                                'msg': f'{spk} інт.{idx}: знайдено подвійні пробіли: "{text[:50]}"',
                                'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})

        # Перевірка форматування маркерів у зірочках
        for mark in self.VALID_STAR_MARKS:

            # Маркер зливається з попереднім словом (немає пробілу зліва)
            pattern_merge_left = rf'[^ ]\*{re.escape(mark)}\*'
            for m in re.finditer(pattern_merge_left, text):
                self.errors.append({'file': filename, 'check': '1_STAR_MERGE_LEFT',
                                    'msg': f'{spk} інт.{idx}: зірочки зливаються зліва: "...{text[max(0, m.start()):m.end()]}..." (має бути пробіл перед *{mark}*)',
                                    'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})
                break

            # Маркер зливається з наступним словом (немає пробілу справа)
            pattern_merge_right = rf'\*{re.escape(mark)}\*[^ ]'
            for m in re.finditer(pattern_merge_right, text):
                self.errors.append({'file': filename, 'check': '1_STAR_MERGE_RIGHT',
                                    'msg': f'{spk} інт.{idx}: зірочки зливаються справа: "...{text[m.start():min(m.end() + 5, len(text))]}..." (має бути пробіл після *{mark}*)',
                                    'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})
                break

            # Пробіли всередині зірочок
            patterns = [
                (rf'\* {re.escape(mark)}\*', f'* {mark}*'),
                (rf'\*{re.escape(mark)} \*', f'*{mark} *'),
                (rf'\* {re.escape(mark)} \*', f'* {mark} *')
            ]
            for pattern, wrong_format in patterns:
                for m in re.finditer(pattern, text):
                    self.errors.append({'file': filename, 'check': '2_STAR_INTERNAL_SPACE',
                                        'msg': f'{spk} інт.{idx}: пробіл всередині зірочок: "{m.group(0)}" (має бути *{mark}*)',
                                        'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})
                    break

    def _check_emotion(self, emotion: str, spk: str, idx: int, interval, filename: str):
        emo_low = emotion.lower()

        # Перевірка валідності коду
        if emo_low not in self.VALID_EMOTIONS:
            self.errors.append({'file': filename, 'check': '5_INVALID_EMOTION',
                                'msg': f'{spk} інт.{idx}: недозволена емоція "{emotion}"',
                                'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})
            return

        # Перевірка правильності інтенсивності
        base = re.sub(r'[0-9]', '', emo_low)
        has_digit = bool(re.search(r'[0-9]', emo_low))

        if base in self.EMOTIONS_WITH_INTENSITY and not has_digit:
            self.errors.append({'file': filename, 'check': '7_MISSING_INTENSITY',
                                'msg': f'{spk} інт.{idx}: "{emotion}" має мати цифру від 1 до 3',
                                'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})
        elif base in self.EMOTIONS_WITHOUT_INTENSITY and has_digit:
            self.errors.append({'file': filename, 'check': '7_UNEXPECTED_INTENSITY',
                                'msg': f'{spk} інт.{idx}: "{emotion}" не має мати цифру',
                                'time': f'{interval.minTime:.3f}-{interval.maxTime:.3f}'})

def find_annotation_files(base_path: Path) -> List[Path]:
    files = []
    lines = []
    # Список шаблонів для пошуку файлів
    patterns = [
        "DLG*/audio/MIC3/*.TextGrid",  # Оригінальні записи MIC3
        "DLG*/audio/MIC1/*_synced.TextGrid",  # Синхронізовані MIC1
        "DLG*/audio/MIC2/*_synced.TextGrid",  # Синхронізовані MIC2
        "DLG*/sync/*.TextGrid",  # Додаткові файли
    ]

    for pattern in patterns:
        found_files = list(base_path.glob(pattern))
        files.extend(found_files)
        if found_files:
            lines.append(f"\n[ЗНАЙДЕНО] {len(found_files)} файлів за шаблоном: {pattern}")
            for f in found_files:
                try:
                    rel_path = f.relative_to(base_path)
                    lines.append(f"  → {rel_path}")
                except:
                    lines.append(f"  → {f}")

    return files, lines

def main():
    # Налаштування шляхів: папка з даними береться з аргументу, звіт зберігається в results/
    base_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sample")
    output_file = Path("results/report.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    # Заголовок звіту
    lines.append("РЕЗУЛЬТАТИ ПЕРЕВІРКИ АНОТАЦІЙ")
    lines.append(f"Шлях пошуку: {base_path.name}")

    # Перевірка існування директорії
    if not base_path.exists():
        lines.append(f" Директорія не існує: {base_path.name}")
    else:
        # Пошук файлів
        files, search_lines = find_annotation_files(base_path)
        lines.extend(search_lines)

        if not files:
            lines.append(f'\n Файлів TextGrid не знайдено')
        else:
            lines.append(f"Всього знайдено: {len(files)} файлів")

            # Ініціалізація валідатора
            validator = TextGridValidator()
            all_errors = []
            files_with_errors = set()
            error_count_by_file = {}

            # Валідація кожного файлу
            for f in files:
                errors = validator.validate_file(f)
                all_errors.extend(errors)

                if errors:
                    files_with_errors.add(f.name)
                    error_count_by_file[f.name] = len(errors)

                    # Детальний звіт для файлу з помилками
                    lines.append(f" ФАЙЛ: {f.name} [ВИЯВЛЕНО ПОМИЛКИ]")

                    # Групування помилок за типами
                    errors_by_type = {}
                    for err in errors:
                        check_type = err["check"]
                        if check_type not in errors_by_type:
                            errors_by_type[check_type] = []
                        errors_by_type[check_type].append(err)

                    for check_type, errs in errors_by_type.items():
                        lines.append(f"\n   Тип помилки: {check_type} (всього: {len(errs)})")
                        lines.append(f"   " + "-" * 60)
                        for err in errs:
                            time_str = f" [час: {err.get('time', '')}]" if err.get('time') else ''
                            lines.append(f"     • {err['msg']}{time_str}")
                else:
                    lines.append(f'\n ФАЙЛ: {f.name}')
                    lines.append(f"   Помилок не виявлено")

            # Підсумкова статистика
            lines.append("\n" + "=" * 70)
            lines.append(" Висновок")
            lines.append(f"Загальна кількість перевірених файлів:  {len(files)}")
            lines.append(f"Кількість файлів з помилками:          {len(files_with_errors)}")
            lines.append(f"Кількість коректних файлів:            {len(files) - len(files_with_errors)}")
            lines.append(f"Загальна кількість знайдених помилок:  {len(all_errors)}")

            # Список проблемних файлів
            if files_with_errors:
                lines.append(f"\nФайли, що містять помилки")
                for fname in sorted(files_with_errors):
                    lines.append(f"  • {fname} → {error_count_by_file[fname]} помилок")

                # Статистика за типами помилок
                lines.append(f"\nЗагальна статистика")
                errors_by_type_total = {}
                for err in all_errors:
                    check_type = err["check"]
                    if check_type not in errors_by_type_total:
                        errors_by_type_total[check_type] = 0
                    errors_by_type_total[check_type] += 1

                for check_type, count in sorted(errors_by_type_total.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"  • {check_type}: {count} помилок")

    # Збереження звіту
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Звіт збережено у файл: {output_file}")

if __name__ == '__main__':
    main()
