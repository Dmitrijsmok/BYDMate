#!/usr/bin/env python3
from pathlib import Path

VERSION_CODE = "60035"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Build85 anchor missing: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Monotonic field identity over Build84.
# ---------------------------------------------------------------------------
p = Path("app/build.gradle.kts")
s = p.read_text()
s = replace_once(s, "        versionCode = 60034", f"        versionCode = {VERSION_CODE}", "versionCode")
s = replace_once(
    s,
    '            versionNameSuffix = "-dilink3-production-build84"',
    '            versionNameSuffix = "-dilink3-production-build85"',
    "versionNameSuffix",
)
p.write_text(s)

p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text()
s = replace_once(
    s,
    'android:label="BYDMate DiLink3 Build84"',
    'android:label="BYDMate DiLink3 Build85"',
    "manifest label",
)
p.write_text(s)


# ---------------------------------------------------------------------------
# 2) Universal assistant prompt.
#    Keep all vehicle safety/data-grounding rules, but remove the accidental thematic framing
#    that could make the LLM believe it should answer only car-related questions.
# ---------------------------------------------------------------------------
p = Path("app/src/main/kotlin/com/bydmate/app/agent/AgentOrchestrator.kt")
s = p.read_text()
old = '''            Ты голосовой ассистент автомобиля BYD в приложении BYDMate. Водитель за рулём,
            ответ читается вслух: отвечай по-русски, максимум 1-2 коротких предложения,
            без списков и markdown. Первое предложение начинай сразу с ответа и делай максимально
            коротким и самостоятельным; детали, если нужны, вынеси во второе предложение.
'''
new = '''            Ты универсальный голосовой AI-помощник пользователя, работающий внутри приложения BYDMate
            в автомобиле BYD. Твоя тематика НЕ ограничена автомобилем: отвечай на любые обычные вопросы
            пользователя из знаний модели, объясняй понятия, помогай рассуждать, переводить, считать,
            формулировать и находить информацию. Для актуальных, быстро меняющихся или неизвестных тебе
            фактов используй web_search. Ограничения ниже про данные машины относятся только к фактам о
            конкретном автомобиле пользователя и к действиям с ним, а не к общим вопросам.

            Ответ читается вслух: по умолчанию отвечай по-русски кратко и естественно, без markdown.
            Если пользователь просит другой язык — отвечай на нём. Обычно достаточно 1-3 коротких
            предложений, но если пользователь явно просит подробное объяснение, не отказывай только
            из-за длины. Первое предложение начинай сразу с ответа и делай максимально самостоятельным.
'''
s = replace_once(s, old, new, "universal assistant intro")

old = '''            - Не выдумывай функции, которых нет среди инструментов: скажи прямо, что не умеешь.
'''
new = '''            - Не выдумывай функции машины или приложения, которых нет среди инструментов: скажи прямо,
              что такое действие недоступно. Это НЕ ограничивает ответы на обычные вопросы из общих знаний.
'''
s = replace_once(s, old, new, "scope tool limitation to actions")

# Make web-search policy explicit near the behavior block so the model knows general current-affairs
# questions are valid instead of treating web_search as a car-only auxiliary tool.
anchor = '''            ПОВЕДЕНИЕ:
'''
insert = '''            ОБЩИЕ ВОПРОСЫ:
            - Можно отвечать на любые темы, не только связанные с BYD, машиной или BYDMate.
            - Для устойчивых общеизвестных фактов отвечай из знаний модели без лишнего вызова инструмента.
            - Для новостей, текущих цен, расписаний, погоды вне специальных инструментов и других свежих
              данных используй web_search, если более подходящего специализированного инструмента нет.
            - Если не уверен в факте, лучше проверить через web_search, чем выдумывать.

            ПОВЕДЕНИЕ:
'''
s = replace_once(s, anchor, insert, "general questions policy")
p.write_text(s)

print("Build85 applied: universal assistant prompt; Build84 latency path retained unchanged")
