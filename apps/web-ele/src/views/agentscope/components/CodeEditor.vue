<script setup lang="ts">
import type { Extension } from '@codemirror/state';

import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { autocompletion } from '@codemirror/autocomplete';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { javascript } from '@codemirror/lang-javascript';
import { json } from '@codemirror/lang-json';
import { python } from '@codemirror/lang-python';
import {
  bracketMatching,
  defaultHighlightStyle,
  foldGutter,
  indentOnInput,
  syntaxHighlighting,
} from '@codemirror/language';
import { lintGutter } from '@codemirror/lint';
import { EditorState } from '@codemirror/state';
import { oneDark } from '@codemirror/theme-one-dark';
import {
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from '@codemirror/view';

const props = withDefaults(
  defineProps<{
    /** Programming language for syntax highlighting. */
    language?: 'javascript' | 'json' | 'python';
    /** Minimum editor height (px). */
    minHeight?: number;
    modelValue?: string;
    placeholder?: string;
    readonly?: boolean;
  }>(),
  {
    language: 'python',
    minHeight: 160,
    modelValue: '',
    placeholder: '',
    readonly: false,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
}>();

const host = ref<HTMLDivElement>();
let view: EditorView | undefined;

function isDark(): boolean {
  return document.documentElement.classList.contains('dark');
}

function languageExtension(): Extension {
  switch (props.language) {
    case 'javascript': {
      return javascript();
    }
    case 'json': {
      return json();
    }
    default: {
      return python();
    }
  }
}

function buildExtensions(): Extension[] {
  const ext: Extension[] = [
    lineNumbers(),
    foldGutter(),
    history(),
    indentOnInput(),
    bracketMatching(),
    highlightActiveLine(),
    highlightActiveLineGutter(),
    autocompletion(),
    lintGutter(),
    keymap.of([...defaultKeymap, ...historyKeymap]),
    languageExtension(),
    EditorView.lineWrapping,
    EditorState.readOnly.of(props.readonly),
    EditorView.theme({
      '&': { fontSize: '13px', minHeight: `${props.minHeight}px` },
      '.cm-content': {
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      },
      '.cm-scroller': { overflow: 'auto' },
      '&.cm-focused': { outline: 'none' },
    }),
    EditorView.updateListener.of((v) => {
      if (v.docChanged) {
        emit('update:modelValue', v.state.doc.toString());
      }
    }),
    isDark()
      ? oneDark
      : syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
  ];
  return ext;
}

function createView() {
  if (!host.value) return;
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.modelValue ?? '',
      extensions: buildExtensions(),
    }),
  });
}

function recreate() {
  view?.destroy();
  createView();
}

onMounted(createView);

onBeforeUnmount(() => {
  view?.destroy();
  view = undefined;
});

watch(
  () => props.modelValue,
  (val) => {
    if (view && val !== view.state.doc.toString()) {
      view.dispatch({
        changes: { from: 0, insert: val ?? '', to: view.state.doc.length },
      });
    }
  },
);

watch(() => [props.language, props.readonly], recreate);

// React to global dark/light toggle.
let observer: MutationObserver | undefined;
onMounted(() => {
  observer = new MutationObserver(() => recreate());
  observer.observe(document.documentElement, {
    attributeFilter: ['class'],
    attributes: true,
  });
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<template>
  <div ref="host" class="code-editor" :data-placeholder="placeholder"></div>
</template>

<style scoped>
.code-editor {
  overflow: hidden;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
}

.code-editor :deep(.cm-editor) {
  background: var(--el-fill-color-blank);
}
</style>
