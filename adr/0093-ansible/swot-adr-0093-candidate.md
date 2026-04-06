# SWOT-анализ candidate ADR 0093: ArtifactPlan Schema and Generator Runtime Integration

## Краткий вывод

Если ADR 0092 — это архитектурное направление, то candidate ADR 0093 — это правильный первый внедряемый шаг.
Его главная сила — конкретность и низкий риск compared to full smart-generator migration.
Главная слабость — это ещё не полный выигрыш, а только фундамент под него.

---

## Strengths

### 1. Приземляет ADR 0092 в конкретный runtime contract
0091 не спорит с 0090, а делает его исполнимым:
- schema;
- runtime integration;
- validate/build hooks;
- compatibility mode.

### 2. Хороший минимальный первый шаг
Вместо немедленного перехода к IR/programmatic emission
0091 начинает с ArtifactPlan и generation report.
Это снижает риск перегруза архитектуры.

### 3. Увеличивает наблюдаемость генерации
Появляется возможность видеть:
- что generator собирался создать;
- что реально создал;
- что пропустил;
- что считает obsolete.

### 4. Подходит для пилотной миграции
Можно начать с 1–2 Terraform family generators,
не затрагивая сразу всю экосистему шаблонов.

### 5. Хорошо ложится на CI и audit
Schema-based артефакты легко валидировать, архивировать и анализировать.

---

## Weaknesses

### 1. Сам по себе 0091 не делает генераторы “умными”
Он создаёт основу для smart generation, но без следующих шагов
может остаться просто ещё одним слоем служебных JSON-файлов.

### 2. Дополнительная сложность для runtime
Нужно обновить:
- generator runtime;
- validate stage;
- build/assemble integration;
- tests.

### 3. Mixed compatibility mode усложнит поддержку
Legacy и migrated generators придётся поддерживать одновременно.

### 4. Есть риск избыточной бюрократии
Если ArtifactPlan schema станет слишком тяжёлой,
разработчики начнут воспринимать её как обузу, а не как средство управления качеством.

---

## Opportunities

### 1. Основа для selective regeneration
После 0091 можно строить:
- точечную регенерацию;
- family-aware rebuild;
- obsolete cleanup;
- explainable diff.

### 2. Основа для richer support tooling
Generation reports можно включать в:
- support bundle;
- diagnostic output;
- release notes;
- operator audit.

### 3. База для IR layer
Когда появится стабильный ArtifactPlan,
следующим естественным шагом становится typed IR.

### 4. База для future AI advisory path
AI уже можно будет давать не “сырую вселенную данных”, а:
- stable projection;
- ArtifactPlan;
- controlled generation metadata.

### 5. Улучшение инженерной дисциплины авторов генераторов
Появится привычка думать о generator output как о контракте, а не как о побочном эффекте цикла render_template().

---

## Threats

### 1. Может быть недооценён как “слишком технический”
Есть риск, что команда увидит в 0091 только внутреннюю схему и не поймёт его стратегической ценности.

### 2. Drift между schema и кодом
Если schema будет жить отдельно от generator runtime без жёстких tests,
появится рассинхрон.

### 3. Half-implemented state
Самый опасный сценарий — начать 0091 и застрять:
- schema есть,
- runtime partially integrated,
- generators partially migrated,
- CI пока ничего толком не требует.

### 4. Неочевидная польза без пилотного внедрения
Пока не будет хотя бы одного migrated generator,
сложно показать команде реальную отдачу.

---

## Итоговая оценка

### Архитектурная ценность
Средне-высокая.

### Практическая ценность
Очень высокая как первый реализуемый шаг после ADR 0092.

### Риск внедрения
Ниже, чем у полного 0090 rollout.

### Приоритет
Очень высокий как companion ADR.

### Рекомендация
Оформить ADR 0093 официально и использовать его как первый этап внедрения ADR 0092:
1. schema;
2. runtime hook;
3. one pilot generator;
4. CI gates;
5. затем расширение на другие families
