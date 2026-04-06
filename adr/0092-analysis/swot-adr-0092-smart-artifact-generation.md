# SWOT-анализ ADR 0090: Smart Artifact Generation and Hybrid Rendering

## Краткий вывод

ADR 0090 — сильный архитектурный шаг. Он не ломает текущую цепочку, а переводит генераторы из режима
«рендер по списку шаблонов» в режим «объяснимое планирование артефактов + контролируемая материализация».
Главная сила ADR 0090 — эволюционность. Главный риск — рост сложности контракта генератора.

---

## Strengths

### 1. Эволюционный, а не разрушительный путь
ADR 0090 не требует big-bang переписывания существующих Terraform и Ansible generators.
Это снижает стоимость миграции и сохраняет совместимость с текущим pipeline.

### 2. Правильный перенос логики из шаблонов
Документ предлагает вынести:
- file planning,
- capability resolution,
- obsolete detection,
- generation reasons

из шаблонов в отдельный planning/IR слой.  
Это делает систему более объяснимой и тестируемой.

### 3. Хорошая база для Terraform и Ansible одновременно
ADR не привязан только к Terraform. Он допускает:
- template rendering там, где это удобно;
- structured serialization там, где формат данных сам по себе структурный;
- programmatic emission для сложных случаев.

### 4. Улучшение explainability
ArtifactPlan и generation evidence дают инженерную прозрачность:
- почему файл появился;
- почему файл не появился;
- почему файл считается obsolete;
- какой capability/bundle это активировал.

### 5. Подготовка к будущему AI-assisted path без surrender контроля
AI mode не становится главным путём.
Это защищает систему от раннего перехода к недетерминированной генерации.

---

## Weaknesses

### 1. Контракт генератора становится заметно сложнее
Generator теперь должен потенциально уметь:
- projection;
- planning;
- IR;
- render/serialize;
- evidence.

Это делает authoring generator plugins дороже.

### 2. Mixed-mode период неизбежен
Некоторое время придётся жить с двумя классами генераторов:
- legacy;
- migrated smart generators.

Это увеличит нагрузку на runtime, CI и review.

### 3. Риск “переархитектурить” слишком рано
Если попытаться быстро внедрить одновременно:
- ArtifactPlan,
- IR,
- hybrid rendering,
- obsolete management,
- AI advisory path,

можно получить архитектурный перегруз.

### 4. Не все генераторы одинаково выиграют сразу
Ansible inventory и Terraform family выиграют по-разному.
Если не выделить migration priority, можно размазать эффект.

---

## Opportunities

### 1. Реальная инженерная зрелость генераторов
ADR 0090 позволяет перейти от “template engine” к “artifact generation system”.
Это повышает качество проекта и делает его заметно сильнее как platform/framework.

### 2. Selective regeneration
После появления ArtifactPlan и family-level logic можно перейти к:
- выборочной регенерации;
- умным diff;
- точечным validate/build сценариям;
- уменьшению лишнего churn в generated outputs.

### 3. Более качественный UX для audit/support
Generation evidence можно использовать не только в CI, но и в:
- operator audit;
- support bundle;
- troubleshooting;
- future handover/reporting.

### 4. Подготовка к AI advisory mode
Когда deterministic planning будет внедрён,
AI сможет использовать stable inputs (effective_json / projection / ArtifactPlan),
а не заменять весь pipeline слепо.

### 5. Снижение хрупкости шаблонов
Чем меньше семантики в шаблонах, тем меньше скрытых ошибок и неожиданных regressions.

---

## Threats

### 1. Слишком ранняя ставка на programmatic emission
Если быстро увести Terraform generation в код вместо аккуратного hybrid-подхода,
можно получить сложный и трудночитаемый emitter layer.

### 2. Schema drift
Если ArtifactPlan, IR и runtime implementation начнут расходиться по версиям,
появится новый класс трудноуловимых ошибок.

### 3. Review overload
Smart generators потребуют ревью не только шаблонов, но и:
- planning logic;
- IR models;
- generation reports;
- obsolete policies.

### 4. Ложное ожидание от AI
Наличие AI advisory mode может породить неправильное ожидание,
что система уже готова к полной AI-генерации. Это опасно организационно.

### 5. Усложнение онбординга новых разработчиков
Входной порог для авторов generator plugins вырастет.

---

## Итоговая оценка

### Архитектурная ценность
Высокая.

### Риск внедрения
Средний.

### Приоритет
Высокий, но с поэтапной миграцией.

### Рекомендация
Принимать ADR 0090 и реализовывать его по волнам:
1. ArtifactPlan
2. generation evidence
3. structured serialization для Ansible
4. hybrid Terraform emission
5. только потом AI advisory experiments
