# Decision Note: связка ADR 0090 и ADR 0091

## Зачем нужны оба документа

### ADR 0090
ADR 0090 задаёт архитектурный вектор:
- переход от template-only мышления к smart artifact generation;
- ввод planning stage и typed IR;
- hybrid rendering;
- подготовка к более умной и объяснимой генерации Terraform и Ansible артефактов;
- сохранение совместимости с существующей pipeline-цепочкой.

Это **рамочный архитектурный ADR**.

### ADR 0091 (candidate)
ADR 0091 нужен как implementation companion:
- закрепляет конкретный контракт `ArtifactPlan`;
- описывает, как генераторы публикуют generation evidence;
- фиксирует schema/runtime/CI integration;
- превращает идеи ADR 0090 в проверяемый и внедряемый runtime-step.

Это **прикладной ADR следующего шага**.

## Какой порядок реализации правильный

1. Утвердить ADR 0090.
2. Создать/утвердить ADR 0091 как implementation-level спецификацию.
3. Внедрить ArtifactPlan и generation reports для одного Terraform family generator.
4. Затем распространить модель на Ansible family.
5. После этого возвращаться к AI advisory mode.

## Главная инженерная мысль

0090 отвечает на вопрос: **"какой должна быть умная система генерации?"**  
0091 отвечает на вопрос: **"как именно встроить первый обязательный слой этой системы в текущий runtime?"**
