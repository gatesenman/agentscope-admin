<script lang="ts" setup>
import type { AgentRecord } from '#/api/agentscope';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';

import {
  ElButton,
  ElCard,
  ElMessage,
  ElOption,
  ElSelect,
  ElTabPane,
  ElTabs,
} from 'element-plus';

import { agentApi, getAgentScopeUserId } from '#/api/agentscope';
import { $t } from '#/locales';

const agents = ref<AgentRecord[]>([]);
const agentId = ref('');
const userId = getAgentScopeUserId();
const baseUrl = `${globalThis.location?.origin ?? ''}/api`;

const curlSnippet = computed(
  () => String.raw`# 1) Create a session
curl -X POST "${baseUrl}/sessions/" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: ${userId}" \
  -d '{"agent_id": "${agentId.value || '<AGENT_ID>'}"}'

# 2) Chat (Server-Sent Events stream)
curl -N -X POST "${baseUrl}/chat/" \
  -H "Content-Type: application/json" \
  -H "X-User-ID: ${userId}" \
  -d '{
    "agent_id": "${agentId.value || '<AGENT_ID>'}",
    "session_id": "<SESSION_ID>",
    "input": {"name": "user", "role": "user",
              "content": [{"type": "text", "text": "Hello"}]}
  }'`,
);

const pythonSnippet = computed(
  () => `import requests, json

BASE = "${baseUrl}"
HEADERS = {"X-User-ID": "${userId}", "Content-Type": "application/json"}

# Create a session
session = requests.post(
    f"{BASE}/sessions/",
    headers=HEADERS,
    json={"agent_id": "${agentId.value || '<AGENT_ID>'}"},
).json()

# Stream a chat reply
resp = requests.post(
    f"{BASE}/chat/",
    headers=HEADERS,
    json={
        "agent_id": "${agentId.value || '<AGENT_ID>'}",
        "session_id": session["session_id"],
        "input": {"name": "user", "role": "user",
                  "content": [{"type": "text", "text": "Hello"}]},
    },
    stream=True,
)
for line in resp.iter_lines():
    if line and line.startswith(b"data:"):
        print(json.loads(line[5:]))`,
);

async function load() {
  const res = await agentApi.listAgents();
  agents.value = res.agents ?? [];
  if (agents.value[0]) agentId.value = agents.value[0].id;
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success($t('agentscope.integration.copied'));
  } catch {
    ElMessage.error('Copy failed');
  }
}

onMounted(load);
</script>

<template>
  <Page :title="$t('agentscope.integration.title')">
    <ElCard class="mb-4" shadow="never">
      <div class="flex items-center gap-3">
        <span class="text-sm font-medium">{{
          $t('agentscope.menu.agents')
        }}</span>
        <ElSelect v-model="agentId" class="w-72">
          <ElOption
            v-for="a in agents"
            :key="a.id"
            :label="a.data.name"
            :value="a.id"
          />
        </ElSelect>
        <span class="text-foreground/50 text-xs">
          Base URL: {{ baseUrl }} · X-User-ID: {{ userId }}
        </span>
      </div>
    </ElCard>

    <ElCard shadow="never">
      <ElTabs>
        <ElTabPane :label="$t('agentscope.integration.curl')" name="curl">
          <div class="flex justify-end">
            <ElButton link type="primary" @click="copy(curlSnippet)">
              {{ $t('agentscope.integration.copy') }}
            </ElButton>
          </div>
          <pre
            class="bg-accent overflow-auto rounded p-4 text-xs leading-relaxed"
            v-text="curlSnippet"
          ></pre>
        </ElTabPane>
        <ElTabPane :label="$t('agentscope.integration.python')" name="python">
          <div class="flex justify-end">
            <ElButton link type="primary" @click="copy(pythonSnippet)">
              {{ $t('agentscope.integration.copy') }}
            </ElButton>
          </div>
          <pre
            class="bg-accent overflow-auto rounded p-4 text-xs leading-relaxed"
            v-text="pythonSnippet"
          ></pre>
        </ElTabPane>
      </ElTabs>
    </ElCard>
  </Page>
</template>
