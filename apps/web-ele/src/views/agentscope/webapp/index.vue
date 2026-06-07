<script lang="ts" setup>
import type { PublicAppMeta } from '#/api/agentscope/publish';

import { nextTick, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';

import { IconifyIcon } from '@vben/icons';

import { ElButton, ElInput } from 'element-plus';

import { getPublicAppMeta, streamPublicChat } from '#/api/agentscope/publish';

interface Msg {
  role: 'assistant' | 'user';
  text: string;
}

const route = useRoute();
const token = String(route.params.token ?? '');

const meta = ref<null | PublicAppMeta>(null);
const error = ref('');
const messages = ref<Msg[]>([]);
const input = ref('');
const sending = ref(false);
const conversationId = ref('');
const scroller = ref<HTMLElement | null>(null);

async function scrollDown() {
  await nextTick();
  if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight;
}

onMounted(async () => {
  try {
    meta.value = await getPublicAppMeta(token);
    if (meta.value.opening_statement) {
      messages.value.push({
        role: 'assistant',
        text: meta.value.opening_statement,
      });
    }
  } catch {
    error.value = 'Application not found or offline.';
  }
});

async function send(text?: string) {
  const query = (text ?? input.value).trim();
  if (!query || sending.value) return;
  input.value = '';
  messages.value.push({ role: 'user', text: query });
  const assistant: Msg = reactive({ role: 'assistant', text: '' });
  messages.value.push(assistant);
  sending.value = true;
  await scrollDown();
  try {
    conversationId.value = await streamPublicChat({
      token,
      query,
      conversationId: conversationId.value || undefined,
      onDelta: (delta) => {
        assistant.text += delta;
        void scrollDown();
      },
    });
  } catch {
    assistant.text = '请求失败，请稍后重试。';
  } finally {
    sending.value = false;
    await scrollDown();
  }
}
</script>

<template>
  <div class="webapp-root flex flex-col bg-gray-50 dark:bg-zinc-900">
    <div v-if="error" class="flex flex-1 items-center justify-center">
      <div class="text-center text-gray-500">
        <IconifyIcon icon="lucide:unplug" class="mb-2 text-5xl" />
        {{ error }}
      </div>
    </div>

    <template v-else-if="meta">
      <!-- Header -->
      <header
        class="flex items-center gap-3 border-b bg-white px-4 py-3 sm:px-6 sm:py-4 dark:border-zinc-700 dark:bg-zinc-800"
      >
        <IconifyIcon
          v-if="meta.icon && meta.icon.includes(':')"
          :icon="meta.icon"
          class="text-2xl"
        />
        <span v-else class="text-2xl">{{ meta.icon }}</span>
        <div>
          <div class="font-semibold">{{ meta.name }}</div>
          <div class="text-xs text-gray-400">{{ meta.description }}</div>
        </div>
      </header>

      <!-- Messages -->
      <main
        ref="scroller"
        class="flex-1 overflow-y-auto px-3 py-4 sm:px-4 sm:py-6"
      >
        <div class="mx-auto flex max-w-3xl flex-col gap-4">
          <div
            v-for="(m, i) in messages"
            :key="i"
            class="flex"
            :class="m.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm"
              :class="
                m.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-800 dark:bg-zinc-800 dark:text-gray-100'
              "
            >
              {{ m.text || '…' }}
            </div>
          </div>

          <!-- Suggested questions -->
          <div
            v-if="messages.length <= 1 && meta.suggested_questions.length > 0"
            class="flex flex-wrap gap-2"
          >
            <button
              v-for="(q, i) in meta.suggested_questions"
              :key="i"
              class="rounded-full border border-gray-300 bg-white px-3 py-1.5 text-xs text-gray-600 hover:border-blue-400 hover:text-blue-600 dark:border-zinc-600 dark:bg-zinc-800 dark:text-gray-300"
              @click="send(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>
      </main>

      <!-- Composer -->
      <footer
        class="webapp-composer border-t bg-white px-3 py-2.5 sm:px-4 sm:py-3 dark:border-zinc-700 dark:bg-zinc-800"
      >
        <div class="mx-auto flex max-w-3xl items-end gap-2">
          <ElInput
            v-model="input"
            :autosize="{ minRows: 1, maxRows: 5 }"
            :disabled="sending"
            placeholder="输入消息…"
            type="textarea"
            @keydown.enter.exact.prevent="send()"
          />
          <ElButton :loading="sending" type="primary" @click="send()">
            发送
          </ElButton>
        </div>
        <div class="mt-2 text-center text-xs text-gray-300">
          Powered by AgentScope Admin
        </div>
      </footer>
    </template>
  </div>
</template>

<style scoped>
/* Cross-platform full-height: dynamic viewport unit avoids the mobile
 * browser chrome clipping the composer; falls back to vh on older engines. */
.webapp-root {
  height: 100vh;
  height: 100dvh;
}

/* Respect the home-indicator / notch safe area on iOS/Android. */
.webapp-composer {
  padding-bottom: calc(0.625rem + env(safe-area-inset-bottom, 0px));
}
</style>
