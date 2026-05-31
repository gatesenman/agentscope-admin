<script lang="ts" setup>
import type { TraceRun, TraceSpan } from '#/api/agentscope/observability';

import { IconifyIcon } from '@vben/icons';

import { ElTag } from 'element-plus';

import { $t } from '#/locales';

defineProps<{ runs: TraceRun[] }>();

interface KindMeta {
  icon: string;
  color: string;
  label: string;
}

const KIND_META: Record<string, KindMeta> = {
  confirm: {
    icon: 'lucide:hand',
    color: '#d97706',
    label: 'agentscope.obs.spanConfirm',
  },
  error: {
    icon: 'lucide:circle-x',
    color: '#dc2626',
    label: 'agentscope.obs.spanError',
  },
  knowledge: {
    icon: 'lucide:book-open',
    color: '#0891b2',
    label: 'agentscope.obs.spanKnowledge',
  },
  model: {
    icon: 'lucide:sparkles',
    color: '#7c3aed',
    label: 'agentscope.obs.spanModel',
  },
  ontology: {
    icon: 'lucide:network',
    color: '#2563eb',
    label: 'agentscope.obs.spanOntology',
  },
  reply: {
    icon: 'lucide:message-square',
    color: '#16a34a',
    label: 'agentscope.obs.spanReply',
  },
  tool: {
    icon: 'lucide:wrench',
    color: '#ea580c',
    label: 'agentscope.obs.spanTool',
  },
};

const DEFAULT_META: KindMeta = {
  icon: 'lucide:wrench',
  color: '#ea580c',
  label: 'agentscope.obs.spanTool',
};

function meta(kind: string): KindMeta {
  return KIND_META[kind] ?? DEFAULT_META;
}

function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function spanTokens(s: TraceSpan): number {
  return (s.input_tokens ?? 0) + (s.output_tokens ?? 0);
}
</script>

<template>
  <div class="trace">
    <div v-for="(run, ri) in runs" :key="run.run_id" class="trace-run">
      <div class="trace-run__head">
        <span class="trace-run__title">
          {{ $t('agentscope.obs.run') }} #{{ runs.length - ri }}
        </span>
        <span class="trace-run__time">
          {{ new Date(run.started_at).toLocaleString() }}
        </span>
        <div class="trace-run__meta">
          <ElTag
            size="small"
            :type="run.status === 'error' ? 'danger' : 'success'"
          >
            {{ run.status }}
          </ElTag>
          <span>{{ fmtMs(run.duration_ms) }}</span>
          <span>{{ run.total_tokens }} tok</span>
          <span>${{ run.cost.toFixed(4) }}</span>
        </div>
      </div>

      <div class="trace-spans">
        <div v-for="span in run.spans" :key="span.id" class="span">
          <div class="span__rail">
            <span
              class="span__dot"
              :style="{ background: meta(span.kind).color }"
            >
              <IconifyIcon :icon="meta(span.kind).icon" class="span__icon" />
            </span>
          </div>
          <div class="span__body">
            <div class="span__head">
              <span
                class="span__kind"
                :style="{ color: meta(span.kind).color }"
              >
                {{ $t(meta(span.kind).label) }}
              </span>
              <span class="span__name">{{ span.name }}</span>
              <span class="span__spacer"></span>
              <span v-if="spanTokens(span)" class="span__chip">
                {{ spanTokens(span) }} tok
              </span>
              <span class="span__chip">{{ fmtMs(span.duration_ms) }}</span>
              <ElTag
                v-if="span.status !== 'ok'"
                size="small"
                :type="span.status === 'error' ? 'danger' : 'warning'"
              >
                {{ span.status }}
              </ElTag>
            </div>
            <details v-if="span.input_text" class="span__io">
              <summary>{{ $t('agentscope.obs.input') }}</summary>
              <pre>{{ span.input_text }}</pre>
            </details>
            <details v-if="span.output_text" class="span__io" open>
              <summary>{{ $t('agentscope.obs.output') }}</summary>
              <pre>{{ span.output_text }}</pre>
            </details>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trace-run {
  margin-bottom: 20px;
}

.trace-run__head {
  display: flex;
  gap: 10px;
  align-items: center;
  padding-bottom: 8px;
  margin-bottom: 8px;
  border-bottom: 1px dashed var(--el-border-color);
}

.trace-run__title {
  font-size: 14px;
  font-weight: 600;
}

.trace-run__time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.trace-run__meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.trace-spans {
  position: relative;
}

.span {
  display: flex;
  gap: 12px;
}

.span__rail {
  position: relative;
  display: flex;
  justify-content: center;
  width: 26px;
}

.span__rail::before {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 2px;
  content: '';
  background: var(--el-border-color-light);
  transform: translateX(-50%);
}

.span:first-child .span__rail::before {
  top: 13px;
}

.span:last-child .span__rail::before {
  bottom: calc(100% - 13px);
}

.span__dot {
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  margin-top: 2px;
  color: #fff;
  border-radius: 50%;
}

.span__icon {
  font-size: 14px;
}

.span__body {
  flex: 1;
  min-width: 0;
  padding-bottom: 14px;
}

.span__head {
  display: flex;
  gap: 8px;
  align-items: center;
  min-height: 30px;
}

.span__kind {
  font-size: 13px;
  font-weight: 600;
}

.span__name {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.span__spacer {
  flex: 1;
}

.span__chip {
  padding: 1px 7px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border-radius: 10px;
}

.span__io {
  margin-top: 4px;
}

.span__io summary {
  font-size: 12px;
  color: var(--el-color-primary);
  cursor: pointer;
}

.span__io pre {
  max-height: 240px;
  padding: 8px 10px;
  margin: 6px 0 0;
  overflow: auto;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}
</style>
