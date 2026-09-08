#!/usr/bin/env python3
from pathlib import Path

p = Path("app/src/test/kotlin/com/bydmate/app/agent/LlmAgentBackendTest.kt")
s = p.read_text()

old = 'assertEquals("Лимит запросов исчерпан, попробуй позже", (e as LlmError).userMessage)'
new = 'assertEquals("Лимит запросов исчерпан, HTTP 429", (e as LlmError).userMessage)'
if old not in s:
    raise SystemExit("Build73 test anchor missing: HTTP429 message")
s = s.replace(old, new, 1)

old = 'assertEquals("Сервер модели недоступен, попробуй позже", (e as LlmError).userMessage)'
new = 'assertEquals("Сервер модели недоступен, HTTP 500", (e as LlmError).userMessage)'
if old not in s:
    raise SystemExit("Build73 test anchor missing: HTTP500 message")
s = s.replace(old, new, 1)

old = '''    @Test
    fun `transient stream failure before any delta retries and falls back`() = runTest {
        coEvery { resolver.primary() } returns conn("zai")
        coEvery { resolver.fallback() } returns conn("openrouter")
        coEvery { client.chatStream("https://zai/v1", any(), any(), any(), any(), any(), any()) } returns
            Result.failure(LlmHttpException(500))
        coEvery { client.chatStream("https://openrouter/v1", any(), any(), any(), any(), any(), any()) } returns
            Result.success(JSONObject("""{"content":"Ок."}"""))
        val reply = backend.chat(listOf(AgentMessage.User("хай")), null) {}.getOrThrow()
        assertEquals("Ок.", reply.content)
        coVerify(exactly = 2) { client.chatStream("https://zai/v1", any(), any(), any(), any(), any(), any()) }
        coVerify(exactly = 1) { client.chatStream("https://openrouter/v1", any(), any(), any(), any(), any(), any()) }
    }
'''
new = '''    @Test
    fun `stream failure before any delta retries same connection non-streaming`() = runTest {
        coEvery { resolver.primary() } returns conn("zai")
        coEvery { resolver.fallback() } returns conn("openrouter")
        coEvery { client.chatStream("https://zai/v1", any(), any(), any(), any(), any(), any()) } returns
            Result.failure(LlmHttpException(500))
        coEvery { client.chatRaw("https://zai/v1", any(), any(), any(), any(), any()) } returns
            Result.success(JSONObject("""{"content":"Ок."}"""))
        val reply = backend.chat(listOf(AgentMessage.User("хай")), null) {}.getOrThrow()
        assertEquals("Ок.", reply.content)
        coVerify(exactly = 1) { client.chatStream("https://zai/v1", any(), any(), any(), any(), any(), any()) }
        coVerify(exactly = 1) { client.chatRaw("https://zai/v1", any(), any(), any(), any(), any()) }
        coVerify(exactly = 0) { client.chatStream("https://openrouter/v1", any(), any(), any(), any(), any(), any()) }
    }
'''
if old not in s:
    raise SystemExit("Build73 test anchor missing: stream fallback test")
s = s.replace(old, new, 1)

p.write_text(s)
print("Build73 tests aligned with intentional runtime behavior")
